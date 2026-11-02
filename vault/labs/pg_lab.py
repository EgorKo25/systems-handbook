#!/usr/bin/env python3
"""Own persistent PostgreSQL 18.6/TLS contract and real Vault database-plugin test."""
import argparse, json, os, pathlib, secrets, select, socket, subprocess, sys, time
import lab
HERE=pathlib.Path(__file__).resolve().parent

def run(args,env=None,stdin=None,ok=True):
    r=subprocess.run(list(map(str,args)),input=stdin,text=True,env=env,capture_output=True,timeout=45)
    if ok and r.returncode: raise RuntimeError(f'{pathlib.Path(args[0]).name} failed; credentials/output withheld')
    return r

def cfg(root):return json.loads((root/'pg-stand.json').read_text())
def env(root,role='lab_admin',db='handbook',passfile='pgpass'):
    c=cfg(root); e={k:v for k,v in os.environ.items() if not k.startswith('PG')}
    e.update(PGHOST='127.0.0.1',PGPORT=str(c['port']),PGUSER=role,PGDATABASE=db,PGPASSFILE=str(root/'private'/passfile),PGSSLMODE='verify-full',PGSSLROOTCERT=str(root/'tls/ca.crt'),PGCONNECT_TIMEOUT='4');return e

def sql(root,text,role='lab_admin',db='handbook',ok=True):
    return run([pathlib.Path(cfg(root)['bin'])/'psql','-X','-qAt','-v','ON_ERROR_STOP=1'],env(root,role,db),text,ok)

def prepare(root,pgbin,port):
    if (root/'data').exists():raise RuntimeError('PGDATA exists; no implicit initialization/reset')
    if root in (pathlib.Path('/'),pathlib.Path.home()):raise RuntimeError('dedicated root required')
    if run([pgbin/'postgres','--version']).stdout.strip()!='postgres (PostgreSQL) 18.6':raise RuntimeError('PostgreSQL 18.6 required')
    if '--with-ssl=openssl' not in run([pgbin/'pg_config','--configure']).stdout:raise RuntimeError('OpenSSL PG build required')
    if os.geteuid()==0:raise RuntimeError('ordinary owner required')
    if not 1024<=port<=65535:raise RuntimeError('unprivileged port required')
    with socket.socket() as s:s.bind(('127.0.0.1',port))
    root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
    for name in ('tls','private','logs','sock'): (root/name).mkdir(exist_ok=True,mode=0o700)
    passwords={name:secrets.token_hex(24) for name in ('lab_admin','flyway_owner','vault_bootstrap')}
    lab.save(root/'private/passwords.json',passwords);lab.save(root/'private/init-password',passwords['lab_admin'])
    lab.save(root/'pg-stand.json',dict(bin=str(pgbin),port=port))
    run([pgbin/'initdb','-D',root/'data','-U','lab_admin','--encoding=UTF8','--locale=C','--auth-local=scram-sha-256','--auth-host=scram-sha-256','--pwfile='+str(root/'private/init-password')])
    def openssl(args):run(['openssl',*args])
    openssl(['req','-x509','-newkey','rsa:2048','-nodes','-days','30','-keyout',root/'tls/ca.key','-out',root/'tls/ca.crt','-subj','/CN=Handbook PG CA','-addext','basicConstraints=critical,CA:TRUE'])
    openssl(['req','-newkey','rsa:2048','-nodes','-keyout',root/'tls/server.key','-out',root/'tls/server.csr','-subj','/CN=localhost'])
    lab.save(root/'tls/server.ext','subjectAltName=IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\n')
    openssl(['x509','-req','-in',root/'tls/server.csr','-CA',root/'tls/ca.crt','-CAkey',root/'tls/ca.key','-CAcreateserial','-days','14','-out',root/'tls/server.crt','-extfile',root/'tls/server.ext'])
    with (root/'data/postgresql.conf').open('a') as f:f.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\nunix_socket_directories=''\nssl=on\nssl_cert_file='{root}/tls/server.crt'\nssl_key_file='{root}/tls/server.key'\npassword_encryption='scram-sha-256'\nshared_buffers='32MB'\nmax_connections=20\nlog_statement='none'\n")
    lab.save(root/'data/pg_hba.conf','local all all scram-sha-256\nhostssl all all 127.0.0.1/32 scram-sha-256\nhostnossl all all 127.0.0.1/32 reject\n')
    lab.save(root/'private/pgpass',''.join(f'127.0.0.1:{port}:*:{name}:{password}\n' for name,password in passwords.items()))
    print('PG18.6 private TLS/SCRAM stand prepared; no server started')

