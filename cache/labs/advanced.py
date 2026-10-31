"""Owned Redis ACL/TLS/replication/Sentinel/Cluster and Memcached mTLS lab.

Requires Linux, OpenSSL and server binaries; never uses existing services.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
from live import Redis, Memcached, port, wait_ready


def wait_for(function,timeout=20):
    deadline=time.monotonic()+timeout
    last=None
    while time.monotonic()<deadline:
        try:
            last=function()
            if last:return last
        except (OSError,RuntimeError):pass
        time.sleep(.1)
    raise AssertionError('Condition timeout: '+str(last))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--redis-server',default='redis-server');parser.add_argument('--redis-cli',default='redis-cli');parser.add_argument('--memcached',default='memcached')
    args=parser.parse_args()
    for value in [args.redis_server,args.redis_cli,args.memcached,'openssl']:
        if not shutil.which(value):parser.error('Missing program '+value)
    report={'status':'RUNNING','kind':'actual owned loopback processes','cases':[],'limits':['No network-partition test','No power-loss test','No Memcached SASL or built-in proxy execution','TLS and cluster tested separately, not combined production topology']}
    def check(name,actual,expected=True):
        if actual!=expected:raise AssertionError(f'{name}: {actual!r} != {expected!r}')
        report['cases'].append({'name':name,'status':'PASS','actual':actual})
    with tempfile.TemporaryDirectory(prefix='cache-book-advanced-') as tmp:
        base=Path(tmp);processes=[];clients=[];logs=[]
        def launch(name,cmd,number):
            log=open(base/(name+'.log'),'wb');logs.append(log)
            proc=subprocess.Popen(cmd,stdout=log,stderr=log);processes.append(proc)
            try:wait_ready(proc,number)
            except Exception:
                log.flush();print((base/(name+'.log')).read_text(errors='replace'));raise
            return proc
        def server(name,number,extra='',sentinel=False):
            directory=base/name;directory.mkdir(exist_ok=True)
            conf=directory/'server.conf'
            text=f'bind 127.0.0.1\nport {number}\ndir {directory}\n'
            if not sentinel:text+='save ""\nappendonly no\n'
            text+=extra+'\n';conf.write_text(text)
            return launch(name,[args.redis_server,str(conf)]+(['--sentinel'] if sentinel else []),number)
        def rc(number,context=None):
            c=Redis(number,context);clients.append(c);return c
        try:
            # ACL applies independently to command and key scope, then survives a restart.
            ap=port();acl=base/'users.acl';acl.write_text('user default on nopass ~* +@all\n')
            proc=server('acl',ap,'aclfile '+str(acl));admin=rc(ap)
            report['versions']={'redis':next(x.split(':',1)[1] for x in admin.send('INFO','server').splitlines() if x.startswith('redis_version:'))}
            check('ACL create',admin.send('ACL','SETUSER','book-reader','reset','on','>lab-reader-only','~book:product:*','+get','+mget','+ttl','+ping'),'OK')
            admin.send('SET','book:product:42','120')
            reader=rc(ap);check('ACL AUTH',reader.send('AUTH','book-reader','lab-reader-only'),'OK')
            check('ACL permitted GET',reader.send('GET','book:product:42'),'120')
            check('ACL command denied','NOPERM' in reader.send('SET','book:product:42','150')['error'])
            check('ACL key denied','NOPERM' in reader.send('GET','other:42')['error'])
            bad=rc(ap);check('ACL bad password','WRONGPASS' in bad.send('AUTH','book-reader','wrong')['error'])
            check('ACL SAVE',admin.send('ACL','SAVE'),'OK')
            proc.terminate();proc.wait(5);server('acl',ap,'aclfile '+str(acl))
            reconnected=rc(ap);check('ACL survives restart',reconnected.send('AUTH','book-reader','lab-reader-only'),'OK')
            # Independent CA; SAN 127.0.0.1, server/client EKUs.
            def openssl(*parts):subprocess.run(['openssl',*parts],cwd=base,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.crt','-days','1','-subj','/CN=Cache Book Temporary CA')
            for name,eku in [('server','serverAuth'),('client','clientAuth')]:
                openssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',name+'.key','-out',name+'.csr','-subj','/CN=localhost')
                (base/(name+'.ext')).write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage='+eku+'\nbasicConstraints=CA:FALSE\n')
                openssl('x509','-req','-in',name+'.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-out',name+'.crt','-days','1','-extfile',name+'.ext')
            good=ssl.create_default_context(cafile=str(base/'ca.crt'));good.load_cert_chain(str(base/'client.crt'),str(base/'client.key'))
            nocert=ssl.create_default_context(cafile=str(base/'ca.crt'))
            tp=port();td=base/'redis-tls';td.mkdir()
            conf=td/'tls.conf';conf.write_text(f'bind 127.0.0.1\nport 0\ntls-port {tp}\ntls-cert-file {base}/server.crt\ntls-key-file {base}/server.key\ntls-ca-cert-file {base}/ca.crt\ntls-auth-clients yes\nsave ""\nappendonly no\ndir {td}\n')
            launch('redis-tls',[args.redis_server,str(conf)],tp)
            secure=rc(tp,good);check('Redis mTLS PING',secure.send('PING'),'PONG')
            def denied(factory,operation):
                c=None
                try:c=factory();operation(c);return False
                except (OSError,ssl.SSLError,RuntimeError):return True
                finally:
                    if c:c.close()
            check('Redis rejects missing client certificate',denied(lambda:Redis(tp,nocert),lambda c:c.send('PING')))
            mp=port();mcmd=[args.memcached,'-l','127.0.0.1','-p',str(mp),'-U','0','-m','32','-t','2','-Z','-o',f'ssl_chain_cert={base}/server.crt,ssl_key={base}/server.key,ssl_ca_cert={base}/ca.crt,ssl_verify_mode=2']
            if os.geteuid()==0:mcmd+=['-u','root']
            launch('memcached-tls',mcmd,mp)
            mc=Memcached(mp,good);clients.append(mc);report['versions']['memcached']=mc.version()
            check('Memcached mTLS set',mc.store('set','book:tls','secure'),'STORED')
            check('Memcached mTLS get',mc.get('book:tls')['value'],'secure')
            check('Memcached rejects missing client certificate',denied(lambda:Memcached(mp,nocert),lambda c:c.version()))
            # Replication and WAIT on one connection.
            pp,rp=port(),port();primary_proc=server('primary',pp);server('replica',rp,f'replicaof 127.0.0.1 {pp}')
            primary=rc(pp);replica=rc(rp)
            wait_for(lambda:'master_link_status:up' in replica.send('INFO','replication'))
            primary.send('SET','book:replication','43');check('WAIT confirms replica',primary.send('WAIT',1,3000),1)
            check('Replica value',replica.send('GET','book:replication'),'43')
            # Three owned Sentinel processes, quorum two; kill only the owned primary.
            sentinel_ports=[port() for _ in range(3)];sentinels=[]
            for i,sp in enumerate(sentinel_ports):
                server('sentinel'+str(i),sp,f'sentinel monitor book-primary 127.0.0.1 {pp} 2\nsentinel down-after-milliseconds book-primary 1000\nsentinel failover-timeout book-primary 5000\nsentinel parallel-syncs book-primary 1',True)
                sentinels.append(rc(sp))
            wait_for(lambda:all(len(s.send('SENTINEL','sentinels','book-primary'))==2 for s in sentinels),timeout=25)
            primary_proc.terminate();primary_proc.wait(5)
            wait_for(lambda:sentinels[0].send('SENTINEL','get-master-addr-by-name','book-primary')==['127.0.0.1',str(rp)],timeout=30)
            # Promotion may close existing client connections; discover and reconnect.
            replica=rc(rp)
            check('Sentinel promotes owned replica',replica.send('ROLE')[0],'master')
            check('Sentinel surviving value',replica.send('GET','book:replication'),'43')
            # Fixed, checked client and bus port ranges for the six-node lab.
            numbers=None
            for start in range(17400,17900,10):
                candidate=list(range(start,start+6))
                try:
                    for n in candidate+[n+10000 for n in candidate]:port(n)
                except OSError:continue
                numbers=candidate;break
            if numbers is None:raise RuntimeError('No free six-node port range')
            for i,n in enumerate(numbers):server('cluster'+str(i),n,'cluster-enabled yes\ncluster-config-file nodes.conf\ncluster-node-timeout 2000')
            created=subprocess.run([args.redis_cli,'--cluster','create',*[f'127.0.0.1:{n}' for n in numbers],'--cluster-replicas','1','--cluster-yes'],text=True,capture_output=True,timeout=30)
            if created.returncode:raise RuntimeError(created.stdout+created.stderr)
            nodes=[rc(n) for n in numbers]
            wait_for(lambda:all('cluster_state:ok' in n.send('CLUSTER','INFO') for n in nodes))
            check('Cluster all slots assigned','cluster_slots_assigned:16384' in nodes[0].send('CLUSTER','INFO'))
            cli=lambda *cmd:subprocess.check_output([args.redis_cli,'-c','-p',str(numbers[0]),*cmd],text=True,timeout=10).strip()
            check('Cluster routed SET',cli('SET','product:42','150'),'OK')
            check('Cluster routed GET',cli('GET','product:42'),'150')
            check('Cluster hash-tag MSET',cli('MSET','cart:{u42}:items','item1','cart:{u42}:version','1'),'OK')
            check('Cluster CROSSSLOT rejected','CROSSSLOT' in cli('MSET','a','1','b','2'))
            promoted_index=next(i for i,c in enumerate(nodes) if c.send('ROLE')[0]=='slave')
            promoted=nodes[promoted_index]
            wait_for(lambda:promoted.send('ROLE')[3]=='connected')
            parent=nodes[numbers.index(int(promoted.send('ROLE')[2]))]
            for i in range(100):
                probe_key='book:failover:'+str(i)
                if parent.send('SET',probe_key,'confirmed')=='OK':break
            else:raise AssertionError('No probe key found in parent slots')
            check('Cluster replica confirms probe',parent.send('WAIT',1,2000),1)
            check('Cluster planned failover accepted',promoted.send('CLUSTER','FAILOVER'),'OK')
            def promoted_role():
                c=Redis(numbers[promoted_index])
                try:return c.send('ROLE')[0]=='master'
                finally:c.close()
            try:wait_for(promoted_role,timeout=30)
            except AssertionError:
                for i in range(6):
                    print('CLUSTER LOG',i,(base/('cluster'+str(i)+'.log')).read_text(errors='replace')[-4000:])
                raise
            promoted=rc(numbers[promoted_index])
            check('Cluster planned failover role',promoted.send('ROLE')[0],'master')
            check('Cluster value after role change',cli('GET','product:42'),'150')
            check('Promoted shard retains confirmed probe',cli('GET',probe_key),'confirmed')
            report['status']='PASS';report['cases_count']=len(report['cases'])
            out=Path(__file__).with_name('advanced-results.json');out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'status':'PASS','cases':len(report['cases']),'versions':report['versions']}))
        finally:
            for c in clients:
                try:c.close()
                except OSError:pass
            for proc in processes:
                if proc.poll() is None:proc.terminate()
            for proc in processes:
                try:proc.wait(3)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            for log in logs:log.close()


if __name__=='__main__':main()
