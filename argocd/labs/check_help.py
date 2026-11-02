#!/usr/bin/env python3
"""Check declared card flag spellings against actual pinned native help.
Not a command-line parser and not a replacement for the production reader audit.
Raw help (which contains private default paths) is never saved publicly.
"""
from pathlib import Path
import importlib.util,json,os,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
binary=os.environ.get('ARGOCD_BIN');assert binary and Path(binary).is_file(),'Set verified ARGOCD_BIN'
spec=importlib.util.spec_from_file_location('argocd_card_reference',ROOT/'sources/reference.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
with tempfile.TemporaryDirectory(prefix='argocd-help-check-') as tmp:
 p=Path(tmp);(p/'empty-kubeconfig').write_text('')
 env=dict(os.environ,HOME=tmp,KUBECONFIG=str(p/'empty-kubeconfig'))
 env.pop('ARGOCD_SERVER',None);env.pop('ARGOCD_AUTH_TOKEN',None)
 def run(words):
  q=subprocess.run([binary,'--config',str(p/'absent-client'),*words],env=env,text=True,capture_output=True,timeout=10)
  assert q.returncode==0,(words,q.returncode,q.stderr[:200]);return q.stdout
 version=run(['version','--client','--short']).strip();assert version=='argocd: v3.5.6+c2b1e30'
 forms=aliases=0
 for c in ref.COMMANDS:
  text=run([*c['name'].split()[1:],'--help'])
  for f in c['flags']:
   # Card labels use literal alias separator " / "; these are not shell input.
   for part in f['flag'].split(' / '):
    form=part.split()[0];assert form.startswith('-')
    assert re.search(r'(?<!\S)'+re.escape(form)+r'(?:[\s,=]|$)',text),(c['name'],form)
    forms+=1
  for alias in c.get('aliases',[]):
   run([*alias.split()[1:],'--help']);aliases+=1
 report={'date':'2026-11-01','version':version,'commands':len(ref.COMMANDS),'flag_forms':forms,'aliases':aliases,'status':'PASS','scope':'declared spellings in native help only; no operation/API; production reader grammar is a separate coordinator audit'}
 (ROOT/'labs/help-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False,indent=2))
