#!/usr/bin/env python3
"""Real Flyway/PostgreSQL/Go acceptance. New private root only; no host install.

The argument root must not exist. A successful run stops its own PostgreSQL
and deletes its own new files unless --keep. Failure preserves evidence after
stopping the server. No persistent reader directory is used.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

VOLUME = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin',required=True)
    parser.add_argument('--flyway',required=True)
    parser.add_argument('--go-bin',required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=18544)
    parser.add_argument('--keep',action='store_true')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.expanduser().resolve()
    if root.exists(): raise SystemExit('Test root must not already exist')
    root.mkdir(mode=0o700,parents=True)
    lab=root/'project';shutil.copytree(VOLUME/'labs',lab,ignore=shutil.ignore_patterns('__pycache__','.private','bin','vendor'))
    logs=root/'logs';logs.mkdir(mode=0o700)
    results=[];processes=[];started=False;success=False
    env=os.environ.copy();env['PATH']=str(Path(args.go_bin).resolve())+os.pathsep+env.get('PATH','')
    def command(label,argv,expected=0,extra_env=None):
        begin=time.monotonic();r=subprocess.run([str(a) for a in argv],cwd=lab,env=extra_env or env,text=True,capture_output=True)
        (logs/(str(len(results))+'-'+label+'.txt')).write_text(r.stdout+'\n'+r.stderr)
        ok=r.returncode==expected if isinstance(expected,int) else r.returncode!=0
        results.append(dict(case=label,returncode=r.returncode,passed=ok,seconds=round(time.monotonic()-begin,4)))
        if not ok:raise AssertionError(label+': unexpected exit '+str(r.returncode)+' '+r.stdout[-1200:]+r.stderr[-1200:])
        return r
    def helper(label,*argv,expected=0):return command(label,[sys.executable,lab/'lab.py',*argv],expected)
    def check(label,value,**facts):
        results.append(dict(case=label,passed=bool(value),**facts))
        if not value:raise AssertionError(label)
    def response(text=None):
        data=json.dumps(dict(text=text)).encode() if text is not None else None
        r=urllib.request.Request('http://127.0.0.1:18080/notes',data=data,headers={'Content-Type':'application/json'})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(r,timeout=5) as out:return out.status,json.loads(out.read())
        except urllib.error.HTTPError as error:return error.code,error.read().decode()
    app=None
    try:
        helper('configure','configure','--pg-bin',args.pg_bin,'--flyway',args.flyway,'--pg-root',root/'pg','--port',args.port)
        helper('start-tls-scram','start');started=True
        helper('bootstrap','bootstrap')
        spec=importlib.util.spec_from_file_location('owned_flyway_lab',lab/'lab.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);c=m.load()
        def query(sql,role='owner',db='handbook'):
            if db not in ('handbook','handbook_restore','postgres','index_transaction_lock','baseline_case','placeholder_case'):
                raise AssertionError('Test database outside the owned fixture set')
            r=subprocess.run([str(Path(args.pg_bin)/'psql'),'-X','-v','ON_ERROR_STOP=1','-A','-t'],
                             cwd=lab,env=m.pg_env(c,role,db),input=sql,text=True,capture_output=True)
            if r.returncode:raise AssertionError('Fixture SQL failed: '+r.stderr)
            return r.stdout.strip()
        check('tls-verified',query("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();")=='t')
        notls=m.pg_env(c);notls['PGSSLMODE']='disable'
        command('plaintext-tcp-denied',[Path(args.pg_bin)/'psql','-X','-c','SELECT 1'],expected='nonzero',extra_env=notls)
        helper('info-before','flyway','info','-target=1')
        helper('standalone-validate-pending-denied','flyway','validate',expected='nonzero')
        helper('validate-pending-explicit','flyway','validate','-ignoreMigrationPatterns=*:pending')
        helper('migrate-v1','flyway','migrate','-target=1')
        check('history-schema-owner',query("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='flyway_meta';")=='flyway_owner')
        check('app-restricted',query("SELECT has_schema_privilege('app_local','app','CREATE'),has_table_privilege('app_local','flyway_meta.flyway_schema_history','SELECT');")=='f|f')
        helper('seed-1000','sql','--role','app','--file','seed.sql')
        # Compile the real Go service before invoking it.
        helper('go-build','app-build')
        def start_app(release):
            nonlocal app
            instance=secrets.token_hex(16)
            appenv=env.copy();appenv.update(APP_RELEASE=release,APP_INSTANCE=instance,DATABASE_URL=m.app_url(c))
            out=(logs/('app-'+release+'.log')).open('w')
            app=subprocess.Popen([str(lab/'app/bin/notes')],cwd=lab,env=appenv,stdout=out,stderr=out);processes.append(app)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(60):
                if app.poll() is not None:raise AssertionError('application exited early')
                try:
                    with opener.open('http://127.0.0.1:18080/healthz',timeout=.2) as r:
                        if r.read().decode().strip()==release and r.headers.get('X-Handbook-Instance')==instance:return
                except OSError:time.sleep(.05)
            raise AssertionError('app readiness timeout')
        def stop_app():
            nonlocal app
            if app and app.poll() is None:app.terminate();app.wait(timeout=8)
            app=None
        start_app('v1');status,value=response('native-v1');check('go-v1-write',status==201,status=status);stop_app()
        info1=helper('info-target2','flyway','info','-target=2').stdout
        infoall=helper('info-default','flyway','info').stdout
        check('target-changes-pending', 'Above Target' in info1 and 'Pending' in infoall)
        helper('migrate-v2','flyway','migrate','-target=2')
        before=query('SELECT count(*) FROM flyway_meta.flyway_schema_history;')
        helper('idempotent-migrate-v2','flyway','migrate','-target=2')
        check('no-duplicate-history',before==query('SELECT count(*) FROM flyway_meta.flyway_schema_history;'))
        v1=lab/'migrations/V1__create_notes.sql';original=v1.read_bytes();v1.write_bytes(original+b'\n-- edited after application\n')
        mismatch=helper('checksum-mismatch','flyway','validate','-ignoreMigrationPatterns=*:pending',expected='nonzero')
        check('checksum-error-specific','checksum mismatch' in (mismatch.stdout+mismatch.stderr).lower())
        v1.write_bytes(original);helper('checksum-restored','flyway','validate','-ignoreMigrationPatterns=*:pending')
        start_app('v2');status,value=response();check('v2-reads-old-rows',status==200 and len(value)==100)
        status,value=response('native-v2');check('v2-dual-write',status==201)
        stop_app()
        wal0=query('SELECT pg_current_wal_lsn();');size0=int(query("SELECT pg_total_relation_size('app.notes');"))
        fill=helper('batch-backfill','backfill','--batch','200')
        wal1=query('SELECT pg_current_wal_lsn();');size1=int(query("SELECT pg_total_relation_size('app.notes');"))
        walbytes=int(query(f"SELECT pg_wal_lsn_diff('{wal1}','{wal0}');"))
        check('backfill-invariant',query('SELECT count(*) FROM app.notes WHERE title IS NULL OR title IS DISTINCT FROM body;')=='0',wal_bytes=walbytes,bytes_before=size0,bytes_after=size1,summary=json.loads(fill.stdout))
        # An application transaction holds a relation lock. Flyway's advisory lock
        # is available; the ALTER is rejected by PostgreSQL lock_timeout.
        hold=subprocess.Popen([str(Path(args.pg_bin)/'psql'),'-X','-v','ON_ERROR_STOP=1','-c','BEGIN; SELECT 1 FROM app.notes LIMIT 1; SELECT pg_sleep(4); COMMIT;'],
                              cwd=lab,env=m.pg_env(c,'app'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        processes.append(hold);time.sleep(.25)
        lockerror=helper('ddl-lock-timeout','flyway','migrate','-target=3',expected='nonzero')
        check('ddl-timeout-identified','55P03' in lockerror.stdout+lockerror.stderr)
        hold.wait(timeout=8)
        helper('migrate-v3','flyway','migrate','-target=3')
        start_app('v1');status,value=response('obsolete-v1');check('v1-denied-after-v3',status==503);stop_app()
        helper('migrate-v4','flyway','migrate','-target=4')
        check('constraint-validated',query("SELECT convalidated FROM pg_constraint WHERE conname='notes_title_present';")=='t')
        # Same V4 starting point: transaction-level coordination vs session lock.
        query('CREATE DATABASE index_transaction_lock TEMPLATE handbook OWNER flyway_owner;','admin','postgres')
        fenv=m.pg_env(c);fenv.update(FLYWAY_USER='flyway_owner',FLYWAY_PASSWORD=c['owner'],FLYWAY_URL=m.jdbc_url(c,'index_transaction_lock'))
        bad=command('concurrent-index-transaction-lock',[args.flyway,'-configFiles='+str(lab/'flyway.conf'),'-postgresql.transactional.lock=true','migrate','-target=5'],expected='nonzero',extra_env=fenv)
        check('index-default-lock-timeout','57014' in bad.stdout+bad.stderr or '55P03' in bad.stdout+bad.stderr)
        helper('concurrent-index-session-lock','flyway','migrate','-target=5')
        check('index-valid',query("SELECT indisready,indisvalid FROM pg_index WHERE indexrelid='app.notes_title_idx'::regclass;")=='t|t')
        # Snapshot with both schema and history; actual restore on another database.
        frozen=query('SELECT count(*) FROM app.notes;')
        fingerprint=query("SELECT md5(string_agg(row_to_json(n)::text,E'\\n' ORDER BY id)) FROM app.notes n;")
        snap=json.loads(helper('snapshot','snapshot').stdout)
        helper('restore-other-db','restore',snap['file'])
        check('restore-count-history',query('SELECT count(*) FROM app.notes;',db='handbook_restore')==frozen and query('SELECT count(*) FROM flyway_meta.flyway_schema_history;',db='handbook_restore')==query('SELECT count(*) FROM flyway_meta.flyway_schema_history;'))
        check('restore-values-fingerprint',query("SELECT md5(string_agg(row_to_json(n)::text,E'\\n' ORDER BY id)) FROM app.notes n;",db='handbook_restore')==fingerprint)
        helper('restore-app-rights','sql','--database','handbook_restore','--role','app','--file','check-restore-app.sql')
        start_app('v3');status,value=response('after-snapshot');check('v3-write-pre-contract',status==201);stop_app()
        check('post-snapshot-rows-absent',int(query('SELECT count(*) FROM app.notes;'))==int(frozen)+1 and query('SELECT count(*) FROM app.notes;',db='handbook_restore')==frozen)
        helper('migrate-contract-v6','flyway','migrate','-target=6')
        start_app('v3');status,value=response('after-contract');check('v3-after-contract',status==201);stop_app()
        start_app('v2');status,value=response();check('v2-rollback-incompatible',status==503);stop_app()
        helper('target-not-rollback','flyway','migrate','-target=2')
        check('body-not-recreated',query("SELECT count(*) FROM information_schema.columns WHERE table_schema='app' AND table_name='notes' AND column_name='body';")=='0')
        # Real transactional and nontransactional failures at the same version.
        tx=lab/'migrations/V7__transactional_failure.sql';shutil.copy2(lab/'experiments'/tx.name,tx)
        helper('transactional-failure','flyway','migrate',expected='nonzero')
        check('transaction-rolled-back',query("SELECT to_regclass('app.failure_probe') IS NULL;")=='t' and query("SELECT count(*) FROM flyway_meta.flyway_schema_history WHERE version='7';")=='0')
        tx.unlink();ntx=lab/'migrations/V7__nontransactional_failure.sql';shutil.copy2(lab/'experiments'/ntx.name,ntx);shutil.copy2(lab/'experiments'/(ntx.name+'.conf'),Path(str(ntx)+'.conf'))
        helper('nontransactional-failure','flyway','migrate',expected='nonzero')
        check('partial-object-remains',query('SELECT count(*) FROM app.partial_probe;')=='1' and query("SELECT success FROM flyway_meta.flyway_schema_history WHERE version='7';")=='f')
        helper('repair-history','flyway','repair')
        check('repair-does-not-clean-data',query('SELECT count(*) FROM app.partial_probe;')=='1' and query("SELECT count(*) FROM flyway_meta.flyway_schema_history WHERE version='7';")=='0')
        query('DROP TABLE app.partial_probe;');ntx.unlink();Path(str(ntx)+'.conf').unlink()
        slow=lab/'migrations/V7__slow_deploy.sql';shutil.copy2(lab/'experiments'/slow.name,slow)
        cmd=[sys.executable,str(lab/'lab.py'),'flyway','migrate']
        out1=(logs/'parallel-one.txt').open('w');out2=(logs/'parallel-two.txt').open('w')
        a=subprocess.Popen(cmd,cwd=lab,env=env,stdout=out1,stderr=out1);processes.append(a)
        saw_lock=False
        for _ in range(100):
            if query("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND granted;")!='0':saw_lock=True;break
            time.sleep(.03)
        b=subprocess.Popen(cmd,cwd=lab,env=env,stdout=out2,stderr=out2);processes.append(b)
        ac,bc=a.wait(timeout=20),b.wait(timeout=20);out1.close();out2.close()
        check('parallel-deploy-serialized',saw_lock and ac==0 and bc==0 and query("SELECT count(*) FROM flyway_meta.flyway_schema_history WHERE version='7' AND success;")=='1',first_exit=ac,second_exit=bc)
        late=lab/'migrations/V1_5__late_note.sql';shutil.copy2(lab/'experiments'/late.name,late)
        ignored=helper('late-default-info','flyway','info').stdout
        check('late-ignored-default','Ignored' in ignored)
        helper('late-default-validation','flyway','validate',expected='nonzero')
        helper('late-out-of-order','flyway','migrate','-outOfOrder=true')
        check('late-history-rank',query("SELECT installed_rank>(SELECT installed_rank FROM flyway_meta.flyway_schema_history WHERE version='7') FROM flyway_meta.flyway_schema_history WHERE version='1.5';")=='t')
        helper('clean-disabled','flyway','clean',expected='nonzero')
        check('clean-data-preserved',int(query('SELECT count(*) FROM app.notes;'))>1000)
        # Offline execution with already prepared binaries and module cache.
        offline=env.copy();offline.update(GOPROXY='off',GOSUMDB='off',GOTOOLCHAIN='local',GOWORK='off')
        command('offline-go-build',[sys.executable,lab/'lab.py','app-build'],extra_env=offline)
        helper('offline-info','flyway','info')
        success=True
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        if started:
            try:helper('stop-owned-server','stop')
            except Exception as error:results.append(dict(case='stop-error',passed=False,error=str(error)))
        report=dict(kind='native-real',flyway='13.12.0 OSS',postgresql='18.6 TLS verify-full SCRAM',
                    successful=success,results=results,limitations=['No clean-VM installation test','No crash exactly at commit','No multi-host failure/HA','Offline used prepared cache; network was not firewalled'])
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(successful=success,passed=sum(r.get('passed',False) for r in results),cases=len(results),report=str(args.report)),ensure_ascii=False))
        if success and not args.keep:shutil.rmtree(root)


if __name__=='__main__':main()
