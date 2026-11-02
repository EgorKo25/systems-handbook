#!/usr/bin/env python3
"""Prepare a new private single-node lab. Never reuse or reset existing data."""
import base64,json,os,pathlib,secrets,sys
if len(sys.argv)!=2:raise SystemExit('usage: python3 labs/prepare.py ABSOLUTE_LAB')
p=pathlib.Path(sys.argv[1]).expanduser()
if not p.is_absolute() or p.exists():raise SystemExit('STOP: choose an absolute path that does not exist')
p.mkdir(mode=0o700,parents=True)
for name in ('data','log','run','private','backups','shell-config'):(p/name).mkdir(mode=0o700)
def private(name,text):
 f=p/'private'/name;f.write_text(text);f.chmod(0o600)
private('keyfile',base64.b64encode(secrets.token_bytes(512)).decode()+'\n')
for username,source in [('operator','admin'),('app','workshop')]:
 password=secrets.token_urlsafe(30)
 private(username+'.json',json.dumps(dict(username=username,password=password,source=source)))
 if username=='operator':private('tools.yml','uri: '+json.dumps('mongodb://operator@127.0.0.1:27117/?authSource=admin&replicaSet=study')+'\npassword: '+json.dumps(password)+'\n')
# JSON double quoted strings are also valid YAML strings; no implicit path expansion.
q=lambda name:json.dumps(str(p/name))
(p/'mongod.yml').write_text('''storage:
  dbPath: %s
  wiredTiger:
    engineConfig:
      cacheSizeGB: 0.25
systemLog:
  destination: file
  path: %s
  logAppend: true
net:
  bindIp: 127.0.0.1
  port: 27117
  unixDomainSocket:
    enabled: false
processManagement:
  pidFilePath: %s
replication:
  replSetName: study
  oplogSizeMB: 128
security:
  authorization: enabled
  keyFile: %s
'''%(q('data'),q('log/mongod.log'),q('run/mongod.pid'),q('private/keyfile')))
print('prepared',p,'; no server started; credentials are private files')
