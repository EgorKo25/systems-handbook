#!/usr/bin/env python3
"""Own native Grafana + mock Prometheus transport, loopback only; never system service.
No real external notifications, datasource, PromQL engine or browser renderer.
"""
import argparse,base64,contextlib,copy,hashlib,http.server,json,os,shutil,socket,subprocess,tempfile,threading,time,urllib.request,urllib.error,urllib.parse,sqlite3,yaml,statistics,platform
from query_payload import payload as query_payload
from pathlib import Path
from labctl import initialize

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def run(home,out):
 records=[];requests=[];traces=[];measurements={"startup_seconds":[],"platform":platform.system()+" "+platform.machine()};fixture='not-a-real-credential';process=None
 class Mock(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self):
   length=int(self.headers.get('Content-Length','0'));body=self.rfile.read(length).decode() if length else ''
   requests.append({'path':self.path,'body':body,'has_fixture_header':self.headers.get('X-Lab-Fixture')==fixture})
   if self.headers.get('X-Lab-Fixture')!=fixture:
    self.send_response(401);self.end_headers();self.wfile.write(b'fixture header required');return
   if 'buildinfo' in self.path:d={'status':'success','data':{'version':'3.13.5'}}
   elif 'query_range' in self.path:
    params=urllib.parse.parse_qs(body or urllib.parse.urlsplit(self.path).query);start=float(params['start'][0]);end=float(params['end'][0]);step=float(params['step'][0]);table=[[1699999980,'0'],[1699999995,'1'],[1700000010,'2'],[1700000025,'3']];values=[x for x in table if start<=x[0]<=end and (x[0]-start)%step==0]
    d={'status':'success','data':{'resultType':'matrix','result':[{'metric':{'__name__':'lab_inflight_requests','job':'go-lab','instance':'127.0.0.1:18080'},'values':values}]}}
   elif 'query' in self.path:d={'status':'success','data':{'resultType':'vector','result':[{'metric':{'job':'go-lab'},'value':[1700000030,'1']}]}}
   else:d={'status':'success','data':[]}
   b=json.dumps(d).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b)
  do_GET=reply;do_POST=reply
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='grafana-native-check-') as tmp:
   root=initialize(Path(tmp)/'persistent lab with spaces',port());cfg=root/'config/grafana.ini';text=cfg.read_text();grafana_port=int(next(x.split('=',1)[1] for x in text.splitlines() if x.startswith('http_port')))
   ds=root/'provisioning/datasources/prometheus.yaml';data=yaml.safe_load(ds.read_text());d=data['datasources'][0];d['url']=f'http://127.0.0.1:{server.server_port}';d['jsonData']['httpHeaderName1']='X-Lab-Fixture';d['secureJsonData']={'httpHeaderValue1':fixture};ds.write_text(yaml.safe_dump(data))
   password=(root/'private/admin-password').read_text();base=f'http://127.0.0.1:{grafana_port}';env={k:v for k,v in os.environ.items() if not k.startswith('GF_')}
   def api(path,payload=None,user='labadmin',pw=password):
    headers={'Authorization':'Basic '+base64.b64encode((user+':'+pw).encode()).decode()}
    if payload is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    try:
     with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:
     b=e.read().decode()
     try:return e.code,json.loads(b)
     except json.JSONDecodeError:return e.code,{'body_length':len(b)}
   def check(name,test):
    if not test:raise AssertionError(name)
    records.append({'check':name,'result':'PASS'})
   def start():
    nonlocal process
    start_time=time.monotonic()
    log=open(root/'logs/native.log','ab');process=subprocess.Popen([str(home/'bin/grafana'),'server','--homepath',str(home),'--config',str(cfg)],stdout=log,stderr=subprocess.STDOUT,env=env);log.close()
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
     if process.poll() is not None:raise AssertionError('native server exited; inspect private temp log while debugging')
     try:
      status,result=api('/api/health')
      if status==200 and result.get('database')=='ok':
       measurements['startup_seconds'].append(round(time.monotonic()-start_time,3));return
     except (urllib.error.URLError,TimeoutError):pass
     time.sleep(.25)
    raise AssertionError('health timeout')
   def stop():
    nonlocal process
    if process is not None and process.poll() is None:
     process.terminate()
     try:process.wait(timeout=20)
     except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    process=None
   try:
    start();check('native health reports version13.3.0',api('/api/health')[1].get('version')=='13.3.0')
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
     status,dash=api('/api/dashboards/uid/go-service-lab')
     if status==200:break
     time.sleep(.3)
    check('file-provisioned dashboard UID and folder UID',status==200 and dash['dashboard']['uid']=='go-service-lab' and dash['meta']['folderUid']=='handbook-go')
    status,source=api('/api/datasources/uid/prom-local');check('datasource UID stable and secure data redacted',status==200 and source.get('secureJsonFields',{}).get('httpHeaderValue1') is True and fixture not in json.dumps(source))
    q=query_payload(15000)
    status,response=api('/api/ds/query',q);check('native builtin Prometheus plugin returns data frame from mock API',status==200 and bool(response.get('results',{}).get('A',{}).get('frames')))
    traces.append({'intervalMs':15000,'request':q,'upstream':requests[-1],'response':response})
    q30=query_payload(30000);code,response30=api('/api/ds/query',q30);check('second interval produces native frame from same authored table',code==200 and bool(response30.get('results',{}).get('A',{}).get('frames')));traces.append({'intervalMs':30000,'request':q30,'upstream':requests[-1],'response':response30})
    check('backend used query_range and decrypted fixture header',any('query_range' in x['path'] and x['has_fixture_header'] for x in requests))
    secure={'name':'Native Secure Persist','uid':'native-secure','type':'prometheus','access':'proxy','url':f'http://127.0.0.1:{server.server_port}','jsonData':{'httpMethod':'POST','httpHeaderName1':'X-Lab-Fixture','timeInterval':'15s'},'secureJsonData':{'httpHeaderValue1':fixture}}
    check('create API-only datasource outside provisioning',api('/api/datasources',secure)[0]==200)
    q_secure=copy.deepcopy(q);q_secure['queries'][0]['datasource']['uid']='native-secure'
    check('API-only datasource initially authenticates to strict mock',api('/api/ds/query',q_secure)[0]==200)

    payload={'dashboard':{'id':None,'uid':'native-persist','title':'Native persistence check','schemaVersion':41,'version':0,'panels':[]},'overwrite':False,'folderUid':'handbook-go'}
    check('legacy API creates separate owned dashboard',api('/api/dashboards/db',payload)[0]==200)
    edited=copy.deepcopy(dash['dashboard']);edited['title']='forbidden UI drift';code,_=api('/api/dashboards/db',{'dashboard':edited,'overwrite':True,'folderUid':'handbook-go'});check('file provisioning rejects UI/API overwrite',code in [400,403])
    viewer_password='fixture-viewer-local-only';code,user=api('/api/admin/users',{'name':'Fixture Viewer','email':'viewer@example.invalid','login':'fixtureviewer','password':viewer_password});check('create isolated local viewer',code==200)
    roles=api('/api/org/users')[1];check('new user has Viewer basic role',any(x.get('login')=='fixtureviewer' and x.get('role')=='Viewer' for x in roles))
    check('OSS Viewer can query datasource',api('/api/ds/query',q,'fixtureviewer',viewer_password)[0]==200)
    check('OSS Viewer cannot save dashboard',api('/api/dashboards/db',payload,'fixtureviewer',viewer_password)[0]==403)
    discovery=[]
    for version in ['v1','v1beta1']:
     code,body=api('/apis/dashboard.grafana.app/'+version+'/namespaces/default/dashboards/go-service-lab');discovery.append({'version':version,'status':code})
    check('new dashboard APIs v1 and v1beta1 both return200',all(x['status']==200 for x in discovery))
    stop();con=sqlite3.connect(root/'data/grafana.db');stored=con.execute('select secure_json_data from data_source where uid=?',('native-secure',)).fetchone()[0];con.close();check('datasource fixture value not plaintext in secure_json_data',fixture not in stored)
    start();check('dashboard persists after same-data-dir restart',api('/api/dashboards/uid/native-persist')[0]==200);check('provisioned UID persists after restart',api('/api/dashboards/uid/go-service-lab')[1]['dashboard']['uid']=='go-service-lab');before=len(requests);code,body=api('/api/ds/query',q_secure)
    check('API-only secret decrypts after restart and strict mock sees new header',code==200 and bool(body.get('results',{}).get('A',{}).get('frames')) and any('query_range' in x['path'] and x['has_fixture_header'] for x in requests[before:]))
    check('persistent init refuses reset',refuse_init(root))
    stop()
    original=root;original_hash=hashlib.sha256((original/'data/grafana.db').read_bytes()).hexdigest()
    backup=Path(tmp)/'consistent backup';shutil.copytree(original,backup)
    restored=Path(tmp)/'separate restored lab';shutil.copytree(backup,restored)
    previous_port=grafana_port;grafana_port=port();root=restored;cfg=root/'config/grafana.ini'
    config=cfg.read_text().replace(str(original),str(restored)).replace('http_port = '+str(previous_port),'http_port = '+str(grafana_port)).replace(':'+str(previous_port)+'/',':'+str(grafana_port)+'/');cfg.write_text(config)
    provider=root/'provisioning/dashboards/handbook.yaml';provider.write_text(provider.read_text().replace(str(original),str(restored)))
    base=f'http://127.0.0.1:{grafana_port}'
    start();check('isolated consistent SQLite copy restores dashboard UID',api('/api/dashboards/uid/native-persist')[0]==200)
    before=len(requests);code,body=api('/api/ds/query',q_secure)
    check('isolated restore decrypts API-only secret with preserved key',code==200 and bool(body.get('results',{}).get('A',{}).get('frames')) and any(x['has_fixture_header'] for x in requests[before:]))
    samples=[]
    for _ in range(20):
     began=time.perf_counter();code,health=api('/api/health');assert code==200;samples.append((time.perf_counter()-began)*1000)
    measurements['health20_median_ms']=round(statistics.median(samples),3);measurements['health20_max_ms']=round(max(samples),3)
    status_text=Path('/proc')/str(process.pid)/'status'
    if status_text.exists():measurements['own_process_rss_kib']=int(next(x.split()[1] for x in status_text.read_text().splitlines() if x.startswith('VmRSS:')))
    stop();measurements['stopped_sqlite_bytes']=(root/'data/grafana.db').stat().st_size
    check('isolated restore did not change original DB bytes',hashlib.sha256((original/'data/grafana.db').read_bytes()).hexdigest()==original_hash)

    # Parser observations use actual binary, no server or plugin install.
    good=subprocess.run([str(home/'bin/grafana'),'server','--homepath',str(home),'--config',str(cfg),'--version'],text=True,capture_output=True,env=env)
    bad=subprocess.run([str(home/'bin/grafana'),'--homepath',str(home),'server','--version'],text=True,capture_output=True,env=env)
    check('server-local config flags accepted including path with spaces',good.returncode==0 and '13.3.0' in good.stdout);check('server-local flag at global scope rejected',bad.returncode!=0)
   finally:stop()
 finally:server.shutdown();server.server_close()
 result={'version':'13.3.0 OSS','checks':records,'mock_boundary':'Prometheus HTTP responses are authored; no PromQL evaluation or real scrape. Native Grafana/plugin/API/SQLite actually executed. No browser render, TLS, shared-DB HA or alert delivery tested. Isolated stopped-SQLite copy/keys restore is tested.','mock_requests':requests,'query_traces':traces,'measurements':measurements}
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'native_checks':len(records),'result':'PASS','output':out.name},ensure_ascii=False))
def refuse_init(root):
 try:initialize(root)
 except ValueError:return True
 return False
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--grafana-home',type=Path,required=True);a.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'verified-native.json');n=a.parse_args();home=n.grafana_home.resolve()
 if not (home/'bin/grafana').is_file():a.error('missing verified native binary')
 run(home,n.output)
