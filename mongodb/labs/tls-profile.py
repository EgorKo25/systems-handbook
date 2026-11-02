#!/usr/bin/env python3
"""Create a private TLS transport exercise for an already prepared, stopped LAB."""
import json,os,pathlib,subprocess,sys,urllib.parse
p=pathlib.Path(sys.argv[1]).expanduser().resolve();t=p/'private/tls'
if not (p/'mongod.yml').is_file() or t.exists():raise SystemExit('STOP: prepared LAB required and TLS profile must be new')
t.mkdir(mode=0o700)
def call(*args):subprocess.run(['openssl',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
for name in ('ca','wrong-ca'):
 call('req','-x509','-newkey','rsa:2048','-nodes','-sha256','-days','7','-subj','/CN=Handbook '+name,'-keyout',str(t/(name+'.key')),'-out',str(t/(name+'.pem')))
call('req','-newkey','rsa:2048','-nodes','-sha256','-subj','/CN=Handbook loopback','-keyout',str(t/'server.key'),'-out',str(t/'server.csr'))
(t/'server.ext').write_text('subjectAltName=IP:127.0.0.1\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
call('x509','-req','-sha256','-days','7','-in',str(t/'server.csr'),'-CA',str(t/'ca.pem'),'-CAkey',str(t/'ca.key'),'-CAcreateserial','-extfile',str(t/'server.ext'),'-out',str(t/'server.crt'))
(t/'server.pem').write_bytes((t/'server.key').read_bytes()+(t/'server.crt').read_bytes())
for f in t.iterdir():f.chmod(0o600)
q=lambda x:json.dumps(str(x))
s=(p/'mongod.yml').read_text().replace('net:\n','net:\n  tls:\n    mode: requireTLS\n    certificateKeyFile: '+q(t/'server.pem')+'\n    CAFile: '+q(t/'ca.pem')+'\n    allowConnectionsWithoutCertificates: true\n')
(p/'mongod-tls.yml').write_text(s)
uri='mongodb://127.0.0.1:27117/?replicaSet=study&retryWrites=true&tls=true&tlsCAFile='+urllib.parse.quote(str(t/'ca.pem'),safe='')
(t/'uri.txt').write_text(uri+'\n')
print('TLS profile created; SAN is only IP 127.0.0.1; no server started; certs expire in 7 days')
