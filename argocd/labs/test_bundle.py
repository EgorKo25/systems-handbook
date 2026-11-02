#!/usr/bin/env python3
"""Real byte verification and extraction from already trusted private fixtures.
No download. BUNDLE_FIXTURE_DIR must contain the four bundle-lock filenames.
"""
from pathlib import Path
import json,os,subprocess,sys,tempfile
BASE=Path(__file__).resolve().parent
source=Path(os.environ['BUNDLE_FIXTURE_DIR'])
lock=json.loads((BASE/'bundle-lock.json').read_text())
with tempfile.TemporaryDirectory(prefix='argocd-bundle-check-') as tmp:
 root=Path(tmp);bundle=root/'bundle';bundle.mkdir()
 for item in lock['files']:
  src=source/item['name'];assert src.is_file(),item['name']
  (bundle/item['name']).symlink_to(src.resolve())
 def run(args,code=0):
  q=subprocess.run(args,text=True,capture_output=True,timeout=90)
  assert q.returncode==code,(args,q.returncode,q.stderr);return q
 run([sys.executable,BASE/'prepare_bundle.py','--output',bundle,'--verify-only'])
 # No download: nonempty output is rejected before any URL is opened.
 run([sys.executable,BASE/'prepare_bundle.py','--output',bundle],2)
 target=bundle/'install.yaml';target.unlink();target.write_text('tampered fixture, never a real manifest')
 run([sys.executable,BASE/'prepare_bundle.py','--output',bundle,'--verify-only'],1)
 target.unlink();run([sys.executable,BASE/'prepare_bundle.py','--output',bundle,'--verify-only'],1)
 target.symlink_to((source/'install.yaml').resolve())
 env=dict(os.environ,LAB_ROOT=str(root))
 q=subprocess.run(['bash',BASE/'scripts/prepare-tools.sh'],env=env,text=True,capture_output=True,timeout=90)
 assert q.returncode==0,q.stderr
 q=subprocess.run(['bash',BASE/'scripts/prepare-tools.sh'],env=env,text=True,capture_output=True,timeout=90)
 assert q.returncode==1 and 'exists' in q.stderr,q.stderr
 print('PASS:real four-file hashes,tamper/missing/nonempty rejection,pinned extraction/version checks,no overwrite. No network/images/cluster.')
