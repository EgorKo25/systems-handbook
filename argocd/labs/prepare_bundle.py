#!/usr/bin/env python3
"""Fetch verified pinned files to a persistent reader-owned directory.
Never install, unpack, execute a downloaded program, query a cluster or fetch images.
"""
from pathlib import Path
import argparse,hashlib,json,urllib.request,os
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
def digest_file(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  while block:=stream.read(1024*1024):h.update(block)
 return h.hexdigest()
lock=json.loads((Path(__file__).resolve().parent/'bundle-lock.json').read_text())
if not a.verify_only and a.output.exists() and any(a.output.iterdir()):p.error('New empty directory required; use --verify-only to inspect an existing persistent bundle')
if a.verify_only and not a.output.is_dir():p.error('Existing bundle directory required')
a.output.mkdir(parents=True,exist_ok=True)
for item in lock['files']:
 target=a.output/item['name']
 if not a.verify_only:
  partial=target.with_suffix(target.suffix+'.part')
  try:
   with urllib.request.urlopen(item['url'],timeout=60) as source, partial.open('xb') as out:
    while data:=source.read(1024*1024):out.write(data)
   digest=digest_file(partial)
   if digest!=item['sha256']:raise RuntimeError('Hash mismatch: '+item['name'])
   partial.replace(target)
  except Exception:
   partial.unlink(missing_ok=True);raise
 if not target.is_file() or digest_file(target)!=item['sha256']:
  raise SystemExit('Verification failed: '+item['name'])
 print('VERIFIED '+item['name'])
if not a.verify_only:
 (a.output/'bundle-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
 print('No images downloaded. Prepare platform-specific image digests and node/registry delivery separately.')
