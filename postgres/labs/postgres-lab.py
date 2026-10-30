#!/usr/bin/env python3
"""16 isolated PostgreSQL experiments; no system service or existing database is used.

Default: show help. Explicit run:
  python3 postgres-lab.py --run --pg-bin /absolute/path/to/postgresql/bin
Needs PostgreSQL 18 tools and optional contrib extensions listed in README.
The cluster is created under /tmp, listens only on its own Unix socket, and is
stopped and deleted on exit unless --keep is explicitly requested.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time


class Session:
    """Interactive psql session with explicit output barriers and bounded waits."""
    def __init__(self, lab, label):
        self.lab = lab
        self.errors = lab.root / (label + '.stderr.txt')
        self.errfile = self.errors.open('w')
        self.proc = subprocess.Popen(lab.psql_args(), env=lab.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errfile,
            text=True, bufsize=1)
        self.lines = queue.Queue()
        self.counter = 0
        def reader():
            try:
                for line in self.proc.stdout:
                    self.lines.put(line.rstrip('\n'))
            finally:
                self.lines.put(None)
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()
        self.query("SET application_name = 'pgbook_" + label + "'; SET statement_timeout='5s'; SET lock_timeout='3s'")

    def query(self, sql, timeout=8):
        self.counter += 1
        marker = '__BOOK_BARRIER_' + str(self.counter) + '__'
        if self.proc.poll() is not None:
            raise RuntimeError(self.error_text())
        self.proc.stdin.write(sql.rstrip(';\n') + ';\n\\echo ' + marker + '\n')
        self.proc.stdin.flush()
        result = []
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('psql barrier timed out')
            line = self.lines.get(timeout=left)
            if line is None:
                self.proc.wait(timeout=2)
                raise RuntimeError(self.error_text())
            if line == marker:
                return '\n'.join(result)
            result.append(line)

    def error_text(self):
        self.errfile.flush()
        return self.errors.read_text(errors='replace')

    def close(self):
        if self.proc.poll() is None:
            with contextlib.suppress(BrokenPipeError):
                self.proc.stdin.write('ROLLBACK;\n\\q\n')
                self.proc.stdin.flush()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.errfile.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


class Lab:
    def __init__(self, pg_bin, keep=False):
        self.bin = Path(pg_bin).resolve()
        for name in ('postgres','initdb','pg_ctl','psql','pg_dump','pg_restore','pg_basebackup','pg_waldump'):
            if not (self.bin/name).is_file():
                raise ValueError('Missing executable: ' + str(self.bin/name))
        self.root = Path(tempfile.mkdtemp(prefix='pgbook-',dir='/tmp'))
        self.data = self.root/'data'
        self.socket = self.root/'socket'; self.socket.mkdir(mode=0o700)
        self.archive = self.root/'archive'; self.archive.mkdir(mode=0o700)
        self.keep = keep
        self.started = []
        self.results = []
        self.env = {k:v for k,v in os.environ.items() if not k.startswith('PG')}
        self.env.update(PGHOST=str(self.socket),PGPORT='55432',PGUSER='book_admin',PGDATABASE='book',
                        PGCONNECT_TIMEOUT='5',PGAPPNAME='pgbook_harness',LC_ALL='C')

    def command(self, name, *args, timeout=60, env=None, check=True):
        result = subprocess.run([str(self.bin/name),*map(str,args)],env=env or self.env,
            text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(name + ' failed:\n' + result.stderr + result.stdout)
        return result

    def psql_args(self, database=None, socket=None, port=None):
        return [str(self.bin/'psql'),'-X','-qAt','-F','\t','-v','ON_ERROR_STOP=1',
                '-v','VERBOSITY=verbose','-d',database or 'book','-h',str(socket or self.socket),'-p',str(port or 55432)]

    def sql(self, text, database=None, expected_error=None, socket=None, port=None):
        result = subprocess.run(self.psql_args(database,socket,port),input=text,
            env=self.env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        if expected_error:
            assert result.returncode != 0 and expected_error in result.stderr,(text,result)
            return result.stderr.strip()
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def start(self, path, logfile):
        self.command('pg_ctl','-D',path,'-l',logfile,'-w','-t','40','start',timeout=45)
        self.started.append(path)

    def stop(self, path, mode='fast'):
        self.command('pg_ctl','-D',path,'-m',mode,'-w','-t','20','stop',timeout=25)
        if path in self.started:self.started.remove(path)

    def init(self):
        self.command('initdb','-D',self.data,'-U','book_admin','--encoding=UTF8','--no-locale',
                     '--data-checksums','--auth-local=trust','--auth-host=reject')
        config = "\nlisten_addresses = ''\nport = 55432\nunix_socket_permissions = 0700\n"
        config += "unix_socket_directories = '"+str(self.socket)+"'\n"
        config += "shared_buffers='16MB'\nmax_connections=20\nwal_level=replica\nmax_wal_senders=4\n"
        config += "fsync=on\nsynchronous_commit=on\nfull_page_writes=on\narchive_mode=on\n"
        config += "archive_command = 'test ! -f "+str(self.archive)+"/%f && cp %p "+str(self.archive)+"/%f'\n"
        config += "log_min_messages=warning\nlog_line_prefix='%m [%p] '\n"
        with (self.data/'postgresql.conf').open('a') as f:f.write(config)
        (self.data/'pg_hba.conf').write_text('local all book_admin trust\nlocal replication book_admin trust\nlocal all all reject\n')
        self.start(self.data,self.root/'server.log')
        self.sql('CREATE DATABASE book;',database='postgres')
        self.sql('CREATE SCHEMA book;')
        self.sql('SET statement_timeout=5000;')
        version = self.sql('SELECT version();')
        assert self.sql('SHOW listen_addresses;') == ''
        self.results.append({'setup':version,'socket':str(self.socket),'tcp_listener':False})

    def experiment(self, number, name, function):
        started=time.monotonic()
        try:
            detail=function()
            result={'number':number,'name':name,'status':'PASS','seconds':round(time.monotonic()-started,3),'detail':detail}
        except Exception as exc:
            result={'number':number,'name':name,'status':'FAIL','seconds':round(time.monotonic()-started,3),'error':str(exc)}
            self.results.append(result);self.write_results();raise
        self.results.append(result);self.write_results()
        print(f'{number:02d} PASS {name}',flush=True)

    def write_results(self):
        (self.root/'results.json').write_text(json.dumps(self.results,ensure_ascii=False,indent=2)+'\n')

    def cleanup(self):
        for path in list(reversed(self.started)):
            with contextlib.suppress(Exception):self.stop(path)
        self.write_results()
        if not self.keep:
            shutil.rmtree(self.root)


def experiments(lab):
    def model():
        out=lab.sql("SELECT (NULL = NULL) IS NULL, NULL IS NULL, (false AND NULL) IS FALSE, (true OR NULL) IS TRUE;")
        assert out=='t\tt\tt\tt',out
        lab.sql('CREATE TABLE book.person(id integer PRIMARY KEY, name text NOT NULL UNIQUE); INSERT INTO book.person VALUES(1,\'Алиса\'),(2,\'Борис\');')
        return 'NULL: unknown comparison; IS NULL and three-valued AND/OR verified'
    lab.experiment(1,'Типы и трёхзначная логика',model)

    def constraints():
        lab.sql('CREATE TABLE book.document(id integer PRIMARY KEY, author integer REFERENCES book.person(id), amount numeric NOT NULL CHECK(amount>0));')
        lab.sql('INSERT INTO book.document VALUES(1,1,10);')
        lab.sql('INSERT INTO book.document VALUES(1,1,20);',expected_error='23505')
        lab.sql('INSERT INTO book.document VALUES(2,999,20);',expected_error='23503')
        lab.sql('INSERT INTO book.document VALUES(2,1,-1);',expected_error='23514')
        lab.sql('BEGIN; INSERT INTO book.document VALUES(2,1,20); ROLLBACK;')
        assert lab.sql('SELECT count(*) FROM book.document;')=='1'
        return '23505 unique; 23503 foreign key; 23514 check; rollback left one row'
    lab.experiment(2,'Ограничения и откат',constraints)

    def joins():
        lab.sql('CREATE TABLE book.action(id int, document_id int); INSERT INTO book.action VALUES(1,1),(2,1); INSERT INTO book.document VALUES(2,2,20);')
        assert lab.sql('SELECT d.id,count(*),count(a.id) FROM book.document d LEFT JOIN book.action a ON a.document_id=d.id GROUP BY d.id ORDER BY d.id;')=='1\t2\t2\n2\t1\t0'
        assert lab.sql('SELECT id,row_number() OVER(ORDER BY id),count(*) OVER() FROM book.action ORDER BY id;')=='1\t1\t2\n2\t2\t2'
        return 'Outer join counts and row-preserving windows matched literal expectations'
    lab.experiment(3,'Соединения, кратность и окна',joins)

    def catalog_objects():
        result=lab.sql("SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='book' AND c.relname='document' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum;")
        assert result=='document\tid\tinteger\ndocument\tauthor\tinteger\ndocument\tamount\tnumeric',result
        (lab.root/'catalog-columns.txt').write_text(result+'\n')
        return 'pg_class→pg_namespace→pg_attribute→format_type verified against actual DDL'
    lab.experiment(4,'Каталоги объектов',catalog_objects)

    def rights():
        lab.sql("CREATE ROLE book_reader; GRANT USAGE ON SCHEMA book TO book_reader; GRANT SELECT ON book.document TO book_reader;")
        assert lab.sql('SET ROLE book_reader; SELECT count(*) FROM book.document; RESET ROLE;')=='2'
        lab.sql('SET ROLE book_reader; INSERT INTO book.document VALUES(9,1,9);',expected_error='42501')
        lab.sql('ALTER TABLE book.document ENABLE ROW LEVEL SECURITY; CREATE POLICY visible_one ON book.document TO book_reader USING(id=1);')
        assert lab.sql('SET ROLE book_reader; SELECT id FROM book.document;')=='1'
        assert lab.sql('SELECT count(*) FROM book.document;')=='2'
        return 'Schema USAGE, table SELECT, denied INSERT and owner/RLS distinction verified'
    lab.experiment(5,'Роли, полномочия и RLS',rights)

    lab.sql('CREATE TABLE book.counter(id int PRIMARY KEY,n int NOT NULL); INSERT INTO book.counter VALUES(1,0),(2,0);')
    def repeatable():
        with Session(lab,'rr') as a:
            a.query('BEGIN ISOLATION LEVEL REPEATABLE READ')
            assert a.query('SELECT n FROM book.counter WHERE id=1')=='0'
            lab.sql('UPDATE book.counter SET n=1 WHERE id=1;')
            assert a.query('SELECT n FROM book.counter WHERE id=1')=='0'
            a.query('COMMIT')
            assert a.query('SELECT n FROM book.counter WHERE id=1')=='1'
        return 'One retained snapshot saw old version; next transaction saw committed replacement'
    lab.experiment(6,'MVCC и повторяемое чтение',repeatable)

    def committed():
        with Session(lab,'rc') as a:
            a.query('BEGIN ISOLATION LEVEL READ COMMITTED')
            assert a.query('SELECT n FROM book.counter WHERE id=1')=='1'
            lab.sql('UPDATE book.counter SET n=2 WHERE id=1;')
            assert a.query('SELECT n FROM book.counter WHERE id=1')=='2'
            a.query('COMMIT')
        return 'Two statements in READ COMMITTED acquired different snapshots'
    lab.experiment(7,'Новый снимок каждой команды',committed)

    def serializable():
        lab.sql('CREATE TABLE book.duty(id int PRIMARY KEY,active boolean NOT NULL); INSERT INTO book.duty VALUES(1,true),(2,true);')
        errors=[]
        with Session(lab,'ssi_a') as a,Session(lab,'ssi_b') as b:
            a.query('BEGIN ISOLATION LEVEL SERIALIZABLE');b.query('BEGIN ISOLATION LEVEL SERIALIZABLE')
            assert a.query('SELECT count(*) FROM book.duty WHERE active')=='2'
            assert b.query('SELECT count(*) FROM book.duty WHERE active')=='2'
            a.query('UPDATE book.duty SET active=false WHERE id=1')
            b.query('UPDATE book.duty SET active=false WHERE id=2')
            for session in (a,b):
                try:session.query('COMMIT')
                except RuntimeError as exc:errors.append(str(exc))
        assert len(errors)==1 and '40001' in errors[0],errors
        assert lab.sql('SELECT count(*) FROM book.duty WHERE active;')=='1'
        return 'SSI rejected one write-skew transaction with 40001; one active row remained'
    lab.experiment(8,'Сериализуемость и 40001',serializable)

    def lock_timeout():
        with Session(lab,'lock_a') as a:
            a.query('BEGIN');a.query('UPDATE book.counter SET n=n+1 WHERE id=1')
            error=lab.sql("SET lock_timeout='150ms'; UPDATE book.counter SET n=n+1 WHERE id=1;",expected_error='55P03')
            a.query('ROLLBACK')
        return '55P03 after bounded lock_timeout; blocker released by ROLLBACK'
    lab.experiment(9,'Ожидание строки и предел времени',lock_timeout)

    def deadlock():
        errors=[]
        with Session(lab,'dead_a') as a,Session(lab,'dead_b') as b:
            for s in (a,b):s.query("SET deadlock_timeout='100ms'; SET lock_timeout='3s'; BEGIN")
            a.query('UPDATE book.counter SET n=n+1 WHERE id=1')
            b.query('UPDATE book.counter SET n=n+1 WHERE id=2')
            def blocked():
                try:a.query('UPDATE book.counter SET n=n+1 WHERE id=2')
                except Exception as exc:errors.append(str(exc))
            worker=threading.Thread(target=blocked);worker.start()
            # Wait until a has a genuine ungranted lock before creating the cycle.
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if lab.sql("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a USING(pid) WHERE a.application_name='pgbook_dead_a' AND NOT l.granted;")!='0':break
                time.sleep(.02)
            else:raise AssertionError('blocking barrier was not observed')
            try:b.query('UPDATE book.counter SET n=n+1 WHERE id=1')
            except RuntimeError as exc:errors.append(str(exc))
            worker.join(timeout=5)
            assert not worker.is_alive()
            assert len(errors)==1 and '40P01' in errors[0],errors
        return 'Observed first ungranted lock, then created cycle; one transaction rejected with 40P01'
    lab.experiment(10,'Настоящий тупик двух сеансов',deadlock)

    def vacuum():
        lab.sql('CREATE TABLE book.hot(id int PRIMARY KEY,n int) WITH(fillfactor=70,autovacuum_enabled=false); INSERT INTO book.hot SELECT i,0 FROM generate_series(1,200)i;')
        before=lab.sql("SELECT ctid FROM book.hot WHERE id=1;")
        lab.sql('UPDATE book.hot SET n=n+1; VACUUM (ANALYZE) book.hot;')
        after=lab.sql("SELECT ctid FROM book.hot WHERE id=1;")
        assert before!=after and lab.sql('SELECT sum(n) FROM book.hot;')=='200'
        frozen=lab.sql("SELECT age(relfrozenxid) FROM pg_class WHERE oid='book.hot'::regclass;")
        return {'ctid_before':before,'ctid_after':after,'relfrozenxid_age':frozen,'note':'HOT eligibility demonstrated; exact HOT count depends on page placement'}
    lab.experiment(11,'Версии, место и очистка',vacuum)

    def plan():
        lab.sql('CREATE TABLE book.plan_sample AS SELECT i AS id, i%100 AS bucket, repeat(\'x\',80) AS payload FROM generate_series(1,10000)i; CREATE INDEX plan_sample_bucket ON book.plan_sample(bucket); ANALYZE book.plan_sample;')
        text=lab.sql('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT * FROM book.plan_sample WHERE bucket=42;')
        data=json.loads(text);node=data[0]['Plan'];assert node['Actual Rows']==100
        (lab.root/'explain.json').write_text(json.dumps(data,indent=2)+'\n')
        return {'actual_rows':100,'node_type':node['Node Type'],'note':'Planner choice recorded, not forced'}
    lab.experiment(12,'Оценки и реальный EXPLAIN',plan)

    def pages():
        lab.sql('CREATE EXTENSION pageinspect; CREATE TABLE book.pages(id int,body text); INSERT INTO book.pages VALUES(1,\'abc\'),(2,\'def\'); CHECKPOINT;')
        result=lab.sql("SELECT lower,upper,special,pagesize,version FROM page_header(get_raw_page('book.pages',0));")
        lower,upper,special,size,version=map(int,result.split('\t'))
        assert lower==32 and 24<lower<=upper<=special==size==8192 and version==4,result
        filepath=lab.sql("SELECT pg_relation_filepath('book.pages');")
        raw=(lab.data/filepath).read_bytes()[:8192]
        # Page LSN is two native-endian 32-bit halves, high then low, NOT uint64.
        order='<' if sys.byteorder=='little' else '>'
        high,low,check,flags,lo,up,sp,pv,prune=struct.unpack(order+'IIHHHHHHI',raw[:24])
        assert (lo,up,sp,pv&0xff)==(lower,upper,special,version)
        checksum_on=lab.sql('SHOW data_checksums;');assert checksum_on=='on'
        tuples=lab.sql("SELECT lp,t_xmin,t_xmax,t_ctid,t_hoff FROM heap_page_items(get_raw_page('book.pages',0)) ORDER BY lp;")
        (lab.root/'page-0.bin').write_bytes(raw)
        detail={'page_lsn':f'{high:X}/{low:X}','checksum_16bit':check,'flags':flags,'lower':lo,'upper':up,'special':sp,'tuple_items':tuples}
        (lab.root/'page-header.json').write_text(json.dumps(detail,indent=2)+'\n')
        return detail
    lab.experiment(13,'Страница 8192 байта и версии строк',pages)

    def wal():
        start=lab.sql('SELECT pg_current_wal_insert_lsn();')
        lab.sql("INSERT INTO book.pages VALUES(3,'wal-visible');")
        end=lab.sql('SELECT pg_current_wal_lsn();')
        dump=lab.command('pg_waldump','-p',lab.data/'pg_wal','-s',start,'-e',end,timeout=20)
        assert 'Heap' in dump.stdout and ('INSERT' in dump.stdout or 'MULTI_INSERT' in dump.stdout),dump.stdout
        assert 'COMMIT' in dump.stdout,dump.stdout
        (lab.root/'wal-records.txt').write_text(dump.stdout)
        return {'start':start,'end':end,'records':dump.stdout}
    lab.experiment(14,'Настоящие записи WAL',wal)

    def logical():
        target=lab.root/'book.dump'
        lab.command('pg_dump','-Fc','-f',target,'book')
        lab.sql('CREATE DATABASE book_restored;',database='postgres')
        lab.command('pg_restore','--exit-on-error','-d','book_restored',target)
        original=lab.sql('SELECT id,author,amount FROM book.document ORDER BY id;')
        restored=lab.sql('SELECT id,author,amount FROM book.document ORDER BY id;',database='book_restored')
        assert original==restored
        return 'Custom-format dump restored into a new database; values matched'
    lab.experiment(15,'Логическая копия и проверенное восстановление',logical)

    def physical():
        lab.sql("CREATE TABLE book.recovery_mark(value text PRIMARY KEY); INSERT INTO book.recovery_mark VALUES('before');")
        base=lab.root/'basebackup'
        lab.command('pg_basebackup','-D',base,'-X','stream','--checkpoint=fast','-h',lab.socket,'-p','55432','-U','book_admin',timeout=60)
        if (lab.bin/'pg_verifybackup').exists():
            lab.command('pg_verifybackup',base,timeout=60)
        lab.sql("INSERT INTO book.recovery_mark VALUES('keep');")
        target_lsn=lab.sql("SELECT pg_create_restore_point('book_target');")
        lab.sql("INSERT INTO book.recovery_mark VALUES('after');")
        filename=lab.sql("SELECT pg_walfile_name('"+target_lsn+"'::pg_lsn);")
        lab.sql('SELECT pg_switch_wal();')
        deadline=time.monotonic()+10
        while not (lab.archive/filename).exists():
            if time.monotonic()>deadline:raise TimeoutError('WAL was not archived')
            time.sleep(.05)
        restore=lab.root/'physical_restore';shutil.copytree(base,restore)
        sock=lab.root/'restore_socket';sock.mkdir(mode=0o700)
        with (restore/'postgresql.conf').open('a') as f:
            f.write("\nport=55433\nunix_socket_directories='"+str(sock)+"'\narchive_mode=off\n")
            f.write("restore_command='cp "+str(lab.archive)+"/%f %p'\n")
            f.write("recovery_target_name='book_target'\nrecovery_target_action='promote'\nrecovery_target_timeline='latest'\n")
        (restore/'recovery.signal').touch()
        lab.start(restore,lab.root/'restore-server.log')
        actual=lab.sql('SELECT value FROM book.recovery_mark ORDER BY value;',socket=sock,port=55433)
        assert actual=='before\nkeep',actual
        assert lab.sql('SELECT pg_is_in_recovery();',socket=sock,port=55433)=='f'
        lab.stop(restore)
        # Process crash recovery, not a simulated disk power-loss experiment.
        lab.stop(lab.data,mode='immediate')
        lab.start(lab.data,lab.root/'server-after-crash.log')
        assert lab.sql('SELECT value FROM book.recovery_mark ORDER BY value;')=='after\nbefore\nkeep'
        return {'restore_point':target_lsn,'archived_segment':filename,'restored_rows':['before','keep'],'primary_crash_recovery':'committed rows retained'}
    lab.experiment(16,'Физическая копия, PITR и аварийное восстановление',physical)


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run',action='store_true',help='explicitly create and run an isolated cluster')
    parser.add_argument('--pg-bin',help='absolute PostgreSQL 18 bin directory')
    parser.add_argument('--keep',action='store_true',help='keep stopped lab files and full results under /tmp')
    args=parser.parse_args()
    if not args.run:
        parser.print_help();return 0
    if not args.pg_bin:parser.error('--run requires --pg-bin')
    if hasattr(os,'geteuid') and os.geteuid()==0:parser.error('run as an ordinary user; PostgreSQL refuses root')
    lab=Lab(args.pg_bin,args.keep)
    print('Private lab directory:',lab.root,flush=True)
    try:
        lab.init();experiments(lab)
        print('OK: all 16 experiments passed. TCP listener disabled.',flush=True)
        if args.keep:print('Stopped lab and evidence retained at:',lab.root,flush=True)
        return 0
    except Exception as exc:
        print('FAIL:',exc,file=sys.stderr)
        print('Evidence directory:',lab.root,'(use --keep to retain it)',file=sys.stderr)
        return 1
    finally:
        lab.cleanup()

if __name__=='__main__':
    raise SystemExit(main())
