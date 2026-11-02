#!/usr/bin/env python3
"""Inventory and verify staged offline files. Does not download or execute them."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def create(root):
 files=[]
 for p in sorted(root.rglob('*')):
  if p.is_symlink():raise ValueError('symlink is outside bundle contract: '+str(p))
  if p.is_file() and p.name!='bundle.json':files.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
 return {'format':'handbook-offline-bundle/v1','files':files}
def verify(root,data):
 for x in data['files']:
  rel=PurePosixPath(x['path'])
  if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe bundle path')
  p=root.joinpath(*rel.parts)
  if p.is_symlink() or not p.is_file() or root not in p.resolve().parents:raise ValueError('missing or unsafe file: '+str(rel))
  if p.stat().st_size!=x['bytes'] or digest(p)!=x['sha256']:raise ValueError('integrity mismatch: '+str(rel))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['create','verify']);a.add_argument('root',type=Path);n=a.parse_args();root=n.root.resolve()
 if n.mode=='create':(root/'bundle.json').write_text(json.dumps(create(root),indent=2)+'\n')
 else:verify(root,json.loads((root/'bundle.json').read_text()));print('PASS: listed bundle bytes match; provenance is a separate trust decision')
