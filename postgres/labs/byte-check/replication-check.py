#!/usr/bin/env python3
"""Два собственных кластера: физическая реплика и remote_apply.

По умолчанию выводит справку. --run требует PostgreSQL 18 и соседний
postgres-lab.py. Только временные данные и Unix-сокеты, TCP отключён.
Системные службы и существующие базы не используются.
"""
from pathlib import Path
import argparse,contextlib,importlib.util,json,time,subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true')
    p.add_argument('--pg-bin',type=Path)
    p.add_argument('--harness',type=Path,default=Path(__file__).resolve().parent.parent/'postgres-lab.py')
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    if not a.run:p.print_help();return
    if a.pg_bin is None:p.error('Нужен --pg-bin с программами PostgreSQL 18')
    version=subprocess.check_output([str(a.pg_bin/'postgres'),'--version'],text=True)
    if ' 18.' not in version:p.error('Этот сценарий проверен для PostgreSQL 18')
    spec=importlib.util.spec_from_file_location('pgbook_harness',a.harness)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    lab=mod.Lab(a.pg_bin)
    evidence={}
    def until(query,predicate,**kwargs):
        deadline=time.monotonic()+12
        while True:
            value=lab.sql(query,**kwargs)
            if predicate(value):return value
            if time.monotonic()>deadline:raise TimeoutError((query,value))
            time.sleep(.05)
    try:
        lab.init()
        lab.sql('CREATE TABLE book.replica_probe(id int PRIMARY KEY,value text); INSERT INTO book.replica_probe VALUES(1,\'before basebackup\');')
        standby=lab.root/'standby';sock=lab.root/'standby_socket';sock.mkdir(mode=0o700)
        lab.command('pg_basebackup','--checkpoint=fast','-D',standby,'-R','-X','stream','-C','-S','book_standby',
                    '-h',lab.socket,'-p','55432','-U','book_admin',timeout=60)
        with (standby/'postgresql.conf').open('a') as f:
            f.write("\nport=55434\nunix_socket_directories='"+str(sock)+"'\narchive_mode=off\nhot_standby=on\n")
        with (standby/'postgresql.auto.conf').open('a') as f:
            f.write("\nprimary_conninfo='host="+str(lab.socket)+" port=55432 user=book_admin application_name=book_standby'\n")
        lab.start(standby,lab.root/'standby.log')
        endpoint=dict(socket=sock,port=55434)
        assert lab.sql('SHOW listen_addresses;',**endpoint)==''
        assert lab.sql('SELECT pg_is_in_recovery();',**endpoint)=='t'
        until("SELECT state FROM pg_stat_replication WHERE application_name='book_standby';",lambda s:s=='streaming')
        lab.sql("INSERT INTO book.replica_probe VALUES(2,'after basebackup');")
        evidence['asynchronous_data']=until('SELECT id,value FROM book.replica_probe ORDER BY id;',lambda s:'after basebackup' in s,**endpoint)
        evidence['slot']=lab.sql("SELECT slot_name,slot_type,active,restart_lsn IS NOT NULL FROM pg_replication_slots WHERE slot_name='book_standby';")
        lab.sql("ALTER SYSTEM SET synchronous_standby_names='FIRST 1 (book_standby)';")
        lab.sql('SELECT pg_reload_conf();')
        evidence['synchronous_state']=until("SELECT state,sync_state FROM pg_stat_replication WHERE application_name='book_standby';",lambda s:s=='streaming\tsync')
        lab.sql("SET statement_timeout='8s'; SET synchronous_commit='remote_apply'; INSERT INTO book.replica_probe VALUES(3,'applied before reply');")
        evidence['immediate_read_after_remote_apply']=lab.sql('SELECT value FROM book.replica_probe WHERE id=3;',**endpoint)
        assert evidence['immediate_read_after_remote_apply']=='applied before reply'
        evidence['standby_positions']=lab.sql('SELECT pg_last_wal_receive_lsn(),pg_last_wal_replay_lsn();',**endpoint)
        evidence['primary_positions']=lab.sql("SELECT sent_lsn,write_lsn,flush_lsn,replay_lsn FROM pg_stat_replication WHERE application_name='book_standby';")
        evidence['write_on_standby_error']=lab.sql("INSERT INTO book.replica_probe VALUES(4,'forbidden');",expected_error='25006',**endpoint)
        evidence['status']='PASS'
        evidence['tcp_listeners']=False
        evidence['version']=lab.sql('SELECT version();')
        if a.report:a.report.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(evidence,ensure_ascii=False,indent=2))
    finally:
        with contextlib.suppress(Exception):
            lab.sql('ALTER SYSTEM RESET synchronous_standby_names;')
            lab.sql('SELECT pg_reload_conf();')
        lab.cleanup()

if __name__=='__main__':main()