def start(root):
    b=pathlib.Path(cfg(root)['bin']);run([b/'pg_ctl','-D',root/'data','-l',root/'logs/server.log','-w','start']);print('Owned PG started')

def bootstrap(root):
    if (root/'bootstrap-complete').exists():raise RuntimeError('bootstrap already applied; inspect rather than recreate')
    pw=json.loads((root/'private/passwords.json').read_text())
    sql(root,'CREATE DATABASE handbook;',db='postgres')
    sql(root,(HERE/'sql/bootstrap.sql').read_text())
    sql(root,'\n'.join(f"ALTER ROLE {name} PASSWORD '{password}';" for name,password in pw.items()))
    assert sql(root,'SELECT message FROM app.vault_probe;',role='vault_bootstrap',ok=False).returncode!=0
    lab.save(root/'bootstrap-complete','PG roles, schema and ACL prepared\n');print('PG contract prepared; plugin role cannot SELECT application data')

def check(root,vault):
    b=pathlib.Path(cfg(root)['bin']);port=cfg(root)['port'];checks=[]
    def passed(name):checks.append(name);print('PASS',name,flush=True)
    assert sql(root,'SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();').stdout.strip()=='t';passed('PostgreSQL TLS verify-full / SCRAM')
    mounts=lab.cli(vault,['secrets','list','-format=json'],json_output=True)
    if 'database/' not in mounts:lab.cli(vault,['secrets','enable','database'])
    pw=json.loads((root/'private/passwords.json').read_text())['vault_bootstrap']
    connection=dict(plugin_name='postgresql-database-plugin',allowed_roles=['handbook-runtime'],connection_url=f'postgresql://{{{{username}}}}:{{{{password}}}}@127.0.0.1:{port}/handbook?sslmode=verify-full&sslrootcert={root}/tls/ca.crt',username='vault_bootstrap',password=pw)
    lab.save(root/'private/database-config.json',connection)
    lab.cli(vault,['write','database/config/handbook','@'+str(root/'private/database-config.json')]);passed('Vault builtin PostgreSQL plugin accepts verified TLS connection')
    lab.cli(vault,['write','-f','database/rotate-root/handbook'])
    assert sql(root,'SELECT 1;',role='vault_bootstrap',ok=False).returncode!=0;passed('plugin bootstrap password rotated; original private password no longer logs in')
    role=dict(db_name='handbook',creation_statements=[(HERE/'sql/creation.sql').read_text()],revocation_statements=[(HERE/'sql/revocation.sql').read_text()],default_ttl='15s',max_ttl='30s')
    lab.save(root/'private/database-role.json',role);lab.cli(vault,['write','database/roles/handbook-runtime','@'+str(root/'private/database-role.json')])
    credential=lab.cli(vault,['read','-format=json','database/creds/handbook-runtime'],json_output=True);lab.save(root/'private/credential.json',credential)
    data=credential['data'];user=data['username'];password=data['password']
    lab.save(root/'private/dynamic.pgpass',f'127.0.0.1:{port}:handbook:{user}:{password}\n')
    e=env(root,user,passfile='dynamic.pgpass')
    def dsql(text,ok=True):return run([b/'psql','-X','-qAt','-v','ON_ERROR_STOP=1'],e,text,ok)
    assert dsql('SELECT message FROM app.vault_probe;').stdout.strip()=='saved application data';passed('dynamic LOGIN role reads allowed application data')
    assert dsql('CREATE TABLE app.forbidden(id integer);',False).returncode!=0
    assert dsql('SELECT * FROM flyway_meta.vault_acl_probe;',False).returncode!=0;passed('dynamic role denied application DDL and flyway_meta')
    session=subprocess.Popen([str(b/'psql'),'-X','-qAt','-v','ON_ERROR_STOP=1'],env=e,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    try:
        session.stdin.write("SELECT 'session-ready';\n");session.stdin.flush()
        if not select.select([session.stdout],[],[],5)[0] or session.stdout.readline().strip()!='session-ready':raise RuntimeError('existing session not ready')
        code,r=lab.request(vault,'sys/leases/renew',{'lease_id':credential['lease_id'],'increment':10},lab.operator(vault));assert code==200;passed('dynamic lease renewed before expiry')
        code,_=lab.request(vault,'sys/leases/revoke',{'lease_id':credential['lease_id']},lab.operator(vault));assert code==204
        assert dsql('SELECT 1;',False).returncode!=0;passed('lease revoke drops role and rejects NEW login')
        session.stdin.write('SELECT 1;\n');session.stdin.flush()
        if not select.select([session.stdout],[],[],5)[0]:raise RuntimeError('existing session query timed out')
        assert session.stdout.readline().strip()=='1';passed('already-open session still executes SELECT 1 after role revoke/drop')
        session.stdin.write('SELECT message FROM app.vault_probe;\n');session.stdin.flush();session.stdin.close()
        session.wait(timeout=5);assert session.returncode!=0;passed('already-open session loses app_runtime table privileges')
    finally:
        if session.poll() is None:session.terminate();session.wait(timeout=5)
    # Do not grant pg_signal_backend or superuser to the plugin merely to hide this limitation.
    # TTL expiration is a separate issuance with a shorter role default.
    role['default_ttl']='3s';lab.save(root/'private/database-role-short.json',role);lab.cli(vault,['write','database/roles/handbook-runtime','@'+str(root/'private/database-role-short.json')])
    short=lab.cli(vault,['read','-format=json','database/creds/handbook-runtime'],json_output=True)
    lab.save(root/'private/short.pgpass',f"127.0.0.1:{port}:handbook:{short['data']['username']}:{short['data']['password']}\n")
    e2=env(root,short['data']['username'],passfile='short.pgpass')
    assert run([b/'psql','-X','-qAt','-c','SELECT 1'],e2).stdout.strip()=='1'
    time.sleep(5)
    assert run([b/'psql','-X','-qAt','-c','SELECT 1'],e2,ok=False).returncode!=0;passed('short lease expiry rejects subsequent login')
    report=dict(kind='native Vault1.21.4 database plugin + PostgreSQL18.6/OpenSSL, loopback',checks=checks,count=len(checks),existing_session_terminated=False,external_pg_backup_restored=False)
    lab.save(root/'checks.json',report);print(json.dumps(report,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=pathlib.Path,required=True);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('--pg-bin',type=pathlib.Path,required=True);a.add_argument('--port',type=int,default=15432)
    for name in ('start','bootstrap','stop'):s.add_parser(name)
    a=s.add_parser('check');a.add_argument('--vault-root',type=pathlib.Path,required=True)
    a=p.parse_args();root=a.root.expanduser().resolve()
    if a.action=='prepare':prepare(root,a.pg_bin.expanduser().resolve(),a.port)
    elif a.action=='start':start(root)
    elif a.action=='bootstrap':bootstrap(root)
    elif a.action=='check':check(root,a.vault_root.expanduser().resolve())
    elif a.action=='stop':run([pathlib.Path(cfg(root)['bin'])/'pg_ctl','-D',root/'data','-m','fast','-w','stop']);print('Owned PG stopped; persistent state retained')
if __name__=='__main__':
    try:main()
    except Exception as e:print(f'STOP: {type(e).__name__}: {e}',file=sys.stderr);sys.exit(1)
