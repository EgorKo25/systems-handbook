"""Finite Linux release experiment in one prepared owned stand, without Git/service installs."""
import argparse,hashlib,json,os,re,signal,socket,subprocess,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
if not(root/'prepared.json').is_file():p.error('prepared stand required')
env=os.environ.copy();env.update(json.loads((root/'env.json').read_text()));env.pop('BASH_ENV',None);env.pop('ENV',None)
if Path(env['LABROOT']).resolve()!=root:p.error('stand identity mismatch')
out=root/'releases'
if out.exists()or out.is_symlink():p.error('releases already exists; preserved. Read its report before another experiment in a new stand')
out.mkdir();children=[];report={'format':1,'builds':[],'checks':[]}
http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def check(name,ok,detail):
 report['checks'].append(dict(name=name,ok=bool(ok),detail=detail))
 if not ok:raise RuntimeError(name)
def build(v):
 d=out/v;d.mkdir();binary=d/'service'
 cmd=[env['GO'],'build','-mod=readonly','-trimpath','-buildvcs=false','-ldflags=-X main.Version='+v,'-o',str(binary),'./cmd/handbook-service']
 r=subprocess.run(cmd,cwd=root/'service',env=env,capture_output=True,text=True,timeout=180)
 (d/'build.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('build failed: '+v)
 m=dict(version=v,sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source_revision=None,source_dirty=True,argv=cmd)
 (d/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');report['builds'].append(m);return binary,m
def port():
 with socket.socket()as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def owns_listener(child,n):
 """Linux only: match this child's socket fd inode with its IPv4 LISTEN row."""
 if child.poll()is not None:return False
 try:
  proc=Path('/proc')/str(child.pid)
  inodes=set()
  for fd in (proc/'fd').iterdir():
   try:
    m=re.fullmatch(r'socket:\[(\d+)\]',os.readlink(fd))
    if m:inodes.add(m[1])
   except FileNotFoundError:pass
  wanted='0100007F:'+format(n,'04X')
  rows=(proc/'net/tcp').read_text().splitlines()[1:]
  found=any(len(fields)>9 and fields[1]==wanted and fields[3]=='0A' and fields[9]in inodes for fields in (r.split()for r in rows))
  return found and child.poll()is None
 except (OSError,ValueError):return False
def start(binary,v):
 n=port();log=(out/(v+'-run.log')).open('w');child=subprocess.Popen([str(binary),'-listen','127.0.0.1:'+str(n)],cwd=root/'service',env=env,stdout=log,stderr=log);children.append((child,log));deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  if child.poll()is not None:raise RuntimeError('child exited before readiness')
  if not owns_listener(child,n):time.sleep(.03);continue
  try:
   with http.open('http://127.0.0.1:'+str(n)+'/healthz',timeout=.2)as r:reply=json.load(r)
   if owns_listener(child,n) and reply.get('version')==v:return child,n
  except (OSError,ValueError):pass
  time.sleep(.03)
 raise TimeoutError('readiness')
def version(child,n):
 if not owns_listener(child,n):raise RuntimeError('child does not own the listening socket')
 with http.open('http://127.0.0.1:'+str(n)+'/healthz',timeout=1)as r:value=json.load(r)['version']
 if not owns_listener(child,n):raise RuntimeError('child lost its listening socket during request')
 return value
try:
 b1,m1=build('lab-v1');b2,m2=build('lab-v2');current=out/'current';current.symlink_to('lab-v1');old,p1=start(current/'service','lab-v1')
 # A rejected manifest must not publish or rewrite the previous release.
 bad=dict(m2,sha256='0'*64);accepted=hashlib.sha256(b2.read_bytes()).hexdigest()==bad['sha256']
 check('bad-hash-refused',not accepted and os.readlink(current)=='lab-v1',os.readlink(current))
 check('old-bytes-preserved',hashlib.sha256(b1.read_bytes()).hexdigest()==m1['sha256'],m1['sha256'])
 if hashlib.sha256(b2.read_bytes()).hexdigest()!=m2['sha256']:raise RuntimeError('release hash mismatch: lab-v2')
 nxt=out/'current.next';nxt.symlink_to('lab-v2');os.replace(nxt,current)
 check('publish-does-not-replace-running-process',version(old,p1)=='lab-v1',version(old,p1))
 new,p2=start(current/'service','lab-v2');check('new-process-ready',version(new,p2)=='lab-v2',version(new,p2))
 nxt.symlink_to('lab-v1');os.replace(nxt,current);check('rollback-pointer',os.readlink(current)=='lab-v1',os.readlink(current))
 check('new-still-v2-until-stopped',version(new,p2)=='lab-v2',version(new,p2))
 with socket.socket()as busy:
  busy.bind(('127.0.0.1',0));busy.listen();r=subprocess.run([str(b2),'-listen','127.0.0.1:'+str(busy.getsockname()[1])],capture_output=True,text=True,timeout=5,env=env)
  check('busy-port-refused',r.returncode!=0 and 'bind' in r.stderr,r.stderr)
 report['ok']=True
finally:
 for child,log in children:
  if child.poll()is None:
   child.send_signal(signal.SIGTERM)
   try:child.wait(timeout=7)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
  log.close()
 report['children_stopped']=all(c.poll()is not None for c,l in children)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
