#!/usr/bin/env python3
"""Personal single-world GitHub handoff. No token handling, no Git disk commits.

Source candidate: backend and fake tests are not a prepared/tested guest image.
"""
from __future__ import annotations
import argparse,base64,contextlib,hashlib,json,os,queue,re,shutil,subprocess,sys,threading,time,uuid
from pathlib import Path
from types import SimpleNamespace
import world

CHUNK=512*1024**2
IDENTITY={'name':'EgorKo25','email':'77259232+EgorKo25@users.noreply.github.com'}
HEX=re.compile(r'[0-9a-f]{64}\Z');TOKEN=re.compile(r'[0-9a-f]{32}\Z');TAG=re.compile(r'world-[0-9a-f]{32}\Z')
class Error(Exception):pass
class HTTP(Error):
 def __init__(self,status):self.status=status;super().__init__('GitHub HTTP '+str(status)+'; local state retained')
def require(x,s):
 if not x:raise Error(s)
def dump(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def sha(p):return world.sha(p)
def fsyncdir(p):
 if os.name!='nt':
  fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
def atomic(p,value):
 p=Path(p);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True);require(not p.is_symlink(),'Symlink state path refused')
 tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('xb')as f:
  if os.name!='nt':os.chmod(tmp,0o600)
  f.write(dump(value));f.flush();os.fsync(f.fileno())
 os.replace(tmp,p);fsyncdir(p.parent)
def load(p,limit=65536):
 p=Path(p);require(p.is_file()and not p.is_symlink()and p.stat().st_size<=limit,'Missing/unsafe/oversize JSON')
 return json.loads(p.read_bytes())
@contextlib.contextmanager
def operation(root):
 root.mkdir(mode=0o700,parents=True,exist_ok=True);p=root/'operation.lock';require(not p.is_symlink(),'Unsafe local lock')
 with p.open('a+b')as f:
  if f.tell()==0:f.write(b'0');f.flush()
  f.seek(0)
  try:
   if os.name=='nt':
    import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:raise Error('Another local operation/supervisor owns this world')from None
  try:yield
  finally:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)
def valid_control(d):
 require(type(d)is dict and type(d.get('format'))is int and d['format']==1 and type(d.get('revision'))is int and d['revision']>=0,'Unknown remote control format')
 require(set(d)=={'format','revision','current','lease'},'Unknown control fields')
 c=d['current']
 if c is not None:require(type(c)is dict and set(c)=={'tag','manifest_sha256'}and TAG.fullmatch(c.get('tag',''))and HEX.fullmatch(c.get('manifest_sha256','')),'Invalid current')
 l=d['lease']
 if l is not None:require(type(l)is dict and set(l)=={'owner','phase'}and TOKEN.fullmatch(l.get('owner',''))and l.get('phase')in('active','uploading'),'Invalid lease')
 return d

