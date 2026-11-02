#!/usr/bin/env python3
"""Fail-closed Bash control-flow checks. Explicit fake clients, never a cluster test."""
from pathlib import Path
import os,subprocess,tempfile,json,sys
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='argocd-guard-check-') as tmp:
 p=Path(tmp);bin_dir=p/'bin';bin_dir.mkdir();log=p/'calls.jsonl'
 # Absolute interpreter avoids recursion through the explicit python3 stub.
 header='#!'+sys.executable+'\n'
 fake=bin_dir/'kubectl';fake.write_text(header+'''import json,os,sys
args=sys.argv[1:];scenario=os.environ['SCENARIO']
with open(os.environ['FAKE_CALLS'],'a') as f:f.write(json.dumps(['kubectl',*args])+'\\n')
def fail():raise SystemExit(43)
if scenario=='first':fail()
if 'config' in args and 'view' in args:
 print('https://wrong.example.invalid:6443' if scenario=='restore-endpoint' else 'https://restore.example.invalid:6443');raise SystemExit(0)
if 'get' in args and 'namespace' in args and 'kube-system' in args:
 print('old-uid' if 'own-test-context' in args or scenario=='restore-same-cluster' else 'restore-uid');raise SystemExit(0)
if 'get' in args and 'namespace' in args and 'argocd' in args and any('restore}' in x for x in args):
 print('' if scenario=='restore-marker' else 'quarantine');raise SystemExit(0)
if 'scale' in args:
 if scenario=='restore-notification-scale' and 'deployment/argocd-notifications-controller' in args:fail()
 if scenario=='restore-appset-scale' and 'deployment/argocd-applicationset-controller' in args:fail()
 if scenario=='restore-app-scale' and 'statefulset/argocd-application-controller' in args:fail()
if 'get' in args and 'pods' in args:
 if scenario=='restore-pods-read':fail()
 print(json.dumps({'items':[]}));raise SystemExit(0)
if 'get' in args and 'namespace' in args:
 if scenario=='namespace-create':raise SystemExit(0)
 print(json.dumps({'metadata':{'labels':{'handbook.example/owner':'argocd-lab'}}}));raise SystemExit(0)
if 'create' in args and '-f' in args and scenario=='namespace-create':fail()
if 'apply' in args:
 dry='--dry-run=server' in args
 if scenario=='install-dry-run' and dry:fail()
 if scenario=='install-apply' and not dry:fail()
 if args[-1].endswith('/project.yaml'):
  if scenario=='project-dry-run' and dry:fail()
  if scenario=='project-apply' and not dry:fail()
 if args[-1].endswith('/application.yaml'):
  if scenario=='app-dry-run' and dry:fail()
  if scenario=='app-apply' and not dry:fail()
if 'wait' in args:
 if scenario=='crd-ready' and '--for=condition=Established' in args:fail()
 if scenario=='deployment-ready' and '--for=condition=Available' in args:fail()
if 'statefulset/argocd-application-controller' in args and scenario=='controller-ready':fail()
if 'get' in args and 'secret' in args:
 if scenario=='certificate-fetch':fail()
 if scenario=='certificate-empty':raise SystemExit(0)
 print('ZmFrZS1jZXJ0aWZpY2F0ZS1ieXRlcw==') # only guard-flow fixture, not a real cert
''');fake.chmod(0o755)
 argo=bin_dir/'argocd';argo.write_text(header+'''import os,sys,json
args=sys.argv[1:];scenario=os.environ['SCENARIO']
with open(os.environ['FAKE_CALLS'],'a') as f:f.write(json.dumps(['argocd',*args])+'\\n')
if (scenario=='initial-password' and 'initial-password' in args) or (scenario=='login' and 'login' in args) or (scenario=='update-password' and 'update-password' in args):raise SystemExit(43)
''');argo.chmod(0o755)
 openssl=bin_dir/'openssl';openssl.write_text(header+'''import os
raise SystemExit(43 if os.environ['SCENARIO']=='certificate-verify' else 0)
''');openssl.chmod(0o755)
 # Bypass only bundle verification for downstream shell tests; its real byte checks
 # have a separate test_bundle.py. All other Python commands use this interpreter.
 python=bin_dir/'python3';python.write_text(header+'''import os,sys
if len(sys.argv)>1 and sys.argv[1].endswith('/prepare_bundle.py'):
 raise SystemExit(43 if os.environ['SCENARIO']=='bundle-verify' else 0)
os.execv(sys.executable,[sys.executable,*sys.argv[1:]])
''');python.chmod(0o755)
 kube=p/'kubeconfig';kube.write_text('')
 lab=p/'persistent';(lab/'bootstrap-initial').mkdir(parents=True)
 for n in ['project','application']:(lab/'bootstrap-initial'/f'{n}.yaml').write_text('not applied')
 env=dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ.get('PATH',''),FAKE_CALLS=str(log),LAB_ROOT=str(lab),LAB_KUBECONFIG=str(kube),LAB_CONTEXT='own-test-context',ARGOCD_BIN=str(argo),RESTORE_KUBECONFIG=str(kube),RESTORE_CONTEXT='restore-personal',RESTORE_EXPECTED_SERVER='https://restore.example.invalid:6443',RESTORE_EXPECTED_CLUSTER_UID='restore-uid')
 env.pop('SOURCE_CLUSTER_UID',None)
 def execute(script,scenario,code=43):
  if log.exists():log.unlink()
  q=subprocess.run(['bash',ROOT/'scripts'/script],env=dict(env,SCENARIO=scenario),text=True,capture_output=True)
  assert q.returncode==code,(script,scenario,q.returncode,q.stderr)
  calls=[json.loads(x) for x in log.read_text().splitlines()]
  assert 'succeeded' not in q.stdout and 'acceptance passed' not in q.stdout,(scenario,q.stdout)
  return calls
 scenarios=0
 for script in ['preflight.sh','install.sh','first-app.sh','first-login.sh']:
  calls=execute(script,'first');scenarios+=1
  assert len(calls)==1 and not any(x in ['apply','create','delete','patch'] for x in calls[0])
 for scenario in ['bundle-verify','namespace-create','install-dry-run','install-apply','crd-ready','deployment-ready','controller-ready']:
  calls=execute('install.sh',scenario);scenarios+=1
  if scenario=='bundle-verify':assert not any('get' in c and 'namespace' in c for c in calls)
  if scenario=='namespace-create':assert len([c for c in calls if 'create' in c and '-f' in c])==1 and not any('apply' in c for c in calls)
  if scenario=='install-dry-run':assert len([c for c in calls if 'apply' in c])==1
  if scenario=='install-apply':assert not any('wait' in c for c in calls)
  if scenario=='crd-ready':assert not any('--for=condition=Available' in c for c in calls)
  if scenario=='deployment-ready':assert not any('statefulset/argocd-application-controller' in c for c in calls)
 for scenario in ['project-dry-run','project-apply','app-dry-run','app-apply']:
  calls=execute('first-app.sh',scenario);scenarios+=1
  last=calls[-1];assert 'apply' in last
  assert last[-1].endswith('/'+('project' if scenario.startswith('project') else 'application')+'.yaml')
  assert ('--dry-run=server' in last)==scenario.endswith('dry-run')
 for scenario in ['certificate-fetch','certificate-empty','certificate-verify','initial-password','login','update-password']:
  calls=execute('first-login.sh',scenario,1 if scenario=='certificate-empty' else 43);scenarios+=1
  argo_calls=[c for c in calls if c[0]=='argocd']
  if scenario.startswith('certificate'):assert not argo_calls
  if scenario=='initial-password':assert len(argo_calls)==1 and 'initial-password' in argo_calls[-1]
  if scenario=='login':assert len(argo_calls)==2 and 'login' in argo_calls[-1]
  if scenario=='update-password':assert len(argo_calls)==3 and 'update-password' in argo_calls[-1]
 for scenario,code in [('first',43),('restore-endpoint',1),('restore-same-cluster',1),('restore-marker',1),('restore-notification-scale',43),('restore-appset-scale',43),('restore-app-scale',43),('restore-pods-read',1)]:
  calls=execute('quarantine-restore.sh',scenario,code);scenarios+=1
  if scenario in ['first','restore-endpoint','restore-same-cluster','restore-marker']:
   assert not any('scale' in c for c in calls)
  if scenario=='restore-notification-scale':assert len([c for c in calls if 'scale' in c])==1
  if scenario=='restore-appset-scale':assert len([c for c in calls if 'scale' in c])==2
  assert not any('import' in c for c in calls)
 for script in (ROOT/'scripts').glob('*.sh'):
  assert subprocess.run(['bash','-n',script],capture_output=True).returncode==0
 print(f'PASS:{scenarios} explicit fake-client failure paths + Bash syntax. No real API/TLS/cluster acceptance.')
