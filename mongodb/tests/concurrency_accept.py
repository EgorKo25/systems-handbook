#!/usr/bin/env python3
"""Own stopped TEST LAB only. Concurrent HTTP correctness, not a load benchmark.
Uses already prepared data/credentials; does not reseed, restore or reset.
--service should name an independently built public source with go build -race.
"""
import argparse,collections,concurrent.futures,datetime,hashlib,json,os,pathlib,socket,subprocess,threading,time,urllib.request,urllib.error
ap=argparse.ArgumentParser()
for name in ('lab','mongod','mongosh','service','case-id'):ap.add_argument('--'+name,required=True)
a=ap.parse_args();lab=pathlib.Path(a.lab).resolve();root=pathlib.Path(__file__).resolve().parents[1]
if not (lab/'private/app.json').is_file() or not (lab/'mongod.yml').is_file():raise SystemExit('STOP: prepared OWN stopped TEST LAB required')
if not a.case_id or len(a.case_id)>50 or not all(c.isalnum() or c in '-_' for c in a.case_id):raise SystemExit('STOP: simple new case-id required')
for port in (27117,18089):
 try:
  with socket.socket() as probe:
   probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);probe.bind(('127.0.0.1',port))
 except OSError:raise SystemExit('STOP: own test port occupied '+str(port))
env=dict(os.environ,LAB=str(lab),MONGO_URI='mongodb://127.0.0.1:27117/?replicaSet=study&retryWrites=true',MONGO_AUTH_FILE=str(lab/'private/app.json'),MONGOSH_CONFIG_DIR=str(lab/'shell-config'),MONGOSH_DISABLE_TELEMETRY='1',GORACE='halt_on_error=1 exitcode=66')
report={'kind':'real concurrent loopback HTTP with database inspection','clients':16,'caseId':a.case_id,'serviceSha256':hashlib.sha256(pathlib.Path(a.service).read_bytes()).hexdigest(),'codeSha256':hashlib.sha256((root/'labs/service/main.go').read_bytes()).hexdigest(),'unknownOutcomes':[]}
log=lab/'log';stdout=log/(a.case_id+'.stdout');stderr=log/(a.case_id+'.stderr');result=lab/(a.case_id+'.json')
if any(p.exists() for p in (stdout,stderr,result)):raise SystemExit('STOP: existing case artifacts; choose a new case-id')
http=None;started=False

def run(args,check=True):
 r=subprocess.run([str(x) for x in args],env=env,text=True,capture_output=True,timeout=30)
 if check and r.returncode:raise RuntimeError('local command failed '+str(r.returncode)+' '+r.stderr)
 return r

def inspect(id):
 literal=json.dumps(id)
 js='const fs=require("fs");const a=JSON.parse(fs.readFileSync(process.env.LAB+"/private/operator.json"));const r=db.getSiblingDB("admin").auth(a.username,a.password);if(r!==1&&r.ok!==1)throw Error("auth");const c=db.getSiblingDB("workshop").jobs;const d=c.findOne({_id:'+literal+'});const t=d?d.version._bsontype:null;if(d){if(t!=="Long")throw Error("version BSON type changed");d.version=d.version.toNumber();}print(JSON.stringify({count:c.countDocuments({_id:'+literal+'}),document:d,versionBsonType:t}));'
 r=run([a.mongosh,'mongodb://127.0.0.1:27117/admin?directConnection=true','--quiet','--norc','--eval',js]);return json.loads(r.stdout.strip())

def post(path,body,barrier=None):
 if barrier:barrier.wait(timeout=15)
 req=urllib.request.Request('http://127.0.0.1:18089'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=10) as r:return {'status':r.status,'body':json.loads(r.read())}
 except urllib.error.HTTPError as r:return {'status':r.code,'body':json.loads(r.read())}
 except (OSError,ValueError) as e:return {'status':None,'errorType':type(e).__name__}

def simultaneous(requests):
 barrier=threading.Barrier(len(requests))
 with concurrent.futures.ThreadPoolExecutor(max_workers=len(requests)) as pool:
  futures=[pool.submit(post,path,body,barrier) for path,body in requests]
  return [f.result(timeout=20) for f in futures]

def known(name,responses):
 unknown=[r for r in responses if r['status'] is None or r['status']>=500]
 report['unknownOutcomes'] += [{'phase':name,'response':r} for r in unknown]
 assert not unknown,'STOP: unknown write outcome; inspect by ID, do not retry invisibly'

