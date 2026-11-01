"""Fake API / own TEMP only. Fake disk bytes are NOT qcow2 or a booted VM."""
import base64,copy,importlib.util,io,json,os,subprocess,sys,tempfile,threading,unittest,uuid
from pathlib import Path
from unittest.mock import patch
VM=Path(__file__).resolve().parents[1]/'vm';sys.path.insert(0,str(VM))
import lab as L

class Fake:
 def __init__(self):self.control={'format':1,'revision':0,'current':None,'lease':None};self.sha='0';self.releases={};self.lock=threading.Lock();self.assets_by_id={};self.next=1;self.fail_after_upload=False;self.corrupt=False;self.lose_cas=False;self.fail_before_cas=False;self.barrier=None;self.deletions=[]
 def get(self):
  with self.lock:r=copy.deepcopy(self.control),self.sha
  if self.barrier:self.barrier.wait(timeout=5)
  return r
 def cas(self,expected,value):
  with self.lock:
   if self.fail_before_cas:self.fail_before_cas=False;raise L.Error('network before CAS')
   if expected!=self.sha:raise L.HTTP(409)
   self.control=copy.deepcopy(value);self.sha=str(int(self.sha)+1)
   if self.lose_cas:self.lose_cas=False;raise L.Error('reply lost after commit')
   return self.sha
 def release(self,tag,create_owner=None):
  if tag not in self.releases:
   if not create_owner:raise L.Error('missing release')
   self.releases[tag]={'id':len(self.releases)+1,'tag_name':tag,'draft':True,'body':'personal-lab-v1:'+create_owner,'items':[]}
  r=self.releases[tag]
  if create_owner:L.require(r['body']=='personal-lab-v1:'+create_owner,'foreign release')
  return r
 def assets(self,release):return copy.deepcopy(release['items'])
 def add(self,r,name,data,state='uploaded'):
  asset={'id':self.next,'name':name,'size':len(data),'state':state};self.next+=1;r['items'].append(asset);self.assets_by_id[asset['id']]=bytes(data);return asset
 def upload(self,release,path):
  L.require(not any(a['name']==Path(path).name for a in release['items']),'duplicate asset')
  self.add(release,Path(path).name,Path(path).read_bytes())
  if self.fail_after_upload:self.fail_after_upload=False;raise L.Error('lost upload reply')
 def download(self,a,destination):Path(destination).write_bytes(self.assets_by_id[a['id']]+(b'bad'if self.corrupt else b''))
 def discard_starter(self,r,a):
  L.require(r['draft']and a['state']=='starter'and a['size']==0,'foreign deletion');r['items']=[x for x in r['items']if x['id']!=a['id']];self.deletions.append(a['id'])
 def publish(self,r):r['draft']=False

class TransportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='personal-transport-own-');self.base=Path(self.temp.name);self.api=Fake();self.t=L.Transport(self.base/'pc-A',self.api)
  self.access={'profile':'bastion-student','role':'student','services':{'ssh':False,'rdp':False,'vnc':False}}
  self.world=self.base/'existing own VM';self.world.mkdir();self.disk=self.world/'active.qcow2';self.disk.write_bytes(b'FAKE COLD DISK, NOT QCOW2\n')
  config=json.loads((VM/'world.example.json').read_text());L.atomic(self.world/'world.json',{'schema':1,'world_id':str(uuid.uuid4()),'config':config,'active_disk':'active.qcow2','state':'own-test'})
  self.patches=[patch.object(L,'CHUNK',8),patch.object(L.world,'independent_info',self.info),patch.object(L,'image_check',lambda p:None),patch.object(L.world,'clone',self.clone)]
  for p in self.patches:p.start()
  self.addCleanup(self.temp.cleanup);self.addCleanup(lambda:[p.stop()for p in reversed(self.patches)])
 def info(self,p):self.assertTrue(Path(p).is_file());return {'format':'qcow2'}
 def clone(self,s,d):self.assertFalse(Path(d).exists());Path(d).parent.mkdir(parents=True,exist_ok=True);Path(d).write_bytes(Path(s).read_bytes())
 def pending(self):
  s=self.t.new();s['access']=copy.deepcopy(self.access);s['world']=str(self.world);self.t.snapshot(s,self.world,'operator-asserted-initial-only');return s
 def synced(self):s=self.pending();self.t.upload_pending(s);return s
 def test_two_concurrent_CAS_starts_only_one_wins(self):
  barrier=threading.Barrier(2);old_get=self.api.get;first=threading.local()
  def get():
   r=old_get()
   if not getattr(first,'done',False):first.done=True;barrier.wait(timeout=5)
   return r
  results=[]
  def run(i):
   t=L.Transport(self.base/('pc-'+str(i)),self.api);s={'format':1,'token':uuid.uuid4().hex,'phase':'acquiring','base':None}
   try:t.acquire(s);results.append('acquired')
   except L.Error:results.append('blocked')
  with patch.object(self.api,'get',get):
   threads=[threading.Thread(target=run,args=(i,))for i in range(2)]
   for t in threads:t.start()
   for t in threads:t.join(6);self.assertFalse(t.is_alive())
  self.assertCountEqual(results,['acquired','blocked'])
 def test_no_TTL_takeover(self):
  s=self.t.new();other=L.Transport(self.base/'pc-B',self.api)
  with patch.object(L.time,'time',return_value=10**20),self.assertRaises(L.Error):other.new()
  self.assertEqual(self.api.control['lease']['owner'],s['token'])
 def test_acquire_reply_lost_reconciles_owned_lease(self):
  self.api.lose_cas=True;s=self.t.new();self.assertEqual(self.api.control['lease']['owner'],s['token']);self.assertEqual(self.t.read()['token'],s['token'])
 def test_failure_before_acquire_leaves_durable_intent_retry(self):
  self.api.fail_before_cas=True
  with self.assertRaises(L.Error):self.t.new()
  s=self.t.read();self.assertEqual(s['phase'],'acquiring');self.assertIsNone(self.api.control['lease']);self.t.acquire(s);self.assertEqual(self.api.control['lease']['owner'],s['token'])
 def test_current_waits_for_all_assets_readback_and_keeps_lease(self):
  s=self.pending();self.api.fail_after_upload=True
  with self.assertRaises(L.Error):self.t.upload_pending(s)
  self.assertIsNone(self.api.control['current']);self.assertEqual(self.api.control['lease']['phase'],'uploading');self.assertEqual(self.disk.read_bytes(),b'FAKE COLD DISK, NOT QCOW2\n')
  with self.assertRaises(L.Error):L.Transport(self.base/'pc-B',self.api).new()
  self.t.upload_pending(s);self.assertEqual(s['phase'],'synced');self.assertIsNone(self.api.control['lease']);self.assertTrue(Path(s['pending']).is_dir());self.assertFalse(self.api.release(s['published']['tag'])['draft'])
 def test_failed_readback_retains_current_and_retry(self):
  s=self.pending();self.api.corrupt=True
  with self.assertRaises(L.Error):self.t.upload_pending(s)
  self.assertIsNone(self.api.control['current']);self.assertIsNotNone(self.api.control['lease']);self.api.corrupt=False;self.t.upload_pending(s);self.assertEqual(s['phase'],'synced')
 def test_cas_publish_lost_reply_then_new_owner_not_released(self):
  s=self.pending();original=self.api.cas
  def lose_final(expected,value):
   if value['current']is not None:self.api.lose_cas=True
   return original(expected,value)
  with patch.object(self.api,'cas',lose_final):self.t.upload_pending(s)
  other=L.Transport(self.base/'pc-B',self.api).new();self.t.upload_pending(s);self.assertEqual(self.api.control['lease']['owner'],other['token'])
 def test_starter_only_owned_draft_is_removed(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);a=self.api.add(r,'disk-0000.part',b'','starter');self.t.upload_pending(s);self.assertEqual(self.api.deletions,[a['id']])
 def test_unknown_or_wrong_uploaded_asset_is_not_deleted(self):
  for kind in('foreign','mismatch'):
   with self.subTest(kind=kind):
    self.api=Fake();self.t=L.Transport(self.base/kind,self.api);s=self.pending();r=self.api.release('world-'+s['token'],s['token']);self.api.add(r,'foreign.bin'if kind=='foreign'else'disk-0000.part',b'WRONG')
    with self.assertRaises(L.Error):self.t.upload_pending(s)
    self.assertFalse(self.api.deletions);self.assertIsNone(self.api.control['current'])
 def test_complete_fetch_reassembles_new_target_old_world_unchanged(self):
  s=self.synced();old=self.disk.read_bytes();other=L.Transport(self.base/'pc-B',self.api);n=other.new();target=other.fetch(n);self.assertEqual((target/'active.qcow2').read_bytes(),old);self.assertEqual(self.disk.read_bytes(),old);self.assertNotEqual(target,self.world)
  self.assertTrue(all(not Path(p['name']).is_absolute()for p in L.load(Path(s['pending'])/'manifest.json')['parts']))
 def test_manifest_bad_hash_no_boot_overwrite_or_current_change(self):
  self.synced();cur=copy.deepcopy(self.api.control['current']);cur['manifest_sha256']='0'*64;self.api.control['current']=cur;other=L.Transport(self.base/'pc-B',self.api);n=other.new()
  with self.assertRaises(L.Error):other.fetch(n)
  self.assertEqual(other.read()['phase'],'acquiring');self.assertEqual(self.api.control['current'],cur);self.assertFalse((other.root/'worlds').exists())
 def test_corrupt_part_kept_and_never_assembled(self):
  s=self.synced();r=self.api.release(s['published']['tag']);part=next(a for a in r['items']if a['name']=='disk-0000.part');self.api.assets_by_id[part['id']]=b'bad';other=L.Transport(self.base/'pc-B',self.api);n=other.new()
  with self.assertRaises(L.Error):other.fetch(n)
  self.assertFalse((other.root/'worlds').exists());self.assertTrue(list((other.root/'downloads').rglob('*.partial-*')))
 def test_traversal_names_and_oversize_parts_rejected(self):
  s=self.pending();m=L.load(Path(s['pending'])/'manifest.json')
  for change in({'name':'../outside'},{'bytes':L.CHUNK+1},{'bytes':True}):
   bad=copy.deepcopy(m);bad['parts'][0].update(change)
   with self.assertRaises(L.Error):self.t.check_manifest(bad,{'tag':m['generation']})
  m['format']=True
  with self.assertRaises(L.Error):self.t.check_manifest(m,{'tag':m['generation']})
 def test_snapshot_manual_assertion_cannot_replace_later_generation(self):
  self.synced();n=self.t.new();n['access']=self.access
  with self.assertRaises(L.Error):self.t.snapshot(n,self.world,'operator-asserted-initial-only')
 def test_completed_manifest_recovers_after_local_phase_write_was_lost(self):
  s=self.pending();folder=Path(s['pending']);s.pop('pending');s['phase']='cold';self.t.save(s)
  self.t.snapshot(s,self.world,'operator-asserted-initial-only');self.assertEqual(s['phase'],'pending');self.assertEqual(s['pending'],str(folder));self.t.upload_pending(s);self.assertEqual(s['phase'],'synced')
 def test_interrupted_part_write_retains_partial_and_retry_succeeds(self):
  s=self.t.new();s['access']=self.access;s['world']=str(self.world);self.t.phase(s,'cold',cold='operator-asserted-initial-only');original=Path.open
  class Interrupted:
   def __init__(self,file):self.file=file
   def __enter__(self):return self
   def __exit__(self,*args):self.file.close()
   def write(self,data):self.file.write(data[:2]);raise OSError('own injected short write')
  def opened(path,*args,**kw):
   file=original(path,*args,**kw)
   return Interrupted(file)if '.part.partial-'in path.name and args==('xb',)else file
  with patch.object(Path,'open',opened),self.assertRaises(OSError):self.t.snapshot(s,self.world,'operator-asserted-initial-only')
  folder=self.t.root/'pending'/('world-'+s['token']);self.assertTrue(list(folder.glob('*.part.partial-*')));self.assertFalse((folder/'disk-0000.part').exists())
  self.t.snapshot(s,self.world,'operator-asserted-initial-only');self.t.upload_pending(s);self.assertEqual(s['phase'],'synced');self.assertTrue(list(folder.glob('*.part.partial-*')))
 def test_pending_mutation_prevents_upload_and_current_advance(self):
  s=self.pending();(Path(s['pending'])/'disk-0000.part').write_bytes(b'changed')
  with self.assertRaises(L.Error):self.t.upload_pending(s)
  self.assertIsNone(self.api.control['current'])
 def test_local_operation_lock_excludes_another_caller(self):
  with L.operation(self.t.root):
   with self.assertRaises(L.Error):
    with L.operation(self.t.root):self.fail('second local owner')
 def test_shutdown_event_and_exit_must_both_match(self):
  good={'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}
  self.assertTrue(L.cold_confirmed([good],0))
  for events,code in [([],0),([good],1),([{'event':'POWERDOWN'}],0),([{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-reset'}}],0),([{'event':'SHUTDOWN','data':{'guest':False,'reason':'host-ui'}}],0),([good,{'event':'SHUTDOWN','data':{'guest':False,'reason':'host-signal'}}],0),([good,{'event':'GUEST_PANICKED'}],0)]:self.assertFalse(L.cold_confirmed(events,code))
 def test_unprepared_access_never_invents_working_endpoints(self):
  s={'phase':'ready','world':str(self.world),'access':self.access};self.assertEqual(L.access_report(s)['status'],'unavailable');s['phase']='running';a=L.access_report(s);self.assertEqual(a['ssh'],'setup-required');self.assertEqual(a['rdp'],'setup-required');self.assertEqual(a['vnc'],'setup-required')
 def test_issued_access_only_loopback_no_host_config(self):
  s={'phase':'running','world':str(self.world),'access':copy.deepcopy(self.access)};s['access']['services']={k:True for k in('ssh','rdp','vnc')};a=L.access_report(s);self.assertIn('UserKnownHostsFile='+str(self.world/'known_hosts'),a['ssh']);self.assertIn('127.0.0.1',a['ssh'][-1]);self.assertEqual(a['vnc'],['vncviewer','127.0.0.1::15901']);self.assertIn('Linux',a['rdp'])
 def test_stop_does_not_require_network_or_print_synced(self):
  cfg=self.base/'config.json';L.atomic(cfg,{'format':1,'repo':'owner/private','branch':'main','root':str(self.t.root),'instructor_console':False,'allow_network':False});s=self.t.new();s['phase']='running';s['world']=str(self.world);self.t.save(s)
  with patch.object(L,'GitHub',side_effect=AssertionError('No network allowed')),patch('sys.stdout',new_callable=io.StringIO)as output:self.assertEqual(L.main(['--config',str(cfg),'stop']),0)
  self.assertNotIn('синхронизировано',output.getvalue());self.assertEqual(L.load(self.t.root/'stop.request.json')['token'],s['token'])
 def supervised(self,events,code=0,protocol='',hold_until_wait=False):
  s=self.t.new();s.update(world=str(self.world),access=copy.deepcopy(self.access),phase='ready');self.t.save(s)
  L.atomic(self.t.root/'stop.request.json',{'token':s['token'],'id':uuid.uuid4().hex})
  test=self
  text=''.join(json.dumps(e)+'\n'for e in [{'QMP':{}},{'return':{},'id':'capabilities'},*events])+protocol
  class Child:
   def __init__(self):self.pid=999999;self.stdout=io.StringIO(text);self.stdin=io.StringIO();self.polls=0;self.waited=False
   def poll(self):self.polls+=1;return None if hold_until_wait and not self.waited or self.polls<3 else code
   def wait(self,timeout=None):test.assertTrue((test.world/'world.lock').exists());self.polls=3;self.waited=True;return code
  child=Child();seen=[]
  def launch(args,**kw):seen.append(args);return child
  args=['qemu-system-x86_64','-no-reboot','-netdev','user,id=management,restrict=on,ipv6=off,hostfwd=tcp:127.0.0.1:2222-:22']
  self.last_launches=seen
  with patch.object(L.world,'available_mib',return_value=4096),patch.object(L.world,'qemu_args',return_value=(args,1024)),patch.object(L.subprocess,'Popen',launch):L.supervise(self.t,s)
  return s,child,seen
 def test_supervisor_actual_adapter_only_confirmed_guest_shutdown_uploads(self):
  s,child,args=self.supervised([{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}])
  self.assertEqual(s['phase'],'synced');self.assertIn('-qmp',args[0]);self.assertEqual(args[0][args[0].index('-qmp')+1],'stdio');self.assertEqual(args[0][args[0].index('-display')+1],'none');self.assertNotIn('tap',' '.join(args[0]));self.assertNotIn('0.0.0.0',' '.join(args[0]));self.assertTrue(L.load(self.world/'shutdown-receipt.json')['confirmed']);self.assertIn('system_powerdown',child.stdin.getvalue());self.assertFalse((self.world/'world.lock').exists())
 def test_supervisor_disk_suspend_is_not_full_shutdown_and_keeps_evidence(self):
  events=[{'event':'SUSPEND_DISK'},{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}]
  original=self.disk.read_bytes();s,_,_=self.supervised(events)
  self.assertEqual(s['phase'],'unclean');self.assertFalse(self.api.releases);self.assertIsNone(self.api.control['current']);self.assertEqual(self.api.control['lease']['owner'],s['token'])
  self.assertEqual(self.disk.read_bytes(),original);self.assertFalse((self.t.root/'pending').exists())
  receipt=L.load(self.world/'shutdown-receipt.json');self.assertFalse(receipt['confirmed']);self.assertEqual(receipt['shutdown_events'],events)
 def test_disk_suspend_rejects_both_event_orders_but_normal_shutdown_still_matches(self):
  good={'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}
  for events in ([{'event':'SUSPEND_DISK'},good],[good,{'event':'SUSPEND_DISK'}]):
   with self.subTest(events=events):self.assertFalse(L.cold_confirmed(events,0))
  self.assertTrue(L.cold_confirmed([good],0))
 def test_supervisor_host_window_close_never_copies_or_uploads(self):
  original=self.disk.read_bytes();s,_,_=self.supervised([{'event':'SHUTDOWN','data':{'guest':False,'reason':'host-ui'}}])
  self.assertEqual(s['phase'],'unclean');self.assertFalse(self.api.releases);self.assertIsNotNone(self.api.control['lease']);self.assertEqual(self.disk.read_bytes(),original);self.assertFalse((self.t.root/'pending').exists())
 def test_supervisor_protocol_error_cannot_be_masked_by_shutdown_event(self):
  s,_,_=self.supervised([{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}],protocol='not-json\n');self.assertEqual(s['phase'],'unclean');self.assertFalse(self.api.releases)
 def test_supervisor_nonzero_child_exit_does_not_publish(self):
  s,_,_=self.supervised([{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}],code=1);self.assertEqual(s['phase'],'unclean');self.assertFalse(self.api.releases)
 def test_supervisor_qcow_check_failure_keeps_shutdown_observed_phase(self):
  calls=[]
  def reject(path):calls.append(path);raise L.Error('qcow validation refused')
  with patch.object(L,'image_check',reject),self.assertRaises(L.Error):self.supervised([{'event':'SHUTDOWN','data':{'guest':True,'reason':'guest-shutdown'}}])
  self.assertEqual(self.t.read()['phase'],'shutdown-observed');self.assertFalse(self.api.releases);self.assertIsNotNone(self.api.control['lease'])
 def test_supervisor_state_setup_failure_occurs_before_child_launch(self):
  actual=self.t.phase
  def failed(s,phase,**fields):
   if phase=='starting':raise OSError('own injected starting state failure')
   return actual(s,phase,**fields)
  with patch.object(self.t,'phase',failed),self.assertRaises(OSError):self.supervised([])
  self.assertEqual(self.last_launches,[]);self.assertFalse(self.api.releases);self.assertIsNotNone(self.api.control['lease'])
 def test_supervisor_thread_setup_failure_waits_before_releasing_world_lock(self):
  with patch.object(L.threading.Thread,'start',side_effect=RuntimeError('own thread setup failure')),self.assertRaises(RuntimeError):self.supervised([])
  self.assertEqual(len(self.last_launches),1);self.assertFalse((self.world/'world.lock').exists());self.assertFalse(self.api.releases);self.assertIsNotNone(self.api.control['lease'])
 def test_repeated_post_Popen_state_IO_failure_waits_with_live_child_lock(self):
  actual=self.t.phase
  def failed(s,phase,**fields):
   if phase in('running','qmp-error-running'):raise OSError('own injected post-Popen state I/O failure')
   return actual(s,phase,**fields)
  with patch.object(self.t,'phase',failed),self.assertRaises(OSError):self.supervised([],hold_until_wait=True)
  self.assertEqual(len(self.last_launches),1);self.assertFalse((self.world/'world.lock').exists());self.assertFalse(self.api.releases);self.assertEqual(self.t.read()['phase'],'starting');self.assertIsNotNone(self.api.control['lease'])
 def test_start_waits_for_handshake_but_does_not_claim_SSH_health(self):
  t=type('View',(),{})();views=iter([{'phase':'ready'},{'phase':'starting'},{'phase':'running'}]);t.read=lambda:next(views)
  with patch.object(L.time,'sleep'),patch.object(L.time,'monotonic',side_effect=[0,.1,.2]):self.assertEqual(L.wait_supervisor(t)['phase'],'running')
  s={'phase':'running','world':str(self.world),'access':self.access};self.assertIn('no health probe',L.access_report(s)['availability'])
 def test_start_wait_is_bounded_and_preserves_unavailable_status(self):
  t=type('View',(),{'read':lambda self:{'phase':'starting'}})()
  with patch.object(L.time,'sleep'),patch.object(L.time,'monotonic',side_effect=[0,6]):s=L.wait_supervisor(t)
  self.assertEqual(L.access_report(s)['status'],'unavailable')
 def test_api_CAS_explicit_noreply_author_and_stderr_not_logged(self):
  seen=[]
  def run(args,**kw):
   seen.append((args,kw));body={'private':True,'default_branch':'main'}if args[args.index('--method')+1]=='GET'else{'content':{'sha':'new'}}
   return subprocess.CompletedProcess(args,0,b'HTTP/2.0 200 OK\nX-Test: own\n\n'+L.dump(body),b'never log this')
  with patch.object(L.subprocess,'run',run):g=L.GitHub('owner/private');g.cas('old',{'format':1,'revision':1,'current':None,'lease':None})
  body=json.loads(seen[-1][1]['input']);self.assertEqual(body['author'],L.IDENTITY);self.assertEqual(body['committer'],L.IDENTITY);self.assertEqual(body['sha'],'old');self.assertEqual(seen[-1][1]['stderr'],subprocess.DEVNULL);self.assertNotIn('Authorization',' '.join(seen[-1][0]))
 def test_upload_pins_github_com_despite_hostile_GH_HOST(self):
  g=object.__new__(L.GitHub);g.repo='owner/private';g.gh='gh';seen=[]
  def run(args,**kw):seen.append(args);return subprocess.CompletedProcess(args,0,b'',b'')
  with patch.dict(os.environ,{'GH_HOST':'enterprise.invalid'}),patch.object(L.subprocess,'run',run):
   g.upload({'tag_name':'world-'+'a'*32},self.disk)
   self.assertEqual(os.environ['GH_HOST'],'enterprise.invalid')
  args=seen[0];self.assertEqual(args[args.index('--repo')+1],'github.com/owner/private');self.assertNotIn('enterprise.invalid',' '.join(args));self.assertNotIn('--clobber',args)
 def test_public_repository_refused_before_CAS_or_release(self):
  def run(args,**kw):return subprocess.CompletedProcess(args,0,b'HTTP/2.0 200 OK\n\n{"private":false}',b'')
  with patch.object(L.subprocess,'run',run),self.assertRaises(L.Error):L.GitHub('owner/public')
 def test_invalid_control_rejected_bool_format_and_lease(self):
  for d in({'format':True,'revision':0,'current':None,'lease':None},{'format':1,'revision':True,'current':None,'lease':None},{'format':1,'revision':0,'current':None,'lease':{'owner':'bad','phase':'active'}}):
   with self.assertRaises(L.Error):L.valid_control(d)

if __name__=='__main__':unittest.main(verbosity=2)
