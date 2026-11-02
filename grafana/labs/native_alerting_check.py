#!/usr/bin/env python3
"""Real isolated Grafana Alerting; authored Prometheus responses and own loopback webhook.
No system service, people, SMTP, cloud, plugins or external notification addresses.
Every phase is bounded; all three own processes/listeners are cleaned up in finally.
"""
import argparse,base64,http.server,shutil,json,os,socket,subprocess,tempfile,threading,time,urllib.request,urllib.error
from pathlib import Path
from labctl import initialize

def free_port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def run(home,output):
 process=None;mode='low';events=[];observations=[];checks=[];started=time.monotonic()
 class Source(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self):
   self.rfile.read(int(self.headers.get('Content-Length','0')))
   if mode=='error':
    self.send_response(500);self.end_headers();self.wfile.write(b'authored source failure');return
   rows=[] if mode=='empty' else [{'metric':{'instance':'fixture'},'value':[time.time(),'0.9' if mode=='high' else '0.2']}]
   body={'status':'success','data':{'resultType':'vector','result':rows}}
   if 'buildinfo' in self.path:body={'status':'success','data':{'version':'3.13.5'}}
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())
  do_POST=reply;do_GET=reply
 class Hook(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_POST(self):
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   events.append({'elapsed_seconds':round(time.monotonic()-started,2),'payload':body})
   self.send_response(200);self.end_headers();self.wfile.write(b'ok')
 source=http.server.ThreadingHTTPServer(('127.0.0.1',0),Source)
 hook=http.server.ThreadingHTTPServer(('127.0.0.1',0),Hook)
 for server in [source,hook]:threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='grafana-alerting-check-') as tmp:
   root=initialize(Path(tmp)/'alert lab',free_port());cfg=root/'config/grafana.ini'
   (root/'provisioning/alerting').mkdir(exist_ok=True);shutil.copyfile(Path(__file__).parent/'provisioning/alerting/error-ratio-paused.yaml',root/'provisioning/alerting/paused.yaml')
   text=cfg.read_text().replace('[unified_alerting]\nenabled = false','[unified_alerting]\nenabled = true\nallowed_integrations = webhook\nadmin_config_poll_interval = 1s\nalertmanager_config_poll_interval = 1s\nevaluation_timeout = 5s\nmax_attempts = 1\nmin_interval = 10s\nha_listen_address = 127.0.0.1:'+str(free_port())+'\nha_peers =')
   cfg.write_text(text);gport=int(next(x.split('=',1)[1] for x in text.splitlines() if x.startswith('http_port')))
   base=f'http://127.0.0.1:{gport}';password=(root/'private/admin-password').read_text()
   env={k:v for k,v in os.environ.items() if not k.startswith('GF_')}
   def api(path,payload=None,method=None):
    h={'Authorization':'Basic '+base64.b64encode(('labadmin:'+password).encode()).decode(),'Content-Type':'application/json'}
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=h,method=method)
    try:
     with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,e.read().decode()
   def check(name,value):
    if not value:raise AssertionError(name)
    checks.append({'check':name,'result':'PASS'})
   def expect(path,payload,method='POST',statuses=(200,201,202)):
    code,body=api(path,payload,method)
    if code not in statuses:raise AssertionError(f'{method} {path}: {code} {body}')
    return body
   log=open(root/'logs/native-alerting.log','wb')
   process=subprocess.Popen([str(home/'bin/grafana'),'server','--homepath',str(home),'--config',str(cfg)],stdout=log,stderr=subprocess.STDOUT,env=env);log.close()
   deadline=time.monotonic()+90
   while time.monotonic()<deadline:
    if process.poll() is not None:raise AssertionError('Grafana exited: '+(root/'logs/native-alerting.log').read_text()[-5000:])
    try:
     if api('/api/health')[0]==200:break
    except (urllib.error.URLError,TimeoutError):pass
    time.sleep(.25)
   else:raise AssertionError('health timeout')
   code,paused=api('/api/v1/provisioning/alert-rules/go-error-ratio');check('file-provisioned paused rule parsed and preserves30s recovery',code==200 and paused.get('isPaused') is True and paused.get('keep_firing_for')=='30s')
   expect('/api/datasources',{'name':'Alert Fixture','uid':'alert-fixture','type':'prometheus','access':'proxy','url':f'http://127.0.0.1:{source.server_port}','jsonData':{'httpMethod':'POST','timeInterval':'10s'}})
   expect('/api/folders',{'uid':'alert-fixtures','title':'Alert Fixtures'})
   expect('/api/v1/provisioning/contact-points',{'uid':'own-loopback','name':'OwnLoopback','type':'webhook','settings':{'url':f'http://127.0.0.1:{hook.server_port}/own-hook','httpMethod':'POST'},'disableResolveMessage':False})
   expect('/api/v1/provisioning/policies',{'receiver':'OwnLoopback','group_by':['alertname'],'group_wait':'0s','group_interval':'5s','repeat_interval':'1h'},'PUT')
   rule={'uid':'native-state-rule','title':'Native state fixture','folderUID':'alert-fixtures','ruleGroup':'native-states','condition':'C','noDataState':'NoData','execErrState':'Error','for':'20s','keep_firing_for':'20s','isPaused':False,'labels':{'service':'authored-fixture'},'annotations':{'summary':'Own loopback test only'},'data':[
    {'refId':'A','datasourceUid':'alert-fixture','relativeTimeRange':{'from':60,'to':0},'model':{'refId':'A','expr':'lab_probe','instant':True,'range':False,'intervalMs':10000,'maxDataPoints':10}},
    {'refId':'B','datasourceUid':'__expr__','relativeTimeRange':{'from':0,'to':0},'model':{'refId':'B','type':'reduce','expression':'A','reducer':'last'}},
    {'refId':'C','datasourceUid':'__expr__','relativeTimeRange':{'from':0,'to':0},'model':{'refId':'C','type':'threshold','expression':'B','conditions':[{'evaluator':{'params':[.7],'type':'gt'},'operator':{'type':'and'},'query':{'params':['C']},'reducer':{'type':'last'}}]}}]}
   expect('/api/v1/provisioning/folder/alert-fixtures/rule-groups/native-states',{'title':'native-states','folderUid':'alert-fixtures','interval':10,'rules':[rule]},'PUT')
   check('API preserves explicit keep_firing_for',api('/api/v1/provisioning/alert-rules/native-state-rule')[1].get('keep_firing_for')=='20s')
   check('API config creates 10s evaluation group and loopback-only notification route',api('/api/v1/provisioning/folder/alert-fixtures/rule-groups/native-states')[1].get('interval')==10 and api('/api/v1/provisioning/policies')[1].get('receiver')=='OwnLoopback')
   def snapshot():
    code,body=api('/api/prometheus/grafana/api/v1/rules')
    if code!=200:raise AssertionError(str((code,body)))
    rules=[r for g in body.get('data',{}).get('groups',[]) for r in g.get('rules',[]) if r.get('name')=='Native state fixture']
    r=rules[0] if rules else {}
    sample={'elapsed_seconds':round(time.monotonic()-started,2),'mode':mode,'state':r.get('state'),'health':r.get('health'),'lastError':r.get('lastError'),'alerts':[{'state':a.get('state'),'labels':a.get('labels',{}),'activeAt':a.get('activeAt')} for a in r.get('alerts',[])]}
    if not observations or any(sample[k]!=observations[-1][k] for k in ['mode','state','health','alerts']):observations.append(sample)
    return sample
   def wait_for(label,predicate,seconds=55):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
     sample=snapshot()
     if sample.get('health')=='error' and mode in ['low','high']:raise AssertionError('unexpected evaluator error '+json.dumps(sample))
     if predicate(sample):return sample
     time.sleep(.5)
    raise AssertionError(label+' timeout: '+json.dumps(observations[-5:])+' LOG '+(root/'logs/native-alerting.log').read_text()[-5000:])
   wait_for('normal',lambda s:s['state']=='inactive');check('low numeric input is Normal/inactive',True)
   mode='high';wait_for('pending',lambda s:s['state']=='pending');check('high numeric input enters Pending',True)
   wait_for('firing',lambda s:s['state']=='firing');check('persistent high input reaches Alerting/firing after pending',True)
   wait_for('local firing webhook',lambda s:any(e['payload'].get('status')=='firing' and any(a['labels'].get('alertname')=='Native state fixture' for a in e['payload'].get('alerts',[])) for e in events),seconds=30)
   check('actual notification route sends firing payload to own loopback receiver',True)
   mode='low';wait_for('recovering',lambda s:any(a.get('state')=='Recovering' for a in s['alerts']));check('low input enters Recovering with keepFiringFor',True)
   wait_for('normal again',lambda s:s['state']=='inactive');check('recovery interval ends in Normal',True)
   wait_for('resolved webhook',lambda s:any(e['payload'].get('status')=='resolved' for e in events),seconds=30);check('own loopback receiver receives resolved payload',True)
   mode='empty';wait_for('NoData pending',lambda s:s['state']=='pending');check('empty source result honors configured Pending',True)
   wait_for('NoData firing',lambda s:any(a.get('state')=='NoData' for a in s['alerts']));check('empty source result creates DatasourceNoData after pending',True)
   wait_for('NoData local webhook',lambda s:any(a['labels'].get('alertname')=='DatasourceNoData' for e in events for a in e['payload'].get('alerts',[])),seconds=20);check('own receiver gets separate DatasourceNoData labels',True)
   mode='low';wait_for('normal before error',lambda s:s['state']=='inactive' and s['health']=='ok' and all(a['state']=='Normal' for a in s['alerts']))
   mode='error';wait_for('Error pending',lambda s:s['state']=='pending');check('source HTTP500 honors configured Pending',True)
   wait_for('Error firing',lambda s:any(a.get('state')=='Error' for a in s['alerts']));check('source HTTP500 creates DatasourceError after pending',True)
   wait_for('Error local webhook',lambda s:any(a['labels'].get('alertname')=='DatasourceError' for e in events for a in e['payload'].get('alerts',[])),seconds=20);check('own receiver gets separate DatasourceError labels',True)
   check('every received webhook targets own fixture rule or datasource event',all(a.get('labels',{}).get('service')=='authored-fixture' for e in events for a in e['payload'].get('alerts',[])))
 finally:
  if process is not None and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=15)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  for server in [source,hook]:server.shutdown();server.server_close()
 result={'version':'13.3.0 OSS','boundary':'Native evaluator and native notification router actually executed. Prometheus responses are authored; no PromQL, real scrape, external notifications, browser, SMTP or HA tested. Temporary DB and listeners removed.','checks':checks,'observations':observations,'webhooks':events}
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'native_alerting_checks':len(checks),'result':'PASS','seconds':round(time.monotonic()-started,1)}))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--grafana-home',type=Path,required=True);a.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'verified-native-alerting.json');args=a.parse_args();run(args.grafana_home.resolve(),args.output)
