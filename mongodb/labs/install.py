#!/usr/bin/env python3
"""Fetch pinned Community artifacts into an existing private LAB; no host install."""
import hashlib,json,pathlib,subprocess,sys,tarfile,urllib.request
p=pathlib.Path(sys.argv[1]).expanduser().resolve()
if not (p/'private/keyfile').is_file():raise SystemExit('STOP: run prepare.py first')
archives=[
('server','https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-8.0.34.tgz','3e55cdcf7013fbc805d29d8195230df4b23c7688733ee15ad58ac6bc2a416611'),
('shell','https://downloads.mongodb.com/compass/mongosh-2.14.1-linux-x64.tgz','8d24940ebe3675959b518fd41ea16b4e2182d6a75c09777db09cfa64e18834a1'),
('dbtools','https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2404-x86_64-100.20.0.tgz','0cee7b5bf3e986a01f5b4fcc750d056064a619ba7131cf1b22fef139558cc4be')]
cache=p/'downloads';cache.mkdir(exist_ok=True)
for name,url,want in archives:
 out=p/'tools'/name
 if out.exists():raise SystemExit('STOP: tools target exists: '+str(out))
 file=cache/(name+'.tgz')
 if not file.exists():file.write_bytes(urllib.request.urlopen(url,timeout=120).read())
 got=hashlib.sha256(file.read_bytes()).hexdigest()
 if got!=want:raise SystemExit('STOP: SHA256 mismatch '+name)
 if name=='server':
  home=p/'private/gnupg';home.mkdir(mode=0o700,exist_ok=True)
  for local,remote in [('server.sig',url+'.sig'),('server-8.0.asc','https://pgp.mongodb.com/server-8.0.asc')]:
   f=cache/local
   if not f.exists():f.write_bytes(urllib.request.urlopen(remote,timeout=30).read())
  subprocess.run(['gpg','--homedir',str(home),'--batch','--import',str(cache/'server-8.0.asc')],check=True)
  r=subprocess.run(['gpg','--homedir',str(home),'--batch','--status-fd','1','--verify',str(cache/'server.sig'),str(file)],text=True,capture_output=True)
  if r.returncode or 'VALIDSIG 4B0752C1BCA238C0B4EE14DC41DE058A4E7DCA05 ' not in r.stdout:raise SystemExit('STOP: invalid signature or unexpected signing key')
  print('server signature verified with pinned fingerprint')
 out.mkdir(parents=True)
 with tarfile.open(file) as ar:
  for member in ar.getmembers():
   parts=pathlib.PurePosixPath(member.name).parts
   if len(parts)<2:continue
   member.name=str(pathlib.PurePosixPath(*parts[1:]))
   ar.extract(member,out,filter='data')
 print(name,'sha256',got)
(cache/'sources.json').write_text(json.dumps(archives,indent=2))
