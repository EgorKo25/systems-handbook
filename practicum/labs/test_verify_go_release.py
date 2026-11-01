"""Real original Go release and negative provenance checks in a temporary repo."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('verify_go_release',HERE/'verify_go_release.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
GO=os.environ.get('HANDBOOK_GO') or shutil.which('go')


class ReleaseVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not GO:
            raise unittest.SkipTest('Prepare real Go in HANDBOOK_GO or PATH')
        cls.temp=tempfile.TemporaryDirectory(prefix='handbook-release-proof-')
        cls.project=Path(cls.temp.name)/'service'
        shutil.copytree(ROOT/'go/labs/service',cls.project,
                        ignore=shutil.ignore_patterns('dist','.lab-cache','__pycache__'))
        shutil.copyfile(HERE/'verify_go_release.py', cls.project/'tools/verify-release.py')
        cls.env={k:v for k,v in os.environ.items() if not k.startswith('GIT_') and k!='CI_COMMIT_SHA'}
        cls.env.update(HANDBOOK_GO=GO,GOENV='off',GOTOOLCHAIN='local',GOWORK='off',
                       GOPROXY='off',GOTELEMETRY='off',GOMAXPROCS='2')
        base=['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
              '-c','user.name=EgorKo25','-c','user.email=77259232+EgorKo25@users.noreply.github.com']
        for args in [('init','--initial-branch=main'),('add','.'),('commit','-m','Original release fixture')]:
            subprocess.run([*base,*args],cwd=cls.project,env=cls.env,check=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        native=json.loads(subprocess.check_output([GO,'env','-json','GOHOSTOS','GOHOSTARCH'],env=cls.env,text=True))
        subprocess.run(['python3','tools/build.py','--goos',native['GOHOSTOS'],'--goarch',native['GOHOSTARCH']],
                       cwd=cls.project,env=cls.env,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        cls.path=cls.project/'dist/manifest.json'
        cls.original=cls.path.read_text()
        cls.manifest=json.loads(cls.original)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'temp'): cls.temp.cleanup()

    def verify(self):
        # Ensure surrounding CI settings cannot accidentally replace the fixture's identity.
        with patch.dict(os.environ,self.env,clear=True):
            return helper.verify(self.project,'1.0.0',GO)

    def test_01_actual_native_binary(self):
        result=self.verify()
        self.assertEqual(result['sha256'],self.manifest['sha256'])
        self.assertEqual(result['source_revision'],self.manifest['source_revision'])

    def test_02_manifest_corruption_rejected(self):
        fields={'format':9,'binary':'../../outside','bytes':1,'sha256':'0'*64,
                'version':'9.9.9','source_revision':'0'*40,'source_dirty':True,
                'flags':[],'toolchain':'not real Go','target':{},'build_script_sha256':'0'*64}
        try:
            for key,value in fields.items():
                with self.subTest(field=key):
                    changed=dict(self.manifest,**{key:value})
                    self.path.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError): self.verify()
        finally:
            self.path.write_text(self.original)

    def test_03_changed_binary_rejected_before_execution(self):
        path=self.project/'dist'/self.manifest['binary'];raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'changed')
            with self.assertRaisesRegex(ValueError,'not executed'): self.verify()
        finally:
            path.write_bytes(raw)

    def test_04_uncommitted_input_rejected(self):
        path=self.project/'cmd/handbook-service/main.go';raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'\n// modified input\n')
            with self.assertRaisesRegex(ValueError,'uncommitted'): self.verify()
        finally:
            path.write_bytes(raw)

    def test_05_declared_ci_commit_checked_against_git(self):
        with patch.dict(os.environ,dict(self.env,CI_COMMIT_SHA='b'*40),clear=True):
            with self.assertRaisesRegex(ValueError,'Declared CI revision'):
                helper.verify(self.project,'1.0.0',GO)


if __name__=='__main__': unittest.main(verbosity=2)
