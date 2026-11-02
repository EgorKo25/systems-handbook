#!/usr/bin/env python3
"""Real integration acceptance; explicit own new LAB and already verified binaries.
No package installation, public listener, reset, destructive failpoint or host service.
"""
import argparse,json,os,pathlib,socket,subprocess,time,urllib.request,urllib.error
ap=argparse.ArgumentParser();ap.add_argument('--lab',required=True);ap.add_argument('--mongod',required=True);ap.add_argument('--mongosh',required=True);ap.add_argument('--dbtools',required=True);ap.add_argument('--service',required=True);a=ap.parse_args()
root=pathlib.Path(__file__).resolve().parents[1];p=pathlib.Path(a.lab).resolve()
if p.exists():raise SystemExit('STOP: test LAB already exists')
for port in (27117,27118,18089):
 try:
  with socket.socket() as probe:
   probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',port))
 except OSError:raise SystemExit('STOP: test port is occupied: '+str(port))
env=dict(os.environ,LAB=str(p),MONGOSH_CONFIG_DIR=str(p/'shell-config'),MONGOSH_DISABLE_TELEMETRY='1',MONGO_AUTH_FILE=str(p/'private/app.json'),MONGO_URI='mongodb://127.0.0.1:27117/?replicaSet=study&retryWrites=true')
report={'kind':'native','server':'8.0.34','shell':'2.14.1','tools':'100.20.0','driver':'v2.9.2'};http=None;started=False;restored=False
uri='mongodb://127.0.0.1:27117/admin?directConnection=true';restore='mongodb://127.0.0.1:27118/?directConnection=true'
def run(args,extra=None,check=True):
 r=subprocess.run([str(x) for x in args],env=dict(env,**(extra or {})),text=True,capture_output=True,timeout=60)
 if check and r.returncode:raise RuntimeError('command failed '+str(args)+'\n'+r.stdout+'\n'+r.stderr)
 return r

def shell(code=None,action=None,target=uri):
 args=[a.mongosh,target,'--quiet','--norc']
 if action:args+=['--file',root/'labs/admin.js'];return run(args,{'ACTION':action})
 return run(args+['--eval',code])
auth='const fs=require("fs");const a=JSON.parse(fs.readFileSync(process.env.LAB+"/private/operator.json"));const r=db.getSiblingDB("admin").auth(a.username,a.password);if(r!==1&&r.ok!==1)throw Error("auth");'
def state(target=uri,authenticated=True):
 code=(auth if authenticated else '')+'const w=db.getSiblingDB("workshop");const h=require("crypto").createHash("sha256");for(const d of w.jobs.find({}).sort({_id:1}))h.update(EJSON.stringify(d,null,0,{relaxed:false})+"\\n");print(JSON.stringify({jobs:w.jobs.countDocuments({}),ledger:w.ledger.countDocuments({}),sha256:h.digest("hex"),index:w.jobs.getIndexes().some(x=>x.name==="tenant_state_recent")}));'
 return json.loads(shell(code,target=target).stdout.strip())
