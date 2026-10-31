"""Redis RDB/AOF restore lab in owned temporary processes; no power-loss claim."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from live import Redis, port, wait_ready


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--redis-server',default='redis-server')
    args=parser.parse_args()
    if not shutil.which(args.redis_server):parser.error('redis-server is required')
    report={'status':'RUNNING','kind':'owned process crash and file restore', 'cases':[],
            'limits':['No host power loss','No disk corruption','AOF always mode; no everysec RPO measurement','Versions outside recorded binary were not executed']}
    def check(name,actual,expected):
        if actual!=expected:raise AssertionError(f'{name}: {actual!r} != {expected!r}')
        report['cases'].append({'name':name,'actual':actual,'expected':expected,'status':'PASS'})
    with tempfile.TemporaryDirectory(prefix='cache-book-persistence-') as tmp:
        base=Path(tmp);procs=[];clients=[];logs=[]
        def start(name,extra='',directory=None):
            directory=directory or base/name;directory.mkdir(exist_ok=True)
            number=port();conf=directory/'redis.conf'
            conf.write_text(f'bind 127.0.0.1\nport {number}\ndir {directory}\ndbfilename dump.rdb\nsave ""\nappendonly no\n'+extra+'\n')
            log=open(base/(name+'.log'),'ab');logs.append(log)
            p=subprocess.Popen([args.redis_server,str(conf)],stdout=log,stderr=log);procs.append(p)
            wait_ready(p,number);c=Redis(number);clients.append(c)
            return p,c,directory
        def crash(p):
            p.kill();p.wait(5)
        try:
            p,c,directory=start('rdb')
            report['redis_version']=next(s.split(':',1)[1] for s in c.send('INFO','server').splitlines() if s.startswith('redis_version:'))
            check('RDB seed value',c.send('SET','book:version','before-snapshot'),'OK')
            check('RDB expiry seed',c.send('SET','book:expired','temporary','EX',1),'OK')
            check('SAVE returns after snapshot write',c.send('SAVE'),'OK')
            check('RDB file exists',(directory/'dump.rdb').is_file(),True)
            check('Post-snapshot mutation',c.send('SET','book:version','after-snapshot'),'OK')
            crash(p)
            restored=base/'rdb-restored';restored.mkdir()
            shutil.copy2(directory/'dump.rdb',restored/'dump.rdb')
            time.sleep(1.1)
            p,r,_=start('rdb-restored',directory=restored)
            check('RDB restores snapshot value',r.send('GET','book:version'),'before-snapshot')
            check('Expired absolute deadline remains expired',r.send('GET','book:expired'),None)
            p,a,adir=start('aof','appendonly yes\nappendfsync always')
            check('AOF SET',a.send('SET','book:value','persisted'),'OK')
            check('AOF HSET',a.send('HSET','book:hash','version',7),1)
            check('AOF INCR',a.send('INCR','book:counter'),1)
            check('AOF write status','aof_last_write_status:ok' in a.send('INFO','persistence'),True)
            crash(p)
            restored_aof=base/'aof-restored';shutil.copytree(adir,restored_aof)
            p,b,_=start('aof-restored','appendonly yes\nappendfsync always',restored_aof)
            check('AOF restores string',b.send('GET','book:value'),'persisted')
            check('AOF restores hash',b.send('HGET','book:hash','version'),'7')
            check('AOF restores counter',b.send('GET','book:counter'),'1')
            check('AOF rewrite accepted',b.send('BGREWRITEAOF'),'Background append only file rewriting started')
            until=time.monotonic()+15
            while time.monotonic()<until:
                info=b.send('INFO','persistence')
                if 'aof_rewrite_in_progress:0' in info and 'aof_last_bgrewrite_status:ok' in info:break
                time.sleep(.05)
            else:raise AssertionError('AOF rewrite did not finish')
            check('AOF rewrite preserves value',b.send('GET','book:value'),'persisted')
            crash(p)
            rewritten=base/'rewritten-restored';shutil.copytree(restored_aof,rewritten)
            p,reloaded,_=start('rewritten-restored','appendonly yes\nappendfsync always',rewritten)
            check('Rewritten AOF restores string',reloaded.send('GET','book:value'),'persisted')
            check('Rewritten AOF restores hash',reloaded.send('HGET','book:hash','version'),'7')
            check('Rewritten AOF restores counter',reloaded.send('GET','book:counter'),'1')
            report['status']='PASS';report['cases_count']=len(report['cases'])
            Path(__file__).with_name('persistence-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'status':'PASS','cases':len(report['cases']),'redis':report['redis_version']}))
        finally:
            for c in clients:
                try:c.close()
                except OSError:pass
            for p in procs:
                if p.poll() is None:p.terminate()
            for p in procs:
                try:p.wait(3)
                except subprocess.TimeoutExpired:p.kill();p.wait()
            for log in logs:log.close()


if __name__=='__main__':main()
