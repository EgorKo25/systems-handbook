#!/usr/bin/env python3
"""Owned, persistent local lab. No shell expansion; no automatic reset/clean.

Run from the copied labs/ directory. Configuration and generated runtime are
private, outside the public handbook. Mutations only reach the marked cluster.
"""
from pathlib import Path
import argparse
import getpass
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / '.private'
CONFIG = PRIVATE / 'runtime.json'
MARKER = '.handbook-flyway-owned-cluster'


def run(argv, *, env=None, input=None, capture=False, check=True):
    result = subprocess.run([str(a) for a in argv], cwd=ROOT, env=env,
                            input=input, text=True, capture_output=capture)
    if check and result.returncode:
        # PostgreSQL/Flyway errors may contain SQL data; private logs only.
        if capture:
            print(result.stderr[-3000:], file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(text)


def load():
    if not CONFIG.is_file():
        raise SystemExit('Run configure first; no implicit connection target')
    if CONFIG.stat().st_mode & 0o077:
        raise SystemExit('runtime.json must have mode 0600')
    c = json.loads(CONFIG.read_text())
    if c['host'] != '127.0.0.1' or not 1024 <= c['port'] <= 65535:
        raise SystemExit('Refusing a non-loopback or privileged endpoint')
    marker = Path(c['pg_root']) / MARKER
    if marker.read_text().strip() != c['ownership']:
        raise SystemExit('Cluster ownership marker mismatch')
    return c


def configure(args):
    if CONFIG.exists():
        raise SystemExit('Configuration already exists; inspect it, do not reset')
    pg_bin, flyway = Path(args.pg_bin).expanduser().resolve(), Path(args.flyway).expanduser().resolve()
    pg_root = Path(args.pg_root).expanduser().resolve()
    if os.geteuid() == 0:
        raise SystemExit('Run as an ordinary local lab owner')
    for name in ['initdb', 'pg_ctl', 'postgres', 'psql', 'pg_dump', 'pg_restore', 'createdb']:
        if not (pg_bin/name).is_file():
            raise SystemExit('Missing PostgreSQL program: ' + name)
    version = run([pg_bin/'postgres', '--version'], capture=True).stdout.strip()
    if '18.6' not in version:
        raise SystemExit('This profile requires PostgreSQL 18.6; found ' + version)
    if not flyway.is_file():
        raise SystemExit('Pass the full path of the unpacked official Flyway CLI')
    if pg_root.exists():
        raise SystemExit('PG root already exists; choose a new owned root, never overwrite')
    if not 1024 <= args.port <= 65535:
        raise SystemExit('Port must be an unprivileged number')
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    pg_root.mkdir(parents=True, mode=0o700)
    c = dict(pg_bin=str(pg_bin), flyway=str(flyway), pg_root=str(pg_root),
             host='127.0.0.1', port=args.port, tls=not args.no_tls,
             ownership=secrets.token_hex(24), admin=secrets.token_urlsafe(32),
             owner=secrets.token_urlsafe(32), app=secrets.token_urlsafe(32))
    private_write(pg_root/MARKER, c['ownership']+'\n')
    private_write(CONFIG, json.dumps(c, indent=2)+'\n')
    print('Configured private paths; no PostgreSQL process started')


def pg_env(c, role='owner', database='handbook'):
    env = {k:v for k,v in os.environ.items() if not k.startswith(('PG','FLYWAY_'))}
    user, password = {'admin':('lab_admin', c['admin']), 'owner':('flyway_owner', c['owner']),
                      'app':('app_local', c['app'])}[role]
    env.update(PGHOST='127.0.0.1', PGPORT=str(c['port']), PGDATABASE=database,
               PGUSER=user, PGPASSWORD=password, PGCONNECT_TIMEOUT='3',
               PGSSLMODE='verify-full' if c['tls'] else 'disable')
    if c['tls']:
        env['PGSSLROOTCERT'] = str(Path(c['pg_root'])/'tls/ca.crt')
    return env


def sql(c, text, role='owner', database='handbook', capture=False):
    if database not in ('handbook', 'handbook_restore', 'postgres'):
        raise SystemExit('Database is outside the lab contract')
    return run([Path(c['pg_bin'])/'psql','-X','-v','ON_ERROR_STOP=1','-A','-t'],
               env=pg_env(c, role, database), input=text, capture=capture)


def make_tls(c):
    tls = Path(c['pg_root'])/'tls'
    tls.mkdir(mode=0o700)
    openssl = shutil.which('openssl')
    if not openssl:
        raise SystemExit('Install/prepare OpenSSL in the personal Linux VM first')
    # Original, ephemeral personal CA; private keys never enter the repository.
    run([openssl,'req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','30',
         '-keyout',tls/'ca.key','-out',tls/'ca.crt','-subj','/CN=Handbook local lab CA'], capture=True)
    run([openssl,'req','-new','-newkey','rsa:2048','-nodes','-keyout',tls/'server.key',
         '-out',tls/'server.csr','-subj','/CN=127.0.0.1'], capture=True)
    private_write(tls/'server.ext', 'subjectAltName=IP:127.0.0.1\nextendedKeyUsage=serverAuth\n')
    run([openssl,'x509','-req','-in',tls/'server.csr','-CA',tls/'ca.crt','-CAkey',tls/'ca.key',
         '-CAcreateserial','-out',tls/'server.crt','-days','14','-sha256',
         '-extfile',tls/'server.ext'], capture=True)
    for key in tls.glob('*.key'):
        key.chmod(0o600)


def start(c):
    data, pg_root, pg_bin = Path(c['pg_root'])/'data', Path(c['pg_root']), Path(c['pg_bin'])
    if not (data/'PG_VERSION').exists():
        private_write(pg_root/'init-password', c['admin']+'\n')
        run([pg_bin/'initdb','-D',data,'-U','lab_admin','--encoding=UTF8','--locale=C',
             '--auth=scram-sha-256','--pwfile='+str(pg_root/'init-password')], capture=True)
        (pg_root/'init-password').unlink()
        if c['tls']:
            make_tls(c)
        extra = "\nlisten_addresses='127.0.0.1'\nport="+str(c['port'])+"\n"
        extra += "unix_socket_directories=''\npassword_encryption='scram-sha-256'\n"
        extra += "shared_buffers='32MB'\nmax_connections=20\nlog_lock_waits=on\ndeadlock_timeout='200ms'\n"
        if c['tls']:
            extra += "ssl=on\nssl_cert_file='../tls/server.crt'\nssl_key_file='../tls/server.key'\n"
            (data/'pg_hba.conf').write_text('hostssl all all 127.0.0.1/32 scram-sha-256\nhostnossl all all 127.0.0.1/32 reject\n')
        else:
            extra += 'ssl=off\n'
            (data/'pg_hba.conf').write_text('host all all 127.0.0.1/32 scram-sha-256\n')
        with (data/'postgresql.conf').open('a') as f:
            f.write(extra)
    status = run([pg_bin/'pg_ctl','-D',data,'status'], capture=True, check=False)
    if status.returncode == 0:
        print('Owned PostgreSQL is already running')
    else:
        run([pg_bin/'pg_ctl','-D',data,'-l',pg_root/'postgresql.log','-w','start'],capture=True)
    result = sql(c,"SELECT version(),current_user,inet_server_addr(),inet_server_port();",'admin','postgres',True)
    print(result.stdout.strip())
    if c['tls']:
        print(sql(c,'SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid();','admin','postgres',True).stdout.strip())


def bootstrap(c):
    existing = sql(c,"SELECT 1 FROM pg_database WHERE datname='handbook';",'admin','postgres',True).stdout.strip()
    if existing:
        owner = sql(c,"SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='app';",'admin','handbook',True).stdout.strip()
        if owner != 'flyway_owner':
            raise SystemExit('Existing app schema is not owned by flyway_owner; stop for inspection')
        print('Existing handbook/app ownership accepted; no role passwords changed')
        return
    # Generated passwords contain only URL-safe characters; never user-supplied SQL.
    sql(c, f"CREATE ROLE flyway_owner LOGIN PASSWORD '{c['owner']}';\n"
           "CREATE ROLE app_runtime NOLOGIN;\n"
           f"CREATE ROLE app_local LOGIN PASSWORD '{c['app']}' IN ROLE app_runtime;\n"
           "CREATE DATABASE handbook OWNER flyway_owner;", 'admin','postgres')
    sql(c,"REVOKE CREATE ON SCHEMA public FROM PUBLIC;\nCREATE SCHEMA app AUTHORIZATION flyway_owner;\nCREATE SCHEMA flyway_meta AUTHORIZATION flyway_owner;\n"
          "GRANT CONNECT ON DATABASE handbook TO app_local;\nGRANT USAGE ON SCHEMA app TO app_runtime;",'admin')
    sql(c,"ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE ALL ON TABLES FROM PUBLIC;\n"
          "ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE ALL ON SEQUENCES FROM PUBLIC;")
    print('Created handbook/app, migration owner and restricted app role')


def flyway(c, argv, database='handbook'):
    if database not in ('handbook', 'handbook_restore'):
        raise SystemExit('Flyway target is outside the owned database pair')
    if not argv:
        raise SystemExit('Supply a Flyway command, for example info')
    commands={'info','validate','migrate','repair','clean','baseline'}
    if argv[0] not in commands:
        raise SystemExit('Supply a supported command first; this wrapper is not a general CLI proxy')
    allowed={'-target','-outOfOrder','-validateOnMigrate','-ignoreMigrationPatterns',
             '-baselineVersion','-baselineDescription','-group','-mixed','-executeInTransaction',
             '-outputType','-X','-q'}
    seen=set()
    for item in argv[1:]:
        key=item.split('=',1)[0]
        if key not in allowed or key in seen:
            raise SystemExit('Refusing target/config/unknown/duplicate override: '+key)
        if key not in ('-X','-q') and '=' not in item:
            raise SystemExit('Use one -key=value argument')
        if key=='-validateOnMigrate' and item!='-validateOnMigrate=true':
            raise SystemExit('The persistent wrapper requires validation on migrate')
        seen.add(key)
    env = pg_env(c)
    env.update(FLYWAY_URL=jdbc_url(c, database), FLYWAY_USER='flyway_owner', FLYWAY_PASSWORD=c['owner'])
    return run([c['flyway'],'-configFiles='+str(ROOT/'flyway.conf'),
                '-url='+jdbc_url(c, database),'-user=flyway_owner',*argv],env=env,check=False).returncode



def restore_check(c, allow_pending):
    exists = sql(c, "SELECT 1 FROM pg_database WHERE datname='handbook_restore';",
                 'admin', 'postgres', True).stdout.strip()
    if exists != '1':
        raise SystemExit('Restore handbook_restore first; source database is not substituted')
    for command in (['info'], ['validate'] + (['-ignoreMigrationPatterns=*:pending'] if allow_pending else [])):
        code = flyway(c, command, database='handbook_restore')
        if code:
            raise SystemExit(code)


def jdbc_url(c, database='handbook'):
    options = {'sslmode':'verify-full' if c['tls'] else 'disable','ApplicationName':'handbook-flyway'}
    if c['tls']:
        options['sslrootcert'] = str(Path(c['pg_root'])/'tls/ca.crt')
    return f"jdbc:postgresql://127.0.0.1:{c['port']}/{database}?"+urllib.parse.urlencode(options)


def app_url(c):
    options = {'sslmode':'verify-full' if c['tls'] else 'disable','application_name':'handbook-notes'}
    if c['tls']:
        options['sslrootcert'] = str(Path(c['pg_root'])/'tls/ca.crt')
    return f"postgresql://app_local:{urllib.parse.quote(c['app'])}@127.0.0.1:{c['port']}/handbook?"+urllib.parse.urlencode(options)


def backfill(c, batch):
    if not 1 <= batch <= 10000:
        raise SystemExit('batch must be between 1 and 10000')
    total, started = 0, time.monotonic()
    while True:
        text = f"""SET lock_timeout='1s'; SET statement_timeout='5s';
WITH picked AS (SELECT id FROM app.notes WHERE title IS NULL
 ORDER BY id LIMIT {batch} FOR UPDATE SKIP LOCKED), changed AS (
 UPDATE app.notes n SET title=n.body FROM picked p
 WHERE n.id=p.id AND n.title IS NULL RETURNING n.id)
SELECT count(*) FROM changed;"""
        result = sql(c,text,capture=True)
        count = int(result.stdout.strip().splitlines()[-1]); total += count
        if count == 0:
            break
        time.sleep(0.02)
    missing = sql(c,'SELECT count(*) FROM app.notes WHERE title IS NULL;',capture=True).stdout.strip()
    print(json.dumps(dict(updated=total,remaining_nulls=int(missing),seconds=round(time.monotonic()-started,3))))
    if missing != '0':
        raise SystemExit('Locked or concurrently inserted rows remain; drain v1 and repeat')


def snapshot(c):
    backups = ROOT/'backups'; backups.mkdir(mode=0o700,exist_ok=True)
    dest = backups/('handbook-'+time.strftime('%Y%m%dT%H%M%S')+'.dump')
    if dest.exists():
        raise SystemExit('Backup filename already exists; do not overwrite')
    started=time.monotonic()
    run([Path(c['pg_bin'])/'pg_dump','--format=custom','--no-owner','--no-acl','--file='+str(dest)],env=pg_env(c))
    dest.chmod(0o600)
    print(json.dumps(dict(file=str(dest),bytes=dest.stat().st_size,seconds=round(time.monotonic()-started,3))))


def restore(c, filename):
    src = Path(filename).expanduser().resolve()
    if not src.is_file():
        raise SystemExit('Backup file does not exist')
    exists=sql(c,"SELECT 1 FROM pg_database WHERE datname='handbook_restore';",'admin','postgres',True).stdout.strip()
    if exists:
        raise SystemExit('handbook_restore already exists; preserve it and choose a new lab for another drill')
    run([Path(c['pg_bin'])/'createdb','--owner=flyway_owner','handbook_restore'],env=pg_env(c,'admin','postgres'))
    run([Path(c['pg_bin'])/'pg_restore','--exit-on-error','--no-owner','--no-acl',
         '--role=flyway_owner','--dbname=handbook_restore',src], env=pg_env(c,'admin','postgres'))
    # ACLs were intentionally omitted: restore only the named application objects.
    sql(c,'GRANT USAGE ON SCHEMA app TO app_runtime; GRANT SELECT,INSERT,UPDATE ON app.notes TO app_runtime; '
          'GRANT SELECT ON app.note_count TO app_runtime; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA app TO app_runtime;',
        database='handbook_restore')
    print('Restored to handbook_restore; original database was not overwritten')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    p=subs.add_parser('configure');p.add_argument('--pg-bin',required=True);p.add_argument('--flyway',required=True)
    p.add_argument('--pg-root',default=str(Path.home()/'handbook-lab/pg18'));p.add_argument('--port',type=int,default=15432)
    p.add_argument('--no-tls',action='store_true',help='Only isolated no-TLS native tests; not the main reader profile')
    for command in ['start','bootstrap','stop','snapshot','measure','app-build']:
        subs.add_parser(command)
    p=subs.add_parser('flyway');p.add_argument('argv',nargs=argparse.REMAINDER)
    p=subs.add_parser('sql');p.add_argument('--role',choices=['owner','admin','app'],default='owner')
    p.add_argument('--database',choices=['handbook','handbook_restore','postgres'],default='handbook');p.add_argument('--file',required=True)
    p=subs.add_parser('backfill');p.add_argument('--batch',type=int,default=200)
    p=subs.add_parser('restore');p.add_argument('file')
    p=subs.add_parser('restore-check');p.add_argument('--allow-pending',action='store_true',help='Explicitly allow not-yet-applied files while validating the restored point')
    p=subs.add_parser('app-run');p.add_argument('release',choices=['v1','v2','v3'])
    p=subs.add_parser('request');p.add_argument('--text')
    args=parser.parse_args()
    os.umask(0o077)
    if args.action=='configure':
        configure(args);return
    c=load()
    if args.action=='start':start(c)
    elif args.action=='bootstrap':bootstrap(c)
    elif args.action=='flyway':raise SystemExit(flyway(c,args.argv))
    elif args.action=='sql':sql(c,Path(args.file).read_text(),args.role,args.database)
    elif args.action=='backfill':backfill(c,args.batch)
    elif args.action=='snapshot':snapshot(c)
    elif args.action=='restore':restore(c,args.file)
    elif args.action=='restore-check':restore_check(c,args.allow_pending)
    elif args.action=='stop':run([Path(c['pg_bin'])/'pg_ctl','-D',Path(c['pg_root'])/'data','-m','fast','-w','stop'],capture=True)
    elif args.action=='measure':
        sql(c,(ROOT/'measure.sql').read_text(),'admin')
    elif args.action=='app-build':
        go=shutil.which('go')
        if not go:raise SystemExit('Prepare the Go toolchain before app-build')
        env=os.environ.copy();env.update(GOTOOLCHAIN='local',GOWORK='off',GOFLAGS='')
        (ROOT/'app/bin').mkdir(exist_ok=True)
        run([go,'-C',ROOT/'app','build','-mod=readonly','-o',ROOT/'app/bin/notes','.'],env=env)
    elif args.action=='app-run':
        env=os.environ.copy();env.update(APP_RELEASE=args.release,DATABASE_URL=app_url(c))
        # Replace this foreground process: Python must not kill a draining child
        # on KeyboardInterrupt. PID/process group and terminal signals stay intact.
        executable = str(ROOT/'app/bin/notes')
        os.chdir(ROOT)
        os.execve(executable, [executable], env)
    elif args.action=='request':
        data=json.dumps({'text':args.text}).encode() if args.text is not None else None
        request=urllib.request.Request('http://127.0.0.1:18080/notes',data=data,headers={'Content-Type':'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request,timeout=5) as response:
            print(response.status,response.read().decode())


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,KeyError) as error:
        raise SystemExit(str(error))
