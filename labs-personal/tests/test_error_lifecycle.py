"""Real own TEMP state/entry guard with fake API only; no gh/VM/real disks."""
import ast,copy,hashlib,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
import test_transport as T
L=T.L
SOURCE=Path(L.__file__).read_text()
GUARD=next(n for n in ast.parse(SOURCE).body if isinstance(n,ast.If)and isinstance(n.test,ast.Compare)and isinstance(n.test.left,ast.Name)and n.test.left.id=='__name__')
ENTRY=compile(ast.Module(body=[GUARD],type_ignores=[]),str(L.__file__),'exec')

class ErrorLifecycleTests(unittest.TestCase):
 setUp=T.TransportTests.setUp
 info=T.TransportTests.info
 clone=T.TransportTests.clone
 pending=T.TransportTests.pending
 def config(self):
  cfg=self.base/'own-config.json';L.atomic(cfg,{'format':1,'repo':self.api.repo,'branch':'main','root':str(self.t.root),'instructor_console':False,'allow_network':False});return cfg
 def worker(self):
  cfg=self.config();out,err=io.StringIO(),io.StringIO();scope=dict(L.__dict__);scope['__name__']='__main__'
  with patch.object(L,'GitHub',return_value=self.api),patch.object(sys,'argv',['own-lab','--config',str(cfg),'_retry']),patch('sys.stdout',out),patch('sys.stderr',err):
   with self.assertRaises(SystemExit)as exit:exec(ENTRY,scope)
  return exit.exception.code,out.getvalue(),err.getvalue()
 def status(self):
  out=io.StringIO()
  with patch.object(L,'GitHub',side_effect=AssertionError('status must not use network')),patch('sys.stdout',out):self.assertEqual(L.main(['--config',str(self.config()),'status']),0)
  return json.loads(out.getvalue())
 def evidence(self,s):
  # Existing evidence and pending bytes must remain, even after resolved error.
  a=self.t.root/'worker-diagnostic.log';a.write_bytes(b'own synthetic previous upload error evidence\n')
  b=self.world/'qemu-stderr.log';b.write_bytes(b'own synthetic QEMU log; no VM ran\n')
  c=self.world/'shutdown-receipt.json';L.atomic(c,{'own_fixture':'not an actual QMP receipt'})
  paths=[a,b,c,self.disk,*Path(s['pending']).iterdir()]
  return {p:p.read_bytes()for p in paths if p.is_file()}
 def retained(self,files):
  for p,b in files.items():self.assertTrue(p.is_file(),p);self.assertEqual(p.read_bytes(),b,p)
  self.assertFalse(self.api.deletions)
 def test_failure_then_successful_actual_retry_clears_active_error_preserves_evidence(self):
  s=self.pending();s['own_extra_field']='retain';self.t.save(s);files=self.evidence(s);self.api.fail_after_upload=True
  code,_,err=self.worker();self.assertEqual(code,2);self.assertIn('LAB:',err)
  failed=self.t.read();self.assertIn('lost upload reply',failed['last_error']);self.assertIsNone(self.api.control['current']);self.assertIsNotNone(self.api.control['lease']);self.assertNotEqual(failed['phase'],'synced');self.retained(files)
  checked=[];original=L.Transport.readback_checked
  def readback(transport,*args):
   self.assertEqual(transport.read()['last_error'],failed['last_error']);checked.append(True)
   return original(transport,*args)
  with patch.object(L.Transport,'readback_checked',readback):code,_,err=self.worker()
  self.assertTrue(checked);self.assertEqual(code,0,err);done=self.t.read();self.assertEqual(done['phase'],'synced');self.assertNotIn('last_error',done);self.assertEqual(done['own_extra_field'],'retain');self.assertEqual(done['pending'],s['pending']);self.assertEqual(self.api.control['current'],done['published']);self.assertIsNone(self.api.control['lease']);self.retained(files)
  view=self.status();self.assertEqual(view['phase'],'synced');self.assertNotIn('last_error',view)
 def test_new_failed_retry_records_current_error_and_retains_pending_and_lease(self):
  s=self.pending();files=self.evidence(s);self.api.fail_after_upload=True;self.assertEqual(self.worker()[0],2);old=self.t.read()['last_error']
  with patch.object(self.api,'assets',side_effect=L.Error('own new listing failure')):code,_,err=self.worker()
  self.assertEqual(code,2);failed=self.t.read();self.assertEqual(failed['last_error'],'own new listing failure');self.assertNotEqual(failed['last_error'],old);self.assertNotEqual(failed['phase'],'synced');self.assertIsNone(self.api.control['current']);self.assertEqual(self.api.control['lease']['owner'],s['token']);self.assertEqual(self.status()['last_error'],'own new listing failure');self.retained(files)
 def test_new_final_local_fsync_failure_is_not_hidden_even_if_remote_synced(self):
  s=self.pending();s['last_error']='own prior network failure';self.t.save(s);files=self.evidence(s);actual=L.fsyncdir;injected=[]
  def fail_final_once(path):
   if Path(path)==self.t.root and self.t.file.exists()and L.load(self.t.file)['phase']=='synced'and not injected:
    injected.append(True);raise OSError('own final directory fsync failure')
   return actual(path)
  with patch.object(L,'fsyncdir',fail_final_once):code,_,err=self.worker()
  self.assertEqual(code,2);self.assertTrue(injected);done=self.t.read();self.assertEqual(done['phase'],'synced');self.assertEqual(done['last_error'],'own final directory fsync failure');self.assertEqual(self.status()['last_error'],done['last_error']);self.assertEqual(self.api.control['current'],done['published']);self.assertIsNone(self.api.control['lease']);self.retained(files)
 def test_publish_CAS_reply_lost_then_confirmed_clears_old_error(self):
  s=self.pending();s['last_error']='own earlier transient failure';self.t.save(s);files=self.evidence(s);original=self.api.cas;lost=[]
  def cas(expected,value):
   if value['current']is not None:self.api.lose_cas=True;lost.append(True)
   return original(expected,value)
  with patch.object(self.api,'cas',cas):code,_,err=self.worker()
  self.assertEqual(code,0,err);self.assertTrue(lost);self.assertNotIn('last_error',self.t.read());self.assertEqual(self.t.read()['phase'],'synced');self.assertIsNone(self.api.control['lease']);self.retained(files)
 def test_already_desired_current_clears_old_error_without_altering_new_owner_lease(self):
  s=self.pending();self.t.upload_pending(s);s.update(phase='uploading',last_error='own lost final reply');self.t.save(s);files=self.evidence(s)
  other=L.Transport(self.base/'other-own-fake',self.api);other_state=other.new();remote=copy.deepcopy(self.api.control)
  with patch.object(self.api,'upload',side_effect=AssertionError('no new upload')),patch.object(self.api,'publish',side_effect=AssertionError('no republish')),patch.object(self.api,'cas',side_effect=AssertionError('must not alter other lease')):code,_,err=self.worker()
  self.assertEqual(code,0,err);self.assertEqual(self.api.control,remote);self.assertEqual(self.api.control['lease']['owner'],other_state['token']);self.assertNotIn('last_error',self.t.read());self.assertEqual(self.t.read()['phase'],'synced');self.retained(files)

if __name__=='__main__':unittest.main(verbosity=2)
