#!/usr/bin/env python3
"""Independent real CLI/baseline/placeholder edge cases; no Go/HTTP listener.

Only a new private root/own loopback PG cluster. Does not repeat the full
application lifecycle from native.py. Inputs are trusted installed runtimes.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

VOLUME=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin',required=True);parser.add_argument('--flyway',required=True)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--port',type=int,default=18545)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--keep',action='store_true')
    args=parser.parse_args();root=args.root.expanduser().resolve()
    if root.exists():raise SystemExit('Choose a new private root')
    root.mkdir(parents=True,mode=0o700);lab=root/'lab copy with spaces'
    shutil.copytree(VOLUME/'labs',lab,ignore=shutil.ignore_patterns('__pycache__','.private','bin','vendor'))
    logs=root/'logs';logs.mkdir(mode=0o700);results=[];started=False;success=False
    def cmd(label,argv,*,env=None,fail=False,input=None):
        r=subprocess.run([str(x) for x in argv],cwd=lab,env=env,input=input,text=True,capture_output=True)
        (logs/(str(len(results))+'-'+label+'.txt')).write_text(r.stdout+r.stderr)
        ok=r.returncode!=0 if fail else r.returncode==0
        results.append(dict(case=label,code=r.returncode,passed=ok))
        if not ok:raise AssertionError(label+': '+r.stdout[-1200:]+r.stderr[-1200:])
        return r
    def helper(label,*argv,fail=False):return cmd(label,[sys.executable,lab/'lab.py',*argv],fail=fail)
    def check(label,condition):
        results.append(dict(case=label,passed=bool(condition)))
        if not condition:raise AssertionError(label)
    try:
        helper('configure','configure','--pg-bin',args.pg_bin,'--flyway',args.flyway,'--pg-root',root/'pg','--port',args.port)
        helper('start','start');started=True;helper('bootstrap','bootstrap')
        spec=importlib.util.spec_from_file_location('edge_lab',lab/'lab.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);c=m.load()
        def query(text,db='handbook',role='owner'):
            if db not in ['handbook','postgres','placeholder_case','parser_case','baseline_migration_case']:raise AssertionError('Outside fixture')
            return cmd('fixture-sql',[Path(args.pg_bin)/'psql','-X','-v','ON_ERROR_STOP=1','-A','-t'],env=m.pg_env(c,role,db),input=text).stdout.strip()
        for label,argv in [('version-word',['version']),('version-short',['-v']),('version-long',['--version']),
                           ('help-short',['-h']),('help-long',['--help']),('help-question',['-?']),('help-command',['help','migrate'])]:
            cmd('cli-'+label,[args.flyway,*argv])
        helper('reject-wrapper-url','flyway','info','-url=jdbc:postgresql://127.0.0.1:1/other',fail=True)
        helper('reject-wrapper-config','flyway','info','-configFiles=missing.conf',fail=True)
        helper('reject-wrapper-disable-validation','flyway','migrate','-validateOnMigrate=false',fail=True)
        helper('reject-wrapper-clean-disable','flyway','clean','-cleanDisabled=false',fail=True)
        helper('reject-wrapper-duplicate-target','flyway','info','-target=1','-target=2',fail=True)
        direct=m.pg_env(c);direct.update(FLYWAY_USER='flyway_owner',FLYWAY_PASSWORD=c['owner'],FLYWAY_URL=m.jdbc_url(c))
        config=lab/'flyway.conf'
        prefix=cmd('target-prefix-and-config-space',[args.flyway,'-configFiles='+str(config),'-outputType=json','-target=2','info'],env=direct)
        suffix=cmd('target-suffix-and-config-space',[args.flyway,'-configFiles='+str(config),'-outputType=json','info','-target=2'],env=direct)
        check('prefix-suffix-same-result',json.loads(prefix.stdout)['migrations']==json.loads(suffix.stdout)['migrations'])
        cmd('reject-posix-double-dash',[args.flyway,'--','-v'],fail=True)
        cmd('reject-space-option-value',[args.flyway,'-configFiles='+str(config),'info','-target','2'],env=direct,fail=True)
        # handbook is deliberately empty of application objects at baseline.
        cmd('baseline-empty-app',[args.flyway,'-configFiles='+str(config),'baseline','-baselineVersion=1','-baselineDescription=Принятая схема ноября'],env=direct)
        check('baseline-did-not-execute-v1',query("SELECT to_regclass('app.notes') IS NULL;")=='t' and query('SELECT type FROM flyway_meta.flyway_schema_history;')=='BASELINE')
        cmd('baseline-did-not-create-schema',[args.flyway,'-configFiles='+str(config),'migrate','-target=2'],env=direct,fail=True)
        # Dedicated resolver fixture, not a rewrite of the reader migration set.
        query('CREATE DATABASE placeholder_case OWNER flyway_owner;','postgres','admin')
        query('CREATE SCHEMA app AUTHORIZATION flyway_owner; CREATE SCHEMA flyway_meta AUTHORIZATION flyway_owner;','placeholder_case')
        ph=root/'placeholder migrations';ph.mkdir()
        v1=ph/'V1__placeholder.sql'
        v1.write_text("CREATE TABLE app.placeholder_probe(v text); INSERT INTO app.placeholder_probe VALUES ('${word}');\n")
        (ph/'R__placeholder_view.sql').write_text("CREATE OR REPLACE VIEW app.placeholder_value AS SELECT '${word}'::text AS v;\n")
        p_env=direct.copy();p_env['FLYWAY_URL']=m.jdbc_url(c,'placeholder_case')
        def phcmd(label,word,command='migrate',fail=False):
            return cmd(label,[args.flyway,'-configFiles='+str(config),'-locations=filesystem:'+str(ph),'-placeholders.word='+word,command],env=p_env,fail=fail)
        phcmd('placeholder-one','one')
        original_crc=query("SELECT checksum FROM flyway_meta.flyway_schema_history WHERE version='1';",'placeholder_case')
        phcmd('placeholder-two','two')
        check('versioned-placeholder-not-reexecuted',query('SELECT v FROM app.placeholder_probe;','placeholder_case')=='one' and query("SELECT checksum FROM flyway_meta.flyway_schema_history WHERE version='1';",'placeholder_case')==original_crc)
        check('repeatable-placeholder-reexecuted',query('SELECT v FROM app.placeholder_value;','placeholder_case')=='two' and query('SELECT count(*) FROM flyway_meta.flyway_schema_history WHERE version IS NULL;','placeholder_case')=='2')
        original=v1.read_bytes();v1.write_bytes(b'\xef\xbb\xbf'+original.replace(b'\n',b'\r\n'))
        phcmd('crc-bom-crlf-normalized','two','validate')
        v1.write_bytes(original+b'-- changed comment\n')
        mismatch=phcmd('crc-comment-changed','two','validate',True)
        check('checksum-specific-error','checksum mismatch' in (mismatch.stdout+mismatch.stderr).lower())
        v1.write_bytes(original);phcmd('crc-restore','two','validate')
        query('CREATE DATABASE parser_case OWNER flyway_owner;','postgres','admin')
        query('CREATE SCHEMA app AUTHORIZATION flyway_owner; CREATE SCHEMA flyway_meta AUTHORIZATION flyway_owner;','parser_case')
        parsing=root/'parser-fixture';parsing.mkdir()
        good=lab/'experiments/parser/V1__dollar_quoted.sql';shutil.copy2(good,parsing/good.name)
        parser_env=direct.copy();parser_env['FLYWAY_URL']=m.jdbc_url(c,'parser_case')
        def parsercmd(label,fail=False):
            return cmd(label,[args.flyway,'-configFiles='+str(config),'-locations=filesystem:'+str(parsing),'-placeholders.word=parsed','migrate'],env=parser_env,fail=fail)
        parsercmd('postgresql-dollar-quote-statements')
        check('semicolon-and-placeholder-result',query('SELECT message FROM app.parser_probe;','parser_case')=='semicolon; parsed' and query("SELECT app.parser_echo('argument');",'parser_case')=='argument;parsed')
        psql=lab/'experiments/parser/V2__psql_meta.sql';shutil.copy2(psql,parsing/psql.name)
        badpsql=parsercmd('psql-meta-not-jdbc',True)
        check('psql-meta-server-syntax-error','42601' in badpsql.stdout+badpsql.stderr and query('SELECT count(*) FROM app.parser_probe;','parser_case')=='1')
        (parsing/psql.name).unlink()
        unbound=lab/'experiments/parser/V2__unbound_parameter.sql';shutil.copy2(unbound,parsing/unbound.name)
        badparam=parsercmd('jdbc-raw-sql-no-bound-parameter',True)
        check('unbound-parameter-specific-error','08P01' in badparam.stdout+badparam.stderr and 'supplies 0 parameters' in badparam.stdout+badparam.stderr and query('SELECT count(*) FROM app.parser_probe;','parser_case')=='1')
        query('CREATE DATABASE baseline_migration_case OWNER flyway_owner;','postgres','admin')
        query('CREATE SCHEMA app AUTHORIZATION flyway_owner; CREATE SCHEMA flyway_meta AUTHORIZATION flyway_owner;','baseline_migration_case')
        b_env=direct.copy();b_env['FLYWAY_URL']=m.jdbc_url(c,'baseline_migration_case')
        cmd('baseline-migration-executes-sql',[args.flyway,'-configFiles='+str(config),'-locations=filesystem:'+str(lab/'experiments/baseline'),'migrate'],env=b_env)
        check('baseline-migration-builds-new-state',query("SELECT count(*) FROM information_schema.columns WHERE table_schema='app' AND table_name='cumulative';",'baseline_migration_case')=='2' and query("SELECT string_agg(script,',' ORDER BY installed_rank) FROM flyway_meta.flyway_schema_history;",'baseline_migration_case')=='B2__cumulative_state.sql,V3__later_comment.sql')
        success=True
    finally:
        if started:
            try:helper('stop-owned','stop')
            except BaseException as error:results.append(dict(case='stop-owned',passed=False,error=str(error)))
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(dict(kind='real-native-edge-cases',successful=success,results=results),ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(successful=success,passed=sum(x.get('passed',False) for x in results),cases=len(results),report=str(args.report)),ensure_ascii=False))
        if success and not args.keep:shutil.rmtree(root)


if __name__=='__main__':main()
