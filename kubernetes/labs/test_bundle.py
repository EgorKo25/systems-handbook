#!/usr/bin/env python3
import tempfile
from pathlib import Path
from bundle_manifest import create,verify
with tempfile.TemporaryDirectory(prefix='k8s-bundle-test-') as t:
 p=Path(t);(p/'images').mkdir();f=p/'images/node.tar';f.write_bytes(b'staged bytes\x00');data=create(p);verify(p,data)
 f.write_bytes(b'corrupted!')
 try:verify(p,data)
 except ValueError:pass
 else:raise AssertionError('corruption not detected')
 for bad in ['../outside','/etc/passwd']:
  try:verify(p,{'files':[{'path':bad,'bytes':0,'sha256':''}]})
  except ValueError:pass
  else:raise AssertionError('path escape accepted')
 print('PASS: bundle round trip, corruption, absolute and parent path rejection')
