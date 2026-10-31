"""Portable Redis mTLS/ACL checks; no system trust or services are modified.

Requires Redis built with TLS, Python 3, and OpenSSL supporting -addext.
Reference run: Redis 7.0.15. Temporary CA material is removed at completion.
"""
from pathlib import Path
import sys,tempfile,subprocess,ssl,socket,json,time
import argparse, shutil
parser = argparse.ArgumentParser(description="Verify mTLS and ACL using an owned Redis loopback process (32 MiB).")
parser.add_argument('--redis-server', default='redis-server', help='Redis TLS-enabled server executable; default: PATH')
parser.add_argument('--openssl', default='openssl', help='OpenSSL executable; default: PATH')
parser.add_argument('--output', type=Path, default=Path(__file__).with_name('depth-tls-results.json'))
options = parser.parse_args()
server_binary = shutil.which(options.redis_server)
openssl_binary = shutil.which(options.openssl)
if server_binary is None or openssl_binary is None:
 parser.error('Redis/OpenSSL executable not found; install separately or pass its executable option.')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live import Redis,port,wait_ready
report={'status':'RUNNING','kind':'owned loopback Redis mTLS and ACL','cases':[], 'limits':['No operating-system trust installation','No load or certificate-rotation experiment','No TLS protection of Sentinel/Cluster tested here']}
def check(name,actual,expected):
 assert actual==expected,(name,actual,expected)
 report['cases'].append({'name':name,'actual':actual,'expected':expected,'status':'PASS'})
proc=None;clients=[];log=None
temp_dir=tempfile.TemporaryDirectory(prefix='redis-depth-tls-')
try:
 folder=temp_dir.name
 d=Path(folder);log=(d/'commands.log').open('wb')
 def run(*cmd):return subprocess.run(cmd,cwd=d,stdout=log,stderr=log,check=True,timeout=20)
 run(openssl_binary,'req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.crt','-days','2','-subj','/CN=Redis Book CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
 for role in ['server','client']:
  run(openssl_binary,'req','-new','-newkey','rsa:2048','-nodes','-keyout',role+'.key','-out',role+'.csr','-subj','/CN=localhost')
  (d/(role+'.ext')).write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage='+role+'Auth\nbasicConstraints=CA:FALSE\n')
  run(openssl_binary,'x509','-req','-in',role+'.csr','-CA','ca.crt','-CAkey','ca.key','-CAcreateserial','-out',role+'.crt','-days','2','-extfile',role+'.ext')
 run(openssl_binary,'verify','-CAfile','ca.crt','-purpose','sslserver','server.crt');check('OpenSSL server chain and usage valid',True,True)
 run(openssl_binary,'verify','-CAfile','ca.crt','-purpose','sslclient','client.crt');check('OpenSSL client chain and usage valid',True,True)
 n=port();proc=subprocess.Popen([server_binary,'--bind','127.0.0.1','--port','0','--tls-port',str(n),'--tls-cert-file',str(d/'server.crt'),'--tls-key-file',str(d/'server.key'),'--tls-ca-cert-file',str(d/'ca.crt'),'--tls-auth-clients','yes','--dir',str(d),'--save','','--appendonly','no','--maxmemory','32mb','--requirepass','lab-admin-only'],stdout=log,stderr=log);wait_ready(proc,n)
 def context(with_cert=True):
  c=ssl.create_default_context(cafile=d/'ca.crt')
  if with_cert:c.load_cert_chain(d/'client.crt',d/'client.key')
  return c
 r=Redis(n,context());clients.append(r)
 check('valid certificate does not bypass AUTH','NOAUTH' in r.send('PING').get('error',''),True)
 check('password over mTLS authenticates',r.send('AUTH','default','lab-admin-only'),'OK')
 check('authorized PING after AUTH',r.send('PING'),'PONG')
 report['server_version']=r.send('INFO','server').split('redis_version:')[1].splitlines()[0]
 r.send('ACL','SETUSER','book-reader','reset','on','>reader','~book:product:*','+get','+ping')
 r2=Redis(n,context());clients.append(r2);r2.send('AUTH','book-reader','reader')
 check('valid certificate and AUTH cannot bypass ACL','NOPERM' in r2.send('SET','book:product:42',150).get('error',''),True)
 try:
  bad=Redis(n,context(False));clients.append(bad);bad.send('PING');failed=False
 except (ssl.SSLError,ConnectionError,RuntimeError):failed=True
 check('missing client certificate refused',failed,True)
 try:
  raw=socket.create_connection(('127.0.0.1',n),timeout=2)
  with context().wrap_socket(raw,server_hostname='wrong.example.test'):pass
  failed=False
 except ssl.SSLCertVerificationError:failed=True
 check('trusted CA but wrong server identity refused',failed,True)
 report['status']='PASS';report['cases_count']=len(report['cases'])
except Exception as error:
 report['status']='FAIL'
 report['failure_type']=type(error).__name__
 raise
finally:
 for c in clients:
  try:c.close()
  except Exception:pass
 if proc is not None and proc.poll() is None:
  proc.terminate()
  try:proc.wait(5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 report['processes_remaining']=int(proc is not None and proc.poll() is None)
 if log is not None:log.close()
 temp_dir.cleanup()
 report['cases_count']=len(report['cases'])
 options.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'cases':len(report['cases']),'processes_remaining':report['processes_remaining']}))