def post(path,data):
 req=urllib.request.Request('http://127.0.0.1:18089'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as r:return r.code,json.loads(r.read())
try:
 run(['python3',root/'labs/prepare.py',p])
 run([a.mongod,'--config',p/'mongod.yml','--fork']);started=True
 run([a.mongosh,uri,'--quiet','--norc','--file',root/'labs/bootstrap.js'],{'PHASE':'init'})
 for n in range(50):
  r=run([a.mongosh,uri,'--quiet','--norc','--eval','if(!db.hello().isWritablePrimary)quit(2)'],check=False)
  if not r.returncode:break
  time.sleep(.2)
 else:raise RuntimeError('primary did not become ready')
 run([a.mongosh,uri,'--quiet','--norc','--file',root/'labs/bootstrap.js'],{'PHASE':'users'})
 shell(action='accept');report['accept']=True
 shell('try{db.getSiblingDB("workshop").jobs.findOne();throw Error("unexpected access")}catch(e){if(e.code!==13)throw e;print("Unauthorized")}');report['anonymous_denied']=True
 shell(action='types');report['types']=True
 report['bson']=run([a.service,'-mode=bson']).stdout.strip();assert report['bson']=='22 bytes: 16000000106e002a00000002730003000000d18f0000'
 report['seed']=run([a.service,'-mode=seed','-n=20000']).stdout.strip();assert 'new=20000 ' in report['seed']
 assert 'new=0 ' in run([a.service,'-mode=seed','-n=20000']).stdout
 report['explain_before']=shell(action='explain').stdout.strip();assert 'totalDocsExamined: 20000' in report['explain_before']
 report['migration']=run([a.service,'-mode=migrate']).stdout.strip();assert 'modified=20000' in report['migration']
 assert 'modified=0 ' in run([a.service,'-mode=migrate']).stdout
 report['explain_after']=shell(action='explain').stdout.strip();assert 'totalDocsExamined: 20' in report['explain_after']
 # Identical post-migration data for both hint comparisons; no writes between them.
 report['natural']=run([a.service,'-mode=measure','-n=200','-hint=natural']).stdout.strip()
 report['index']=run([a.service,'-mode=measure','-n=200','-hint=tenant_state_recent']).stdout.strip()
 http=subprocess.Popen([a.service,'-mode=serve'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 for n in range(50):
  if http.poll() is not None:raise RuntimeError('own HTTP process exited before readiness')
  try:urllib.request.urlopen('http://127.0.0.1:18089/jobs?tenant=native',timeout=1).close();break
  except (OSError,urllib.error.HTTPError):time.sleep(.1)
 else:raise RuntimeError('HTTP service not ready')
 payload={'id':'http-example-1','tenant':'native','title':'Проверить часы'}
 first=post('/jobs',payload);again=post('/jobs',payload);assert first[0]==201 and again[0]==200 and first[1]==again[1],(first,again)
 assert post('/jobs',dict(payload,title='other'))[0]==409
 assert post('/jobs/http-example-1/close',{})==(200,{'modified':1})
 assert post('/jobs/http-example-1/close',{})==(200,{'modified':0})
 report['http_codes']=[201,200,409];report['close_modified']=[1,0]
 http.terminate();http.wait(timeout=10);report['httpExitCode']=http.returncode;assert http.returncode==0,'HTTP process did not exit cleanly';http=None
 run([a.service,'-mode=transaction']);run([a.service,'-mode=transaction'])
 report['before_restart']=state();assert report['before_restart']['jobs']==20001 and report['before_restart']['ledger']==1
 run([a.mongod,'--config',p/'mongod.yml','--shutdown']);started=False
 run([a.mongod,'--config',p/'mongod.yml','--fork']);started=True
 report['after_restart']=state();assert report['after_restart']==report['before_restart']
 archive=p/'backups/workshop.archive.gz'
 run([pathlib.Path(a.dbtools)/'mongodump','--config',p/'private/tools.yml','--db','workshop','--archive='+str(archive),'--gzip'])
 target=p/'restore';target.mkdir();(target/'data').mkdir()
 run([a.mongod,'--dbpath',target/'data','--port','27118','--bind_ip','127.0.0.1','--nounixsocket','--logpath',target/'mongod.log','--pidfilepath',target/'mongod.pid','--wiredTigerCacheSizeGB','0.25','--fork']);restored=True
 run([pathlib.Path(a.dbtools)/'mongorestore','--uri',restore,'--archive='+str(archive),'--gzip','--stopOnError'])
 report['restored']=state(restore,False);assert report['restored']==report['after_restart']
 run([a.mongosh,restore,'--quiet','--norc','--file',root/'labs/restore-accept.js'],{'EXPECTED_JOBS':'20001'})
 report['passed']=True
finally:
 if http is not None:http.terminate();http.wait(timeout=10)
 if restored:run([a.mongod,'--shutdown','--dbpath',p/'restore/data'],check=False)
 if started:run([a.mongod,'--config',p/'mongod.yml','--shutdown'],check=False)
 (p/'native-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
