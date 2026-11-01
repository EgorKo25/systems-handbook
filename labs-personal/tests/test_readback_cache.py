"""Real local files, fake remote API only; no credentials, network, VM or 512MiB data."""
import copy, hashlib, os, stat, sys, unittest, uuid
from pathlib import Path
from unittest.mock import patch
import test_transport as T

L = T.L

class ReadbackCacheTests(unittest.TestCase):
 setUp=T.TransportTests.setUp
 info=T.TransportTests.info
 clone=T.TransportTests.clone
 pending=T.TransportTests.pending

 def four_part_failure(self):
  # Four tiny parts stand for the same control path as four 512MiB parts.
  self.disk.write_bytes(bytes(range(31)))
  s=self.pending();real=self.api.download;self.downloads=[];self.fail_fourth=True
  def download(asset,path):
   self.downloads.append((self.api.repo,asset['id'],asset['name']))
   if self.fail_fourth and asset['name']=='disk-0003.part':Path(path).write_bytes(b'')
   else:real(asset,path)
  self.api.download=download
  with self.assertRaisesRegex(L.Error,'Remote read-back failed'):self.t.upload_pending(s)
  return s

 def one_cached(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token'])
  p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes())
  self.t.readback_checked(s,r,a,p)
  return s,r,a,p

 def cache_files(self):return list((self.t.root/'verification/readback-v1').glob('*.verified'))
 def retained(self,s):
  self.assertIsNone(self.api.control['current']);self.assertEqual(self.api.control['lease']['owner'],s['token'])
  self.assertNotEqual(self.t.read()['phase'],'synced')

 def test_second_process_retry_reuses_first_three_but_fourth_failure_still_blocks_current(self):
  s=self.four_part_failure();self.assertEqual(len(self.cache_files()),3);self.retained(s)
  self.assertEqual([x[2]for x in self.downloads],['disk-0000.part','disk-0001.part','disk-0002.part','disk-0003.part'])
  # Actual _retry CLI dispatch, new Transport instance, persisted handoff/cache.
  cfg=self.base/'offline-config.json';L.atomic(cfg,{'format':1,'repo':self.api.repo,'branch':'main','root':str(self.t.root),'instructor_console':False,'allow_network':False})
  with patch.object(L,'GitHub',return_value=self.api),self.assertRaisesRegex(L.Error,'Remote read-back failed'):
   L.main(['--config',str(cfg),'_retry'])
  self.assertEqual([x[2]for x in self.downloads],['disk-0000.part','disk-0001.part','disk-0002.part','disk-0003.part','disk-0003.part'])
  self.assertEqual(len(self.cache_files()),3);self.retained(s)
  partials=list((self.t.root/'verification/readback-v1').glob('*.partial-*'))
  self.assertEqual(len(partials),2);self.assertTrue(all(p.stat().st_size==0 for p in partials))
  self.fail_fourth=False
  t2=L.Transport(self.t.root,self.api);again=t2.read();t2.upload_pending(again)
  self.assertEqual([x[2]for x in self.downloads][-2:],['disk-0003.part','manifest.json'])
  self.assertEqual(again['phase'],'synced');self.assertIsNone(self.api.control['lease'])
  self.assertEqual(self.api.control['current'],again['published'])

 def test_reuse_hashes_actual_cache_bytes_again_and_rejects_same_size_corruption(self):
  s=self.four_part_failure();files=self.cache_files();first=next(p for p in files if p.read_bytes()==bytes(range(8)))
  first.write_bytes(b'CORRUPT!');seen=[];real=L.sha
  def hashed(p):
   if Path(p).suffix=='.verified':seen.append(Path(p))
   return real(p)
  before=list(self.downloads)
  with patch.object(L,'sha',hashed),self.assertRaisesRegex(L.Error,'cache changed'):
   self.t.upload_pending(self.t.read())
  self.assertIn(first,seen);self.assertEqual(self.downloads,before);self.assertEqual(first.read_bytes(),b'CORRUPT!');self.retained(s)

 def test_deleted_cache_requires_real_download_again(self):
  s=self.four_part_failure();first=next(p for p in self.cache_files()if p.read_bytes()==bytes(range(8)));first.unlink()
  with self.assertRaises(L.Error):self.t.upload_pending(self.t.read())
  self.assertEqual([n for _,_,n in self.downloads].count('disk-0000.part'),2);self.retained(s)

 def test_replaced_remote_asset_id_cannot_reuse_old_verified_file(self):
  s=self.four_part_failure();r=self.api.release('world-'+s['token'],s['token']);a=r['items'][0];old=a['id']
  fresh=self.api.next;self.api.next+=1;a['id']=fresh;self.api.assets_by_id[fresh]=self.api.assets_by_id[old]
  with self.assertRaises(L.Error):self.t.upload_pending(self.t.read())
  self.assertEqual(sum(i==old for _,i,_ in self.downloads),1)
  self.assertEqual(sum(i==fresh for _,i,_ in self.downloads),1)
  self.assertEqual(len(self.cache_files()),4);self.retained(s)

 def test_repo_identity_is_part_of_the_cache_key(self):
  s=self.four_part_failure();self.api.repo='other-owner/other-private'
  with self.assertRaises(L.Error):self.t.upload_pending(self.t.read())
  for n in range(3):self.assertEqual([name for _,_,name in self.downloads].count('disk-%04d.part'%n),2)
  self.assertEqual(len(self.cache_files()),6);self.retained(s)

 def test_changed_expected_hash_and_size_need_new_real_bytes_not_old_cache(self):
  s,r,a,p=self.one_cached();old=list(self.cache_files());data=b'new descriptor bytes'
  self.api.assets_by_id[a['id']]=data;a['size']=len(data)
  new=dict(p,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
  calls=[];real=self.api.download
  def downloaded(asset,path):calls.append(asset['id']);return real(asset,path)
  with patch.object(self.api,'download',downloaded):self.t.readback_checked(s,r,a,new)
  self.assertEqual(calls,[a['id']]);self.assertEqual(len(self.cache_files()),2)
  self.assertTrue(old[0].exists());self.retained(s)

 def test_incomplete_remote_state_cannot_reuse_cache_or_advance_current(self):
  s=self.four_part_failure();r=self.api.release('world-'+s['token'],s['token']);r['items'][0]['state']='processing'
  before=list(self.downloads)
  with self.assertRaisesRegex(L.Error,'Remote asset incomplete'):self.t.upload_pending(self.t.read())
  self.assertEqual(self.downloads,before);self.retained(s)

 def test_wrong_remote_size_rejected_despite_valid_local_cache(self):
  s,r,a,p=self.one_cached();a['size']+=1
  with patch.object(self.api,'download',side_effect=AssertionError('must not download')),self.assertRaisesRegex(L.Error,'changed/incomplete'):
   self.t.readback_checked(s,r,a,p)
  self.retained(s)

 def test_boolean_remote_size_cannot_impersonate_a_one_byte_asset(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token'])
  a=self.api.add(r,'disk-0000.part',b'x');a['size']=True
  p={'name':a['name'],'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
  with patch.object(self.api,'download',side_effect=AssertionError('must not download')),self.assertRaisesRegex(L.Error,'changed/incomplete'):
   self.t.readback_checked(s,r,a,p)
  self.retained(s)

 def test_foreign_renamed_asset_blocks_before_cache_reuse(self):
  s=self.four_part_failure();r=self.api.release('world-'+s['token'],s['token']);r['items'][0]['name']='foreign.bin';before=list(self.downloads)
  with self.assertRaisesRegex(L.Error,'Unexpected assets'):self.t.upload_pending(self.t.read())
  self.assertEqual(self.downloads,before);self.assertFalse(self.api.deletions);self.retained(s)

 def test_foreign_release_owner_and_stolen_lease_block_without_download(self):
  for kind in ('owner','lease'):
   with self.subTest(kind=kind):
    s,r,a,p=self.one_cached();before=len(self.cache_files())
    if kind=='owner':r['body']='personal-lab-v1:'+'f'*32
    else:self.api.control['lease']['owner']='e'*32
    with patch.object(self.api,'download',side_effect=AssertionError('must not download')),self.assertRaises(L.Error):self.t.readback_checked(s,r,a,p)
    self.assertEqual(len(self.cache_files()),before);self.assertIsNone(self.api.control['current'])
    # Fresh own local fixture for the second subcase, no reset of a real world.
    if kind=='owner':
     self.api=T.Fake();self.t=L.Transport(self.base/'second-own-fake',self.api)

 def test_lease_loss_during_local_rehash_is_rechecked_before_reuse(self):
  s,r,a,p=self.one_cached();real=L.sha
  def hashed(path):
   value=real(path)
   if Path(path).suffix=='.verified':self.api.control['lease']['owner']='e'*32
   return value
  with patch.object(L,'sha',hashed),patch.object(self.api,'download',side_effect=AssertionError('must not download')),self.assertRaisesRegex(L.Error,'lease/current mismatch'):
   self.t.readback_checked(s,r,a,p)
  self.assertIsNone(self.api.control['current'])

 def test_asset_replaced_during_download_is_not_promoted_to_verified(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes());real=self.api.download
  def changed(asset,path):
   real(asset,path);replacement=copy.deepcopy(a);replacement['id']=987;r['items']=[replacement]
  with patch.object(self.api,'download',changed),self.assertRaisesRegex(L.Error,'changed/incomplete'):
   self.t.readback_checked(s,r,a,p)
  self.assertFalse(self.cache_files());self.assertTrue(list((self.t.root/'verification/readback-v1').glob('*.partial-*')));self.retained(s)

 def test_release_replaced_during_download_is_not_promoted(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes());original=copy.deepcopy(r);real=self.api.download
  def changed(asset,path):real(asset,path);r['id']+=1
  with patch.object(self.api,'download',changed),self.assertRaisesRegex(L.Error,'release changed'):
   self.t.readback_checked(s,original,a,p)
  self.assertFalse(self.cache_files());self.retained(s)

 def test_remote_digest_and_reported_size_never_substitute_for_actual_bytes(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],b'badbytes');a['digest']='sha256:'+p['sha256'];self.assertEqual(a['size'],p['bytes'])
  with self.assertRaisesRegex(L.Error,'Remote read-back failed'):self.t.readback_checked(s,r,a,p)
  self.assertFalse(self.cache_files());self.retained(s)

 def test_new_download_hash_file_fsync_atomic_replace_directory_fsync_order(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes());events=[]
  actual_download=self.api.download;actual_hash=L.sha;actual_sync=L.os.fsync;actual_replace=L.os.replace;actual_dir=L.fsyncdir
  def download(asset,path):events.append('download');return actual_download(asset,path)
  def hashed(path):events.append('hash');return actual_hash(path)
  def synced(fd):
   if stat.S_ISREG(os.fstat(fd).st_mode):events.append('file-fsync')
   return actual_sync(fd)
  def renamed(src,dst):events.append('atomic-replace');return actual_replace(src,dst)
  def directory(path):events.append('directory-fsync');return actual_dir(path)
  with patch.object(self.api,'download',download),patch.object(L,'sha',hashed),patch.object(L.os,'fsync',synced),patch.object(L.os,'replace',renamed),patch.object(L,'fsyncdir',directory):self.t.readback_checked(s,r,a,p)
  self.assertEqual(events,['download','hash','file-fsync','atomic-replace','directory-fsync'])
  self.assertEqual(len(self.cache_files()),1);self.assertFalse(list(self.cache_files()[0].parent.glob('*.partial-*')))

 def test_file_fsync_failure_retains_partial_without_verified_success(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes())
  with patch.object(L.os,'fsync',side_effect=OSError('own fsync failure')),self.assertRaises(OSError):self.t.readback_checked(s,r,a,p)
  self.assertFalse(self.cache_files());self.assertTrue(list((self.t.root/'verification/readback-v1').glob('*.partial-*')));self.retained(s)

 @unittest.skipIf(os.name=='nt','Creating symlinks may require Windows host privilege; no such privilege requested')
 def test_symlink_cache_file_is_not_read_or_overwritten(self):
  s,r,a,p=self.one_cached();file=self.cache_files()[0];outside=self.base/'unrelated';outside.write_bytes(file.read_bytes());file.unlink();file.symlink_to(outside)
  with patch.object(self.api,'download',side_effect=AssertionError('must not download')),self.assertRaisesRegex(L.Error,'Unsafe read-back cache file'):
   self.t.readback_checked(s,r,a,p)
  self.assertEqual(outside.read_bytes(),(Path(s['pending'])/p['name']).read_bytes());self.retained(s)

 @unittest.skipIf(os.name=='nt','No privileged Windows symlink creation')
 def test_symlink_cache_directory_is_not_traversed(self):
  s=self.pending();r=self.api.release('world-'+s['token'],s['token']);p=L.load(Path(s['pending'])/'manifest.json')['parts'][0]
  a=self.api.add(r,p['name'],(Path(s['pending'])/p['name']).read_bytes());outside=self.base/'outside';outside.mkdir()
  (self.t.root/'verification').symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(L.Error,'Unsafe verification directory'):self.t.readback_checked(s,r,a,p)
  self.assertFalse(list(outside.iterdir()));self.retained(s)

 def test_final_remote_asset_set_change_blocks_publish_after_individual_verification(self):
  s=self.pending();actual=self.t.readback_checked
  def changed(state,release,asset,p):
   actual(state,release,asset,p)
   if p['name']=='manifest.json':
    first=release['items'][0];first['id']=99999
  with patch.object(self.t,'readback_checked',changed),self.assertRaisesRegex(L.Error,'asset set changed'):
   self.t.upload_pending(s)
  self.assertTrue(self.api.release('world-'+s['token'],s['token'])['draft']);self.retained(s)

 def test_duplicate_names_rejected_even_with_a_valid_cache(self):
  s,r,a,p=self.one_cached();r['items'].append(copy.deepcopy(a))
  with self.assertRaisesRegex(L.Error,'Duplicate asset names'):self.t.readback_checked(s,r,a,p)
  self.retained(s)

 def test_missing_repository_identity_cannot_reuse_cache(self):
  s,r,a,p=self.one_cached()
  with patch.object(self.api,'repo',None),self.assertRaisesRegex(L.Error,'repository identity'):
   self.t.readback_checked(s,r,a,p)
  self.retained(s)

if __name__=='__main__':unittest.main(verbosity=2)
