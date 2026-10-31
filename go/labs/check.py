#!/usr/bin/env python3
"""Verify the actual Go teaching project in isolated copies. Needs Go and Git."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
GO=os.environ.get('HANDBOOK_GO') or shutil.which('go')
if not GO: raise SystemExit('Install a suitable Go or set HANDBOOK_GO; no tools were installed.')

class GoProjectChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='handbook-go-check-')
        cls.root=Path(cls.temp.name)
        cls.env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        cls.env.update(HANDBOOK_GO=GO,GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1',GIT_AUTHOR_DATE='2000-01-01T00:00:00+0000',
                       GIT_COMMITTER_DATE='2000-01-01T00:00:00+0000',GOMAXPROCS='2',
                       GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',
                       GOCACHE=str(cls.root/'test-cache'),GOPATH=str(cls.root/'gopath'),
                       GOMODCACHE=str(cls.root/'modules'),GOTELEMETRY='off')
        cls.a=cls.copy('first');cls.b=cls.copy('different-parent/second')
        cls.run_command([GO,'test','-count=1','./...'],cls.a)
        cls.ma=cls.build(cls.a);cls.mb=cls.build(cls.b)
        cls.baseline=(cls.a/'dist/handbook-service').read_bytes()
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    @classmethod
    def run_command(cls,argv,cwd,check=True):
        return subprocess.run(argv,cwd=cwd,env=cls.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=check)
    @classmethod
    def git(cls,cwd,*args):
        return cls.run_command(['git','-c','core.hooksPath=/dev/null','-c','user.name=Handbook Lab','-c','user.email=lab@example.invalid',*args],cwd).stdout.strip()
    @classmethod
    def copy(cls,name):
        path=cls.root/name
        shutil.copytree(HERE/'service',path,ignore=shutil.ignore_patterns('.lab-cache','dist','__pycache__'))
        cls.git(path,'init','--initial-branch=main');cls.git(path,'add','.');cls.git(path,'commit','-m','Initial teaching source')
        return path
    @classmethod
    def build(cls,cwd,*args):
        cls.run_command(['python3','tools/build.py',*args],cwd)
        return json.loads((cwd/'dist/manifest.json').read_text())
    def test_01_native_go_tests_and_artifact(self):
        self.assertTrue(self.baseline.startswith(b'\x7fELF'))
        self.assertEqual(self.ma['sha256'],hashlib.sha256(self.baseline).hexdigest())
        self.assertEqual(self.ma['bytes'],len(self.baseline))
        self.assertFalse(self.ma['source_dirty'])
    def test_02_binary_and_build_information(self):
        self.assertEqual(self.run_command([str(self.a/'dist/handbook-service'),'-version'],self.a).stdout,'1.0.0\n')
        info=self.run_command([GO,'version','-m',str(self.a/'dist/handbook-service')],self.a).stdout
        for field in ['-trimpath=true','CGO_ENABLED=0','GOOS=linux','GOARCH=amd64']: self.assertIn(field,info)
        self.assertNotIn('vcs.revision=',info)
    def test_03_clean_copies_in_different_paths_match(self):
        self.assertEqual(self.baseline,(self.b/'dist/handbook-service').read_bytes())
    def test_04_empty_commit_changes_only_recorded_provenance(self):
        self.git(self.b,'commit','--allow-empty','-m','Different source identity')
        updated=self.build(self.b)
        self.assertNotEqual(updated['source_revision'],self.mb['source_revision'])
        self.assertEqual(updated['sha256'],self.mb['sha256'])
        self.assertFalse(updated['source_dirty'])
    def test_05_changed_source_changes_binary_and_dirty_record(self):
        p=self.a/'internal/httpapp/handler.go';old=p.read_bytes()
        try:
            p.write_bytes(old.replace(b'Hello, ',b'Welcome, '))
            changed=self.build(self.a)
            self.assertNotEqual(changed['sha256'],self.ma['sha256'])
            self.assertTrue(changed['source_dirty'])
        finally:
            p.write_bytes(old);self.build(self.a)
    def test_06_version_is_a_real_build_input(self):
        try:
            changed=self.build(self.a,'--version','2.0.0')
            self.assertNotEqual(changed['sha256'],self.ma['sha256'])
            self.assertEqual(self.run_command([str(self.a/'dist/handbook-service'),'-version'],self.a).stdout,'2.0.0\n')
        finally:self.build(self.a)
    def test_07_symlink_output_is_rejected(self):
        bad=self.copy('symlink-case');outside=self.root/'outside';outside.mkdir();marker=outside/'keep.txt';marker.write_text('keep')
        (bad/'dist').symlink_to(outside,target_is_directory=True)
        result=self.run_command(['python3','tools/build.py'],bad,check=False)
        self.assertNotEqual(result.returncode,0);self.assertEqual(marker.read_text(),'keep')
        self.assertEqual(sorted(p.name for p in outside.iterdir()),['keep.txt'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(GoProjectChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'format':1,'ok':result.wasSuccessful(),'tests':result.testsRun,
                      'go':subprocess.check_output([GO,'version'],text=True).strip(),
                      'not_tested':['Windows execution','external module proxy','CGO runtime']}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
