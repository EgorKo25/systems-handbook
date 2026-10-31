"""Start only owned loopback servers; test actual protocols using stdlib Python.

No packages or system services are installed or modified. Servers must exist.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time


class Redis:
    def __init__(self,port,context=None):
        self.sock=socket.create_connection(('127.0.0.1',port),timeout=3)
        if context is not None:self.sock=context.wrap_socket(self.sock,server_hostname='127.0.0.1')
        self.file=self.sock.makefile('rb')
    def close(self): self.file.close(); self.sock.close()
    def send(self,*args):
        parts=[a if isinstance(a,bytes) else str(a).encode() for a in args]
        self.sock.sendall(b'*'+str(len(parts)).encode()+b'\r\n'+b''.join(b'$'+str(len(p)).encode()+b'\r\n'+p+b'\r\n' for p in parts))
        return self.read()
    def read(self):
        line=self.file.readline()
        if not line.endswith(b'\r\n'): raise RuntimeError('Truncated RESP')
        tag,value=line[:1],line[1:-2]
        if tag==b'+': return value.decode()
        if tag==b'-': return {'error':value.decode()}
        if tag==b':': return int(value)
        if tag==b'$':
            n=int(value)
            if n==-1:return None
            body=self.file.read(n)
            if len(body)!=n or self.file.read(2)!=b'\r\n':raise RuntimeError('Bad bulk reply')
            return body.decode()
        if tag==b'*':
            n=int(value)
            return None if n==-1 else [self.read() for _ in range(n)]
        raise RuntimeError('Unknown RESP type')


class Memcached:
    def __init__(self,port,context=None):
        self.sock=socket.create_connection(('127.0.0.1',port),timeout=3)
        if context is not None:self.sock=context.wrap_socket(self.sock,server_hostname='127.0.0.1')
        self.file=self.sock.makefile('rb')
    def close(self): self.file.close(); self.sock.close()
    def store(self,command,key,value,ttl=60,token=None):
        data=value.encode()
        header=f'{command} {key} 0 {ttl} {len(data)}'+(f' {token}' if token is not None else '')
        self.sock.sendall(header.encode()+b'\r\n'+data+b'\r\n')
        return self.file.readline().decode().strip()
    def get(self,key,cas=False):
        self.sock.sendall(('gets ' if cas else 'get ').encode()+key.encode()+b'\r\n')
        line=self.file.readline()
        if line==b'END\r\n':return None
        parts=line.decode().split()
        if len(parts)<4 or parts[0]!='VALUE':raise RuntimeError(line)
        n=int(parts[3]); data=self.file.read(n)
        if len(data)!=n or self.file.read(2)!=b'\r\n' or self.file.readline()!=b'END\r\n':raise RuntimeError('Bad VALUE reply')
        return dict(value=data.decode(),token=parts[4] if cas else None)
    def version(self):
        self.sock.sendall(b'version\r\n');return self.file.readline().decode().strip()


def port(requested=0):
    with socket.socket() as s:
        s.bind(('127.0.0.1',requested));return s.getsockname()[1]


def wait_ready(proc,number):
    until=time.monotonic()+8
    while time.monotonic()<until:
        if proc.poll() is not None:raise RuntimeError('Owned server exited during startup')
        try:
            with socket.create_connection(('127.0.0.1',number),timeout=.1):return
        except OSError:time.sleep(.05)
    raise RuntimeError('Owned server did not become ready')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--redis-server',default='redis-server');p.add_argument('--redis-cli',default='redis-cli')
    p.add_argument('--memcached',default='memcached');p.add_argument('--manual',action='store_true')
    p.add_argument('--output',type=Path,default=Path(__file__).with_name('live-results.json'))
    args=p.parse_args(); programs={}
    for name in ['redis_server','redis_cli','memcached']:
        value=getattr(args,name); resolved=shutil.which(value)
        if not resolved:p.error(f'Program unavailable: {value}; install it separately or supply its path')
        programs[name]=resolved
    rp,mp=port(16379 if args.manual else 0),port(11222 if args.manual else 0)
    if rp==mp:mp=port()
    processes=[];clients=[]
    with tempfile.TemporaryDirectory(prefix='cache-book-lab-') as directory:
        with open(Path(directory)/'servers.log','wb') as log:
            try:
                redis_args=[programs['redis_server'],'--bind','127.0.0.1','--port',str(rp),'--save','','--appendonly','no','--dir',directory,'--maxmemory','32mb','--maxmemory-policy','allkeys-lru']
                mem_args=[programs['memcached'],'-l','127.0.0.1','-p',str(mp),'-U','0','-m','32','-t','2']
                if hasattr(os,'geteuid') and os.geteuid()==0:mem_args+=['-u','root']
                for cmd,number in [(redis_args,rp),(mem_args,mp)]:
                    proc=subprocess.Popen(cmd,stdout=log,stderr=log)
                    processes.append(proc);wait_ready(proc,number)
                r=Redis(rp);m=Memcached(mp);clients=[r,m]
                if args.manual:
                    print('Owned lab ready: Redis 127.0.0.1:16379; Memcached 127.0.0.1:11222. Enter stops both.',flush=True)
                    input();return
                report=dict(kind='actual loopback servers',versions={},cases=[])
                report['versions']['redis']=next(line.split(':',1)[1] for line in r.send('INFO','server').splitlines() if line.startswith('redis_version:'))
                report['versions']['memcached']=m.version()
                def check(name,actual,expected):
                    if actual!=expected:raise AssertionError(f'{name}: {actual!r} != {expected!r}')
                    report['cases'].append(dict(name=name,actual=actual,expected=expected,status='PASS'))
                check('redis ping',r.send('PING'),'PONG')
                check('redis set ttl',r.send('SET','book:cache:42','hello','EX',60),'OK')
                check('redis value',r.send('GET','book:cache:42'),'hello')
                ttl=r.send('TTL','book:cache:42');check('redis ttl range',0<ttl<=60,True)
                check('redis nx rejects',r.send('SET','book:cache:42','other','NX'),None)
                check('redis replace',r.send('SET','book:cache:42','hello'),'OK')
                check('redis plain set removes ttl',r.send('TTL','book:cache:42'),-1)
                check('redis missing',r.send('GET','book:cache:missing'),None)
                r.send('SET','book:cache:empty','');check('redis empty',r.send('GET','book:cache:empty'),'')
                check('redis incr first',r.send('INCR','book:cache:n'),1)
                check('redis incr second',r.send('INCR','book:cache:n'),2)
                check('redis hash fields',r.send('HSET','book:cache:hash','version','7','price','120'),2)
                check('redis hash read',r.send('HGET','book:cache:hash','price'),'120')
                r.send('SET','book:cache:bad','text');r.send('MULTI')
                r.send('INCR','book:cache:bad');r.send('SET','book:cache:after','written')
                transaction=r.send('EXEC');check('redis exec per-command error',isinstance(transaction[0],dict) and 'error' in transaction[0] and transaction[1]=='OK',True)
                check('redis no rollback',r.send('GET','book:cache:after'),'written')
                script='local n=redis.call("INCR",KEYS[1]); if n==1 then redis.call("EXPIRE",KEYS[1],60) end; return n'
                check('redis lua count',r.send('EVAL',script,1,'book:cache:rate'),1)
                check('redis lua ttl',0<r.send('TTL','book:cache:rate')<=60,True)
                check('memcached set',m.store('set','book:42','hello'),'STORED')
                check('memcached get',m.get('book:42')['value'],'hello')
                check('memcached add rejects',m.store('add','book:42','other'),'NOT_STORED')
                previous=m.get('book:42',cas=True)
                m.store('set','book:42','new')
                check('memcached cas conflict',m.store('cas','book:42','old',token=previous['token']),'EXISTS')
                check('memcached cas preserves',m.get('book:42')['value'],'new')
                current=m.get('book:42',cas=True)
                check('memcached cas success',m.store('cas','book:42','newer',token=current['token']),'STORED')
                check('memcached missing',m.get('book:missing'),None)
                m.store('set','book:empty','');check('memcached empty',m.get('book:empty')['value'],'')
                m.store('set','book:lines','hello\r\nEND\r\nworld');check('memcached byte framing',m.get('book:lines')['value'],'hello\r\nEND\r\nworld')
                m.store('set','book:expired','x',ttl=2592001);check('memcached absolute expiration',m.get('book:expired'),None)
                # Check CLI semantics separately from the custom RESP decoder.
                reply=subprocess.check_output([programs['redis_cli'],'-h','127.0.0.1','-p',str(rp),'PING'],text=True).strip()
                check('redis-cli actual',reply,'PONG')
                report['status']='PASS';report['limits']='No throughput, persistence, power-loss, Sentinel, Cluster, TLS or production-load claims.'
                args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(dict(status='PASS',cases=len(report['cases']),versions=report['versions'])))
            finally:
                for client in clients:client.close()
                for proc in processes:
                    if proc.poll() is None:proc.terminate()
                for proc in processes:
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()


if __name__=='__main__':main()