def counters(responses):return {str(k):v for k,v in collections.Counter(r['status'] for r in responses).items()}
def date(value):return datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
try:
 run([a.mongod,'--config',lab/'mongod.yml','--fork']);started=True
 for n in range(40):
  r=run([a.mongosh,'mongodb://127.0.0.1:27117/admin?directConnection=true','--quiet','--norc','--eval','if(!db.hello().isWritablePrimary)quit(2)'],check=False)
  if r.returncode==0:break
  time.sleep(.2)
 else:raise RuntimeError('primary not ready')
 sameid='same-'+a.case_id;mixedid='mixed-'+a.case_id
 for id in (sameid,mixedid):assert inspect(id)['count']==0,'STOP: existing test ID; no mutation performed'
 with stdout.open('xb') as out,stderr.open('xb') as err:
  http=subprocess.Popen([a.service,'-mode=serve'],env=env,stdout=out,stderr=err)
  for n in range(50):
   if http.poll() is not None:raise RuntimeError('own HTTP process exited before readiness')
   try:urllib.request.urlopen('http://127.0.0.1:18089/jobs?tenant=concurrency',timeout=1).close();break
   except (OSError,urllib.error.HTTPError):time.sleep(.1)
  else:raise RuntimeError('HTTP not ready')
  one={'id':sameid,'tenant':'concurrency-same','title':'Один исходный payload'}
  responses=simultaneous([('/jobs',one)]*16);known('samePayload',responses)
  assert counters(responses)=={'201':1,'200':15},counters(responses)
  created=next(r['body'] for r in responses if r['status']==201)
  assert all(r['body']==created for r in responses),'same ID/payload returned different stored fields'
  initial=inspect(sameid);d=initial['document'];assert initial['count']==1 and d['tenant']==one['tenant'] and d['title']==one['title'] and d['version']==1 and d['state']=='open' and d['schemaVersion']==2
  assert date(d['createdAt'])==date(created['createdAt'])
  report['samePayload']={'responses':counters(responses),'records':initial['count'],'version':d['version'],'versionBsonType':initial['versionBsonType'],'fieldsUnchanged':True}
  left={'id':mixedid,'tenant':'concurrency-A','title':'Payload A'};right={'id':mixedid,'tenant':'concurrency-B','title':'Payload B'}
  inputs=[left,right]*8
  responses=simultaneous([('/jobs',p) for p in inputs]);known('competingPayloads',responses)
  assert sum(r['status']==201 for r in responses)==1
  winner=next(r['body'] for r in responses if r['status']==201)
  for payload,response in zip(inputs,responses):
   matching=payload['tenant']==winner['tenant'] and payload['title']==winner['title']
   assert response['status'] in (200,201) if matching else response['status']==409
   if matching:assert response['body']==winner
  mixed=inspect(mixedid);m=mixed['document'];assert mixed['count']==1 and m['tenant']==winner['tenant'] and m['title']==winner['title'] and m['version']==1 and m['state']=='open' and m['schemaVersion']==2
  assert date(m['createdAt'])==date(winner['createdAt'])
  assert collections.Counter(r['status'] for r in responses)=={201:1,409:8,200:7}
  report['competingPayloads']={'responses':counters(responses),'records':mixed['count'],'winnerTenant':winner['tenant'],'version':m['version'],'versionBsonType':mixed['versionBsonType'],'fieldsUnchanged':True}
  closes=simultaneous([('/jobs/'+sameid+'/close',{})]*16);known('parallelClose',closes)
  assert all(r['status']==200 for r in closes)
  modified=collections.Counter(r['body'].get('modified') for r in closes);assert modified=={1:1,0:15},modified
  closed=inspect(sameid);cd=closed['document'];expected=dict(d,state='closed',version=2);assert closed['count']==1 and cd==expected,'parallel close changed original fields or version unexpectedly'
  after=post('/jobs',one);known('readAcceptedAgain',[after]);assert after['status']==200 and after['body']['state']=='closed' and after['body']['version']==2
  assert inspect(mixedid)==mixed,'competing payload overwrote the winner'
  report['parallelClose']={'responses':counters(closes),'modified':{str(k):v for k,v in modified.items()},'records':closed['count'],'version':cd['version'],'state':cd['state'],'versionBsonType':closed['versionBsonType'],'otherFieldsUnchanged':True}
  http.terminate();http.wait(timeout=15);report['httpExitCode']=http.returncode;http=None
  assert report['httpExitCode']==0,'HTTP process did not exit cleanly; inspect private stderr'
  diagnostic=stderr.read_text(errors='replace');assert 'DATA RACE' not in diagnostic and 'WARNING: DATA RACE' not in diagnostic
  report['raceDiagnosticDetected']=False;report['stderrKeptPrivate']=True;report['passed']=True
finally:
 if http is not None:
  http.terminate();http.wait(timeout=15);report['httpExitCode']=http.returncode
 if started:run([a.mongod,'--config',lab/'mongod.yml','--shutdown'],check=False)
 result.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
