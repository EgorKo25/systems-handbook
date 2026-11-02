#!/usr/bin/env python3
"""Real TLS exercise on an existing OWN stopped LAB; returns it stopped."""
import argparse,json,os,pathlib,socket,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--lab',required=True);p.add_argument('--mongod',required=True);p.add_argument('--mongosh',required=True);p.add_argument('--service',required=True);p.add_argument('--dbtools',required=True);a=p.parse_args();lab=pathlib.Path(a.lab).resolve();root=pathlib.Path(__file__).resolve().parents[1]
env=dict(os.environ,LAB=str(lab),MONGOSH_CONFIG_DIR=str(lab/'shell-config'),MONGOSH_DISABLE_TELEMETRY='1',MONGO_AUTH_FILE=str(lab/'private/app.json'))
def run(args,extra=None,ok=True):
 r=subprocess.run([str(x) for x in args],env=dict(env,**(extra or {})),text=True,capture_output=True,timeout=30)
 if ok and r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r
with socket.socket() as probe:
 try:probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',27117))
 except OSError:raise SystemExit('STOP: own LAB must be stopped; port27117 occupied')
run(['python3',root/'labs/tls-profile.py',lab]);t=lab/'private/tls';report={}
run([a.mongod,'--config',lab/'mongod-tls.yml','--fork'])
try:
 args=[a.mongosh,'mongodb://127.0.0.1:27117/admin?directConnection=true&serverSelectionTimeoutMS=1500','--quiet','--norc','--tls','--tlsCAFile',t/'ca.pem']
 for n in range(30):
  r=run(args+['--file',root/'labs/admin.js'],{'ACTION':'accept'},ok=False)
  if r.returncode==0:break
  time.sleep(.2)
 else:raise RuntimeError('TLS accepted configuration not ready: '+r.stderr)
 report['trustedCA_and_IP']=r.returncode==0
 for name,uri,ca in [('wrongCA','127.0.0.1',t/'wrong-ca.pem'),('wrongName','localhost',t/'ca.pem')]:
  r=run([a.mongosh,'mongodb://'+uri+':27117/admin?directConnection=true&serverSelectionTimeoutMS=1500','--quiet','--norc','--tls','--tlsCAFile',ca,'--eval','db.runCommand({ping:1})'],ok=False)
  assert r.returncode!=0 and any(x in r.stderr.lower() for x in ['certificate','hostname','self-signed','does not match']),r.stderr
  report[name]={'exit':r.returncode,'rejected':True}
 r=run([a.mongosh,'mongodb://127.0.0.1:27117/admin?directConnection=true&serverSelectionTimeoutMS=1500','--quiet','--norc','--eval','db.runCommand({ping:1})'],ok=False);assert r.returncode!=0;report['plaintext']={'exit':r.returncode,'rejected':True}
 uri=(t/'uri.txt').read_text().strip();r=run([a.service,'-mode=check'],{'MONGO_URI':uri});report['go_tls']=r.stdout.strip()
 archive=lab/'backups/tls-probe.archive.gz'
 if archive.exists():raise RuntimeError('STOP archive exists')
 r=run([pathlib.Path(a.dbtools)/'mongodump','--config',lab/'private/tools.yml','--ssl','--sslCAFile',t/'ca.pem','--db','workshop','--archive='+str(archive),'--gzip']);report['tools_tls']=r.returncode==0
 report['passed']=True
finally:run([a.mongod,'--config',lab/'mongod-tls.yml','--shutdown'],ok=False)
(lab/'tls-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