class GitHub:
 """Every subprocess uses the existing gh credential helper; stderr is not logged."""
 def __init__(self,repo,branch='main',gh='gh'):
  require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo)is not None,'Use OWNER/PRIVATE_REPO')
  require(re.fullmatch(r'[A-Za-z0-9_.-]+',branch)is not None,'Simple metadata branch required')
  self.repo=repo;self.branch=branch;self.gh=gh;self.prefix='repos/'+repo
  info=self.api('GET',self.prefix)
  require(info.get('private')is True and not info.get('archived'),'Transport requires a PRIVATE writable repository')
  require(info.get('default_branch')==branch,'Use the private repository default branch for initial metadata')
 def api(self,method,path,data=None,missing=False):
  args=[self.gh,'api','--hostname','github.com','--include','--method',method,path,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2026-03-10']
  if data is not None:args+=['--input','-']
  for attempt in range(3):
   r=subprocess.run(args,input=dump(data)if data is not None else None,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
   raw=r.stdout;parts=re.split(rb'\r?\n\r?\n',raw,maxsplit=1);status=re.match(rb'HTTP/\S+\s+(\d+)',parts[0])
   # Only a failed GET with no response can be retried; never replay mutations.
   if method=='GET'and r.returncode and not raw and status is None and attempt<2:
    time.sleep(attempt+1);continue
   break
  require(status is not None,'gh did not return an HTTP status; authentication/network may be unavailable')
  code=int(status[1])
  if code==404 and missing:return None
  if r.returncode or not 200<=code<300:raise HTTP(code)
  body=parts[1]if len(parts)>1 else b'';require(len(body)<4*1024**2,'Oversize API response')
  return json.loads(body)if body.strip()else None
 def get(self):
  obj=self.api('GET',self.prefix+'/contents/lab-control.json?ref='+self.branch,missing=True)
  if obj is None:return None,None
  require(obj.get('type')=='file'and obj.get('encoding')=='base64'and obj.get('size',65537)<=65536,'Invalid control object')
  raw=base64.b64decode(obj['content']);require(len(raw)<=65536,'Oversize control');return valid_control(json.loads(raw)),obj['sha']
 def cas(self,expected,value):
  valid_control(value);payload={'message':'personal lab state transition','content':base64.b64encode(dump(value)).decode(),'branch':self.branch,'author':IDENTITY,'committer':IDENTITY}
  if expected is not None:payload['sha']=expected
  else:payload.pop('branch') # First explicit noreply commit uses repo default branch, even when empty.
  return self.api('PUT',self.prefix+'/contents/lab-control.json',payload)['content']['sha']
 def release(self,tag,create_owner=None):
  require(TAG.fullmatch(tag),'Invalid release generation')
  # Draft releases are intentionally used: immutable-release protection starts
  # on publication. A partial draft must remain discoverable on retry.
  found=None
  for page in range(1,101):
   rows=self.api('GET',self.prefix+'/releases?per_page=100&page='+str(page))
   matches=[x for x in rows if x.get('tag_name')==tag];require(len(matches)<2,'Duplicate release tags')
   if matches:found=matches[0];break
   if len(rows)<100:break
  else:raise Error('Release listing budget exceeded')
  if found is None and create_owner:
   found=self.api('POST',self.prefix+'/releases',{'tag_name':tag,'name':tag,'body':'personal-lab-v1:'+create_owner,'draft':True,'prerelease':True,'target_commitish':self.branch})
  require(found is not None,'Generation release not found')
  if create_owner:require(found.get('body')=='personal-lab-v1:'+create_owner,'Release belongs to another operation')
  return found
 def assets(self,release):
  result=[]
  for page in range(1,12):
   rows=self.api('GET',self.prefix+'/releases/'+str(release['id'])+'/assets?per_page=100&page='+str(page));result+=rows
   if len(rows)<100:return result
  raise Error('Release asset budget exceeded')
 def download(self,asset,destination):
  require(type(asset.get('id'))is int,'Invalid asset id')
  destination=Path(destination);require(not destination.exists(),'Download destination exists')
  with destination.open('xb')as f:
   r=subprocess.run([self.gh,'api','--hostname','github.com',self.prefix+'/releases/assets/'+str(asset['id']),'-H','Accept: application/octet-stream'],stdout=f,stderr=subprocess.DEVNULL)
   f.flush();os.fsync(f.fileno())
  require(r.returncode==0,'Download failed; partial retained')
 def upload(self,release,path):
  path=Path(path);require('#'not in str(path),'gh label delimiter is forbidden in transport path')
  r=subprocess.run([self.gh,'release','upload',release['tag_name'],str(path),'--repo','github.com/'+self.repo],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  require(r.returncode==0,'Upload failed/ambiguous; pending retained; retry reconciles remote assets')
 def discard_starter(self,release,asset):
  require(release.get('draft')is True and asset.get('state')=='starter'and asset.get('size')==0,'Only this owned draft empty starter can be removed')
  self.api('DELETE',self.prefix+'/releases/assets/'+str(asset['id']))
 def publish(self,release):
  if release.get('draft'):self.api('PATCH',self.prefix+'/releases/'+str(release['id']),{'draft':False,'make_latest':'false'})

class Transport:
 def __init__(self,root,backend):self.root=Path(root).resolve();self.backend=backend;self.file=self.root/'handoff.json'
 def read(self):return load(self.file)
 def save(self,s):atomic(self.file,s)
 def init(self):
  d,rev=self.backend.get();require(d is None,'Remote control already exists')
  self.backend.cas(None,{'format':1,'revision':0,'current':None,'lease':None})
 def acquire(self,s):
  d,rev=self.backend.get();require(d is not None,'Run instructor init first');valid_control(d)
  if d['lease'] is not None:
   require(d['lease']['owner']==s['token'],'World leased elsewhere; no TTL takeover')
   require(d['current']==s.get('base'),'Remote generation changed under retained lease');return d
  require(s['phase']=='acquiring','Lease unexpectedly absent; no stale local boot/upload')
  s['base']=d['current'];self.save(s) # Durable intent BEFORE CAS, recoverable after lost reply.
  changed=dict(d,revision=d['revision']+1,lease={'owner':s['token'],'phase':'active'})
  try:self.backend.cas(rev,changed)
  except Error:
   now,_=self.backend.get()
   if now!=changed:raise
  return changed
 def new(self):
  if self.file.exists():require(self.read()['phase']=='synced','Retained operation exists; use status/retry, never overwrite it')
  s={'format':1,'token':uuid.uuid4().hex,'phase':'acquiring','base':None,'created':time.time()};self.save(s);self.acquire(s);return s
 def owns(self,s):
  d,rev=self.backend.get();require(d is not None and d['lease']is not None and d['lease']['owner']==s['token']and d['current']==s['base'],'Exclusive lease/current mismatch; no automatic takeover')
  return d,rev
 def phase(self,s,phase,**fields):s.update(phase=phase,**fields);self.save(s)
 def check_manifest(self,m,current):
  require(type(m)is dict and type(m.get('format'))is int and m['format']==1 and m.get('generation')==current['tag'],'Invalid generation manifest')
  world.valid_config(m['config']);require(m.get('cold')in('qmp-guest-shutdown','operator-asserted-initial-only'),'No named cold provenance')
  require(type(m.get('bytes'))is int and 0<m['bytes']<=160*1024**3 and HEX.fullmatch(m.get('sha256','')),'Invalid disk descriptor')
  parts=m.get('parts');require(type(parts)is list and 0<len(parts)<=998,'Invalid part count')
  for i,p in enumerate(parts):
   require(type(p)is dict and set(p)=={'name','bytes','sha256'}and p['name']=='disk-%04d.part'%i and type(p['bytes'])is int and 0<p['bytes']<=CHUNK and HEX.fullmatch(p.get('sha256','')),'Invalid part')
  require(sum(x['bytes']for x in parts)==m['bytes']and all(x['bytes']==CHUNK for x in parts[:-1]),'Part total/chunk layout mismatch');access_validate(m['access']);return m
 def fetch(self,s):
  self.owns(s);current=s['base'];require(current is not None,'No verified initial VM exists; instructor seed is required')
  folder=self.root/'downloads'/current['tag'];folder.mkdir(parents=True,exist_ok=True)
  release=self.backend.release(current['tag']);require(not release.get('draft'),'Current must not refer to a draft')
  assets=self.backend.assets(release);names={x['name']:x for x in assets};require(len(names)==len(assets),'Duplicate asset names')
  require('manifest.json'in names,'Manifest asset missing')
  mpath=folder/'manifest.json';self.download_checked(names['manifest.json'],mpath,current['manifest_sha256'],None)
  m=self.check_manifest(load(mpath),current)
  require(set(names)=={'manifest.json',*[p['name']for p in m['parts']]},'Unexpected/missing generation assets')
  for i,p in enumerate(m['parts']):
   self.phase(s,'downloading',progress={'part':i+1,'of':len(m['parts'])});self.download_checked(names[p['name']],folder/p['name'],p['sha256'],p['bytes'])
  target=self.root/'worlds'/s['token'];target.mkdir(parents=True,exist_ok=True);disk=target/'active.qcow2'
  if not disk.exists():
   partial=target/('active.qcow2.partial-'+uuid.uuid4().hex)
   with partial.open('xb')as out:
    for p in m['parts']:
     with(folder/p['name']).open('rb')as f:shutil.copyfileobj(f,out,1024**2)
    out.flush();os.fsync(out.fileno())
   require(sha(partial)==m['sha256']and partial.stat().st_size==m['bytes'],'Assembled disk mismatch')
   os.replace(partial,disk);fsyncdir(target)
  require(sha(disk)==m['sha256'],'Existing local download changed; never overwrite it')
  world.independent_info(disk);image_check(disk)
  atomic(target/'world.json',{'schema':1,'world_id':m['world_id'],'config':m['config'],'active_disk':'active.qcow2','state':'transported'})
  self.phase(s,'ready',world=str(target),access=m['access']);return target
 def download_checked(self,asset,path,expected,size):
  path=Path(path)
  if path.exists():require(path.is_file()and not path.is_symlink()and sha(path)==expected and(size is None or path.stat().st_size==size),'Retained local asset differs; not overwritten');return
  require(size is None and asset.get('size',65537)<=65536 or size is not None and asset.get('size')==size,'Asset size mismatch')
  temp=path.with_name(path.name+'.partial-'+uuid.uuid4().hex);self.backend.download(asset,temp)
  require(sha(temp)==expected and(size is None or temp.stat().st_size==size),'Downloaded checksum mismatch; partial retained')
  os.replace(temp,path);fsyncdir(path.parent)
 def snapshot(self,s,source,cold):
  self.owns(s);require(cold in('qmp-guest-shutdown','operator-asserted-initial-only'),'Shutdown unconfirmed')
  if cold=='operator-asserted-initial-only':require(s['base']is None,'Manual assertion only permits first admission')
  source=Path(source);data=world.state(source);generation='world-'+s['token'];folder=self.root/'pending'/generation;folder.mkdir(parents=True,exist_ok=True)
  image=folder/'disk.qcow2';mfile=folder/'manifest.json'
  if mfile.exists():
   m=self.check_manifest(load(mfile),{'tag':generation});require(sha(image)==m['sha256'],'Pending image changed');self.phase(s,'pending',pending=str(folder));return folder
  # qemu-img is explicit-format and takes its own locks; no -U and no repair.
  world.independent_info(world.contained(source,data['active_disk']));image_check(world.contained(source,data['active_disk']))
  if not image.exists():
   captured=folder/('capture-'+uuid.uuid4().hex+'.qcow2');world.clone(world.contained(source,data['active_disk']),captured);os.replace(captured,image);fsyncdir(folder)
  image_check(image);parts=[]
  with image.open('rb')as f:
   i=0
   while chunk:=f.read(CHUNK):
    p=folder/('disk-%04d.part'%i)
    if p.exists():require(p.read_bytes()==chunk,'Pending part changed; not overwritten')
    else:
     partial=p.with_name(p.name+'.partial-'+uuid.uuid4().hex)
     with partial.open('xb')as out:out.write(chunk);out.flush();os.fsync(out.fileno())
     os.replace(partial,p);fsyncdir(folder)
    parts.append({'name':p.name,'bytes':len(chunk),'sha256':sha(p)});i+=1
  m={'format':1,'generation':generation,'world_id':data['world_id'],'config':data['config'],'cold':cold,'bytes':image.stat().st_size,'sha256':sha(image),'parts':parts,'access':s['access']}
  self.check_manifest(m,{'tag':generation});atomic(mfile,m);self.phase(s,'pending',pending=str(folder));return folder
 def owned_assets(self,s,release):
  self.owns(s);current=self.backend.release('world-'+s['token'],s['token'])
  require(type(current.get('id'))is int and current['id']>0 and type(release.get('id'))is int and current['id']==release['id']and current.get('tag_name')==release.get('tag_name')=='world-'+s['token']and current.get('body')=='personal-lab-v1:'+s['token'],'Owned generation release changed; current not advanced')
  assets=self.backend.assets(current);require(len({a['name']for a in assets})==len(assets),'Duplicate asset names')
  return assets
 def readback_checked(self,s,release,asset,p):
  require(type(asset.get('id'))is int and asset['id']>0,'Invalid read-back asset id')
  def remote_matches():
   found=next((a for a in self.owned_assets(s,release)if a.get('name')==p['name']),None)
   require(found is not None and type(found.get('id'))is int and found['id']==asset['id']and found.get('state')=='uploaded'and type(found.get('size'))is int and found['size']==p['bytes'],'Read-back asset changed/incomplete; current not advanced')
  remote_matches()
  repo=getattr(self.backend,'repo',None);require(type(repo)is str and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo),'Read-back cache requires the explicit repository identity')
  key={'format':1,'repo':repo,'release_id':release['id'],'generation':release['tag_name'],'owner':s['token'],'asset_id':asset['id'],'name':p['name'],'bytes':p['bytes'],'sha256':p['sha256']}
  verify=self.root/'verification';require(not verify.is_symlink(),'Unsafe verification directory');verify.mkdir(mode=0o700,exist_ok=True)
  cache=verify/'readback-v1';require(not cache.is_symlink(),'Unsafe read-back cache directory');cache.mkdir(mode=0o700,exist_ok=True)
  path=cache/(hashlib.sha256(dump(key)).hexdigest()+'.verified')
  require(not path.is_symlink(),'Unsafe read-back cache file')
  if path.exists():
   require(path.is_file()and path.stat().st_size==p['bytes']and sha(path)==p['sha256'],'Verified read-back cache changed; retained, current not advanced')
   remote_matches();return
  temp=cache/(path.name+'.partial-'+uuid.uuid4().hex);self.backend.download(asset,temp)
  require(temp.is_file()and not temp.is_symlink()and temp.stat().st_size==p['bytes']and sha(temp)==p['sha256'],'Remote read-back failed; partial retained, current not advanced')
  if os.name!='nt':os.chmod(temp,0o600)
  with temp.open('r+b')as f:f.flush();os.fsync(f.fileno())
  remote_matches();os.replace(temp,path);fsyncdir(cache)
 def upload_pending(self,s):
  folder=Path(s['pending']);mfile=folder/'manifest.json';m=self.check_manifest(load(mfile),{'tag':'world-'+s['token']})
  desired={'tag':m['generation'],'manifest_sha256':sha(mfile)}
  d,rev=self.backend.get()
  if d is not None and d['current']==desired:self.phase(s,'synced',published=desired,progress=None);return # Lost CAS reply; NEVER alter a subsequent owner's lease.
  d,rev=self.owns(s)
  changed=dict(d,revision=d['revision']+1,lease={'owner':s['token'],'phase':'uploading'})
  if d['lease']['phase']!='uploading':
   try:self.backend.cas(rev,changed)
   except Error:
    actual,_=self.backend.get();require(actual==changed,'Ambiguous uploading transition; retained')
  release=self.backend.release(m['generation'],s['token']);records=[*m['parts'],{'name':'manifest.json','bytes':mfile.stat().st_size,'sha256':sha(mfile)}]
  known={p['name']for p in records};verified=[]
  for i,p in enumerate(records):
   self.owns(s);local=folder/p['name'];require(local.is_file()and not local.is_symlink()and local.stat().st_size==p['bytes']and sha(local)==p['sha256'],'Pending bytes changed; no upload')
   assets=self.backend.assets(release);require(len({a['name']for a in assets})==len(assets)and all(a['name']in known for a in assets),'Unexpected assets in owned generation')
   found=next((a for a in assets if a['name']==p['name']),None)
   if found and found.get('state')=='starter'and found.get('size')==0:self.backend.discard_starter(release,found);found=None
   if found is None:self.backend.upload(release,local);assets=self.backend.assets(release);found=next((a for a in assets if a['name']==p['name']),None)
   require(found is not None and found.get('state')=='uploaded'and found.get('size')==p['bytes'],'Remote asset incomplete')
   self.phase(s,'uploading',progress={'part':i+1,'of':len(records),'verified':i})
   # A retained verification is reusable only after fresh remote/lease checks
   # and hashing its actual local bytes again, never by a server digest alone.
   self.readback_checked(s,release,found,p);verified.append((found['id'],p['name'],p['bytes'],'uploaded'))
  assets=self.owned_assets(s,release)
  require(len(assets)==len(verified)and all(type(a.get('id'))is int and type(a.get('size'))is int for a in assets)and {(a.get('id'),a.get('name'),a.get('size'),a.get('state'))for a in assets}==set(verified),'Verified generation asset set changed; current not advanced')
  self.backend.publish(release);d,rev=self.owns(s);new=dict(d,revision=d['revision']+1,current=desired,lease=None)
  try:self.backend.cas(rev,new)
  except Error:
   actual,_=self.backend.get();require(actual is not None and actual['current']==desired,'Publish CAS ambiguous; lease/pending retained')
  self.phase(s,'synced',published=desired,progress=None)

def image_check(path):world.call([world.tool('qemu-img'),'check','-f','qcow2',str(path)])
def cold_confirmed(events,exit_code):
 shutdowns=[e for e in events if e.get('event')=='SHUTDOWN']
 return exit_code==0 and bool(shutdowns)and shutdowns[-1].get('data',{}).get('guest')is True and shutdowns[-1]['data'].get('reason')=='guest-shutdown'and not any(e.get('event')in('GUEST_PANICKED','SUSPEND_DISK')for e in events)
def access_validate(a):
 require(type(a)is dict and set(a)=={'profile','role','services'}and a['role']=='student'and re.fullmatch(r'[a-z0-9-]{1,48}',a['profile']),'Invalid access profile')
 require(type(a['services'])is dict and set(a['services'])=={'ssh','rdp','vnc'},'Explicit service availability required')
 for name,v in a['services'].items():require(type(v)is bool,'Availability must be true/false')
 return a
def access_report(s):
 if s.get('phase')not in('running','stop-requested'):return {'status':'unavailable','reason':'VM not confirmed running; image/services may require setup'}
 a=access_validate(s['access']);root=Path(s['world']);cfg=world.state(root)['config'];require(re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',cfg.get('guest_ssh_user',''))and cfg.get('guest_ssh_user')!='root','Invalid non-root student account');result={'profile':a['profile'],'role':'student','availability':'configured endpoints; guest services may still be loading; no health probe','warning':'Only management/bastion guest is forwarded; hidden nodes have no host forwarding. Enforcement requires the prepared guest firewall/topology.'}
 result['ssh']=['ssh','-F',str(root/'ssh_config'),'-o','UserKnownHostsFile='+str(root/'known_hosts'),'-p',str(cfg['ssh_port']),cfg['guest_ssh_user']+'@127.0.0.1']if a['services']['ssh']else'setup-required'
 if isinstance(result['ssh'],list)and s.get('ssh_identity'):
  identity=Path(s['ssh_identity']).expanduser().resolve();require(identity.is_file(),'Configured student key is missing; not read or generated');result['ssh'][1:1]=['-i',str(identity),'-o','IdentitiesOnly=yes']
 result['rdp']='127.0.0.1:13389 (Linux desktop profile only)'if a['services']['rdp']else'setup-required'
 result['vnc']=['vncviewer','127.0.0.1::15901']if a['services']['vnc']else'setup-required';return result

def spawn_worker(config,verb):
 flags={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}if os.name=='nt'else{'start_new_session':True}
 return subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--config',str(config),verb],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,**flags).pid

def supervise(t,s,instructor_console=False,allow_network=False,timeout=120):
 """Own QEMU only. QMP is a private pipe, never a student TCP endpoint."""
 root=Path(s['world']);data=world.state(root)
 memory=world.available_mib();require(memory is None or memory>=data['config']['memory_mib']+768,'Insufficient free RAM; no other programs stopped')
 args=SimpleNamespace(accel='auto',installer=None,console='window',dry_run=False,allow_network=allow_network)
 command,_=world.qemu_args(root,data,args);command+=['-serial','none','-monitor','none','-qmp','stdio']
 if not instructor_console:command+=['-display','none']
 access_validate(s['access']);net=command.index('-netdev')+1
 for name,host,guest in [('rdp',13389,3389),('vnc',15901,5901)]:
  if s['access']['services'][name]:
   require(host!=data['config']['ssh_port'],'Forward ports collide');command[net]+=f',hostfwd=tcp:127.0.0.1:{host}-:{guest}'
 ssh_config=root/'ssh_config';require(not ssh_config.is_symlink(),'Own SSH config must not be a symlink')
 if not ssh_config.exists():ssh_config.touch(exist_ok=False) # Host config/known_hosts untouched.
 events=[];messages=queue.Queue();process=None;stop_id=None;deadline=None;caps=False;guest_ok=False;qmp_valid=True
 with world.locked(root):
  # Re-read under the existing world lock; no guest may be writing this image.
  fresh=world.state(root);require(fresh==data,'World changed before its lock');world.independent_info(world.contained(root,data['active_disk']))
  with(root/'qemu-stderr.log').open('ab')as stderr:
   t.phase(s,'starting')
   process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,bufsize=1)
   try:
    def reader():
     try:
      for line in iter(lambda:process.stdout.readline(65537),''):
       if len(line)>65536:messages.put({'protocol_error':True});continue
       try:messages.put(json.loads(line))
       except ValueError:messages.put({'protocol_error':True})
     finally:messages.put({'eof':True})
    reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start()
    def send(command,id):process.stdin.write(json.dumps({'execute':command,'id':id})+'\n');process.stdin.flush()
    # Keep the world lock until THIS child has exited, even after Ctrl-C or QMP
    # failure. No force kill, qmp quit, repair or implicit release follows.
    while process.poll()is None or not messages.empty():
     try:
      try:msg=messages.get(timeout=.2)
      except queue.Empty:msg={}
      if 'QMP'in msg:send('qmp_capabilities','capabilities')
      if msg.get('id')=='capabilities'and'return'in msg:caps=True;t.phase(s,'running')
      if msg.get('event'):events.append(msg)
      if msg.get('protocol_error'):
       qmp_valid=False;t.phase(s,'qmp-error-running',last_error='QMP parse failed; shutdown not certified')
      request=t.root/'stop.request.json'
      if caps and request.exists():
       r=load(request)
       if r.get('token')==s['token']and r.get('id')!=stop_id:
        require(TOKEN.fullmatch(r.get('id','')),'Invalid stop request');stop_id=r['id'];send('system_powerdown',stop_id);deadline=time.monotonic()+timeout;t.phase(s,'stop-requested')
      if msg.get('error'):t.phase(s,'shutdown-request-error',last_error='QMP command rejected; VM may still run')
      if deadline and time.monotonic()>deadline and process.poll()is None:t.phase(s,'shutdown-timeout',last_error='Guest did not shut down; no checkpoint/upload; use issued access or instructor recovery');deadline=None
     except KeyboardInterrupt:continue
     except (Error,OSError,ValueError):
      t.phase(s,'qmp-error-running',last_error='QMP/control failure; waiting for own child, no force stop or upload')
      # A broken pipe cannot certify any subsequent shutdown.
      guest_ok=False;caps=False;qmp_valid=False
    code=process.wait();reader_thread.join(timeout=5)
    while not messages.empty():
     tail=messages.get()
     if tail.get('event'):events.append(tail)
     if tail.get('protocol_error'):qmp_valid=False
    guest_ok=qmp_valid and not reader_thread.is_alive()and cold_confirmed(events,code)
    atomic(root/'shutdown-receipt.json',{'qemu_exit':code,'shutdown_events':[e for e in events if e.get('event')in('SHUTDOWN','GUEST_PANICKED','SUSPEND_DISK')],'confirmed':guest_ok})
    if not guest_ok:t.phase(s,'unclean',last_error='No observed guest-shutdown + exit0; active disk retained, no upload');return
    t.phase(s,'shutdown-observed')
    image_check(world.contained(root,data['active_disk']))
    t.phase(s,'cold',cold='qmp-guest-shutdown')
   finally:
    # Setup, thread allocation, state I/O and parsing may all fail. The old
    # world.lock must outlive this child, even when no QMP reader was started.
    while process.poll()is None:
     try:process.wait(timeout=.5)
     except (subprocess.TimeoutExpired,KeyboardInterrupt):continue
  # Snapshot is immutable from this point, still under the world lock.
  t.snapshot(s,root,'qmp-guest-shutdown')
 t.upload_pending(s)

def wait_supervisor(t,seconds=5):
 deadline=time.monotonic()+seconds
 while True:
  s=t.read()
  if s['phase']not in('ready','starting')or time.monotonic()>=deadline:return s
  time.sleep(.1)

def config_load(path):
 c=load(path);require(type(c)is dict and set(c)-{'ssh_identity'}=={'format','repo','branch','root','instructor_console','allow_network'}and type(c['format'])is int and c['format']==1,'Invalid protected config schema')
 require(type(c['instructor_console'])is bool and type(c['allow_network'])is bool,'Explicit lifecycle/network boolean required')
 root=Path(c['root']).expanduser().resolve();require(str(root)!=str(Path.home().resolve())and root!=Path(root.anchor),'Select a dedicated own state directory')
 return c,root

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path.home()/'.personal-lab/config.json')
 sub=p.add_subparsers(dest='action',required=True)
 for verb in ('init','start','stop','retry','access','vnc','_run','_retry'):sub.add_parser(verb)
 status=sub.add_parser('status');status.add_argument('--remote',action='store_true')
 seed=sub.add_parser('seed');seed.add_argument('world',type=Path);seed.add_argument('--guest-stopped',action='store_true');seed.add_argument('--accept-initial-image',action='store_true');seed.add_argument('--access',type=Path,required=True)
 a=p.parse_args(argv);cfg,root=config_load(a.config);file=root/'handoff.json'
 if a.action in('status','access','vnc','stop'):
  s=load(file)if file.exists()else{'phase':'uninitialized'}
  if a.action=='status':
   result={k:s[k]for k in('phase','created','progress','last_error','published')if k in s}
   if a.remote:
    backend=GitHub(cfg['repo'],cfg['branch']);d,_=backend.get();result['remote']=None if d is None else{'current':d['current'],'lease':None if d['lease']is None else{'phase':d['lease']['phase'],'owned_here':d['lease']['owner']==s.get('token')}}
   print(json.dumps(result,ensure_ascii=False,indent=2));return 0
  if a.action=='stop':
   require(s.get('phase')in('running','stop-requested','shutdown-timeout','shutdown-request-error'),'No supervised running guest; inspect status; no guessed poweroff')
   atomic(root/'stop.request.json',{'token':s['token'],'id':uuid.uuid4().hex});print('Выключение запрошено. Загрузка ещё НЕ подтверждена; lab status покажет результат.');return 0
  result=access_report(s)
  if a.action=='access':print(json.dumps(result,ensure_ascii=False,indent=2));return 0
  require(isinstance(result.get('vnc'),list),'VNC unavailable/setup-required for this assignment')
  viewer=shutil.which(result['vnc'][0]);require(viewer is not None,'VNC viewer not installed; nothing installed automatically');subprocess.Popen([viewer,*result['vnc'][1:]]);return 0
 backend=GitHub(cfg['repo'],cfg['branch']);t=Transport(root,backend);launch=None
 with operation(root):
  if a.action=='init':t.init();print('Private metadata initialized; VM image is still setup-required.');return 0
  if a.action=='seed':
   require(a.guest_stopped and a.accept_initial_image,'Initial seed requires explicit operator cold/image acceptance; not automatic shutdown proof')
   d,_=backend.get();require(d is not None and d['current']is None,'Seed only permits the first accepted image')
   s=t.read()if file.exists()else t.new();require(s['phase']=='acquiring','Pending operation already exists');t.acquire(s);s['access']=access_validate(load(a.access));s['world']=str(a.world.expanduser().resolve());s['cold']='operator-asserted-initial-only';t.phase(s,'cold')
   with world.locked(Path(s['world'])):t.snapshot(s,s['world'],s['cold'])
   launch='_retry'
  elif a.action=='start':
   d,_=backend.get();require(d is not None and d['current']is not None,'No accepted VM image yet: setup-required, no start or lease acquired')
   world.tool('qemu-img');world.tool('qemu-system-x86_64')
   s=t.new();s['ssh_identity']=cfg.get('ssh_identity');t.save(s);t.fetch(s);launch='_run'
  elif a.action in('retry','_retry'):
   s=t.read()
   if a.action=='retry':launch='_retry'
   elif s['phase']in('pending','uploading'):t.upload_pending(s)
   elif s['phase']=='cold':
    with world.locked(Path(s['world'])):t.snapshot(s,s['world'],s['cold'])
    t.upload_pending(s)
   elif s['phase']in('acquiring','downloading','ready'):
    t.acquire(s);t.fetch(s);launch='_run'
   elif s['phase']=='synced':pass
   else:raise Error('VM may still be active/unclean; retry cannot bypass shutdown/lease')
  elif a.action=='_run':
   s=t.read();require(s['phase']=='ready','No verified ready image');t.owns(s);supervise(t,s,cfg['instructor_console'],cfg['allow_network'])
 # Release operation lock before a child can acquire it; phase/token already durable.
 if launch:
  pid=spawn_worker(a.config.resolve(),launch);print('Собственный фоновый процесс:',pid,'; состояние: lab status. Пока не synced, другой ПК заблокирован.')
  view=wait_supervisor(t)if launch=='_run'else t.read()
  print(json.dumps(access_report(view),ensure_ascii=False,indent=2))
  if view['phase']in('ready','starting'):print('Supervisor ещё запускается. Повторите lab access; доступ служб пока не подтверждён.')
 return 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except (Error,world.LabError,OSError,ValueError,KeyError,TypeError,RuntimeError)as e:
  # Never dump gh stderr or environment. Preserve state and lease on failure.
  try:
   if any(v in sys.argv for v in('_run','_retry')):
    parsed=argparse.ArgumentParser(add_help=False);parsed.add_argument('--config',type=Path,default=Path.home()/'.personal-lab/config.json');args,_=parsed.parse_known_args();c,r=config_load(args.config);state=load(r/'handoff.json');state['last_error']=str(e);atomic(r/'handoff.json',state)
  except Exception:pass
  print('LAB:',str(e),file=sys.stderr);raise SystemExit(2)
