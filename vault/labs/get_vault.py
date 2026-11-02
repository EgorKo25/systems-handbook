#!/usr/bin/env python3
"""Download a pinned official archive into a private root and verify before use."""
import argparse, hashlib, os, pathlib, subprocess, urllib.request, zipfile
P=argparse.ArgumentParser(description=__doc__)
P.add_argument('--root',type=pathlib.Path,required=True)
a=P.parse_args(); root=a.root.expanduser().resolve()
if root in (pathlib.Path('/'),pathlib.Path.home()): P.error('choose a dedicated private directory')
os.umask(0o077); root.mkdir(parents=True,exist_ok=True); root.chmod(0o700)
for d in ('downloads','bin','gnupg'): (root/d).mkdir(exist_ok=True,mode=0o700)
version='1.21.4'; archive=f'vault_{version}_linux_amd64.zip'
files={archive:f'https://releases.hashicorp.com/vault/{version}/{archive}',
 f'vault_{version}_SHA256SUMS':f'https://releases.hashicorp.com/vault/{version}/vault_{version}_SHA256SUMS',
 f'vault_{version}_SHA256SUMS.sig':f'https://releases.hashicorp.com/vault/{version}/vault_{version}_SHA256SUMS.sig',
 'hashicorp.asc':'https://www.hashicorp.com/.well-known/pgp-key.txt'}
for name,url in files.items():
 target=root/'downloads'/name
 if not target.exists():
  with urllib.request.urlopen(url,timeout=60) as response, target.with_suffix(target.suffix+'.part').open('wb') as out:
   while block:=response.read(1024*1024): out.write(block)
  target.with_suffix(target.suffix+'.part').replace(target)
# The expected primary fingerprint was checked against the vendor security page.
# Downloading a key and accepting any fingerprint would not bootstrap trust.
fpr='C874011F0AB405110D02105534365D9472D7468F'
gpg=['gpg','--batch','--homedir',str(root/'gnupg')]
subprocess.run(gpg+['--import',str(root/'downloads/hashicorp.asc')],check=True,capture_output=True)
r=subprocess.run(gpg+['--status-fd=1','--verify',str(root/'downloads'/f'vault_{version}_SHA256SUMS.sig'),str(root/'downloads'/f'vault_{version}_SHA256SUMS')],capture_output=True,text=True,check=True)
valid=[line.split() for line in r.stdout.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
if not any(line[-1]==fpr for line in valid): raise SystemExit('signature identity mismatch; stop')
expected=next(line.split()[0] for line in (root/'downloads'/f'vault_{version}_SHA256SUMS').read_text().splitlines() if line.endswith(archive))
actual=hashlib.file_digest((root/'downloads'/archive).open('rb'),'sha256').hexdigest()
if actual!=expected: raise SystemExit('archive checksum mismatch; stop')
with zipfile.ZipFile(root/'downloads'/archive) as z:
 data=z.read('vault')
binary=root/'bin/vault'; binary.write_bytes(data); binary.chmod(0o700)
print('Verified primary fingerprint:',fpr)
print('Verified archive SHA256:',actual)
subprocess.run([str(binary),'version'],check=True)
