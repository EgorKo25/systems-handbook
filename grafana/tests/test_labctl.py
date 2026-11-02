#!/usr/bin/env python3
import concurrent.futures,hashlib,importlib.util,os,stat,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'labs/labctl.py';sp=importlib.util.spec_from_file_location('labctl',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
def snapshot(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
class InitTests(unittest.TestCase):
 def test_partial_state_never_overwritten(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'lab';(root/'private').mkdir(parents=True);(root/'data').mkdir();(root/'private/secret-key').write_text('existing-key');(root/'data/grafana.db').write_bytes(b'existing-db');before=snapshot(root)
   with self.assertRaises(ValueError):m.initialize(root)
   self.assertEqual(before,snapshot(root));self.assertFalse((root/'config').exists())
 def test_perms_and_repeat(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'path with spaces';root.mkdir();old=os.umask(0)
   try:m.initialize(root)
   finally:os.umask(old)
   self.assertEqual(stat.S_IMODE((root/'private').stat().st_mode),0o700)
   for name in ['admin-password','secret-key']:self.assertEqual(stat.S_IMODE((root/'private'/name).stat().st_mode),0o600)
   before=snapshot(root)
   with self.assertRaises(ValueError):m.initialize(root)
   self.assertEqual(before,snapshot(root))
 def test_unsupported_configuration_roots_rejected_before_creation(self):
  with tempfile.TemporaryDirectory() as t:
   parent=Path(t);(parent/'sentinel').write_bytes(b'preserve-existing-parent');before=snapshot(parent)
   names=['dollar$HOME','hash#part','semicolon;part',"apostrophe'part",'brace}part','tab\tpart','newline\npart','del'+chr(127)+'part','template@LAB_ROOT@','template@PORT@']
   for name in names:
    with self.subTest(name=repr(name)):
     root=parent/name
     with self.assertRaises(ValueError):m.initialize(root)
     self.assertFalse(root.exists());self.assertEqual(before,snapshot(parent))
 def test_concurrent_init_one_owner(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'lab'
   def attempt(_):
    try:m.initialize(root);return True
    except (ValueError,FileExistsError):return False
   with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(attempt,range(2)))
   self.assertEqual(sum(result),1);self.assertTrue((root/'config/grafana.ini').is_file())
if __name__=='__main__':unittest.main()
