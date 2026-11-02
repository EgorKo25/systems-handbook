#!/usr/bin/env python3
"""Grafana-only contract checks. No shared builder, mutation or network."""
from pathlib import Path
import importlib.util,ast,json,re
from html.parser import HTMLParser
import html,sys
import yaml
R=Path(__file__).resolve().parents[1]
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cfg=module(R/'volume_config.py','cfg').CONFIG;ref=module(R/'sources/reference.py','ref');ds=module(R/'sources/diagrams.py','ds').DIAGRAMS
chapters=[x for title,ids in cfg['sections'] for x in ids];assert len(chapters)==len(set(chapters))
assert all(x.startswith('grafana-') for x in chapters if x not in ['00-route','99-glossary'])
class Page(HTMLParser):
 def __init__(self):super().__init__();self.head=[];self.links=[];self.text=[]
 def handle_starttag(self,t,a):
  if t in ['h1','header']:self.head.append(t)
  if t=='a':self.links.append(dict(a).get('href',''))
  assert t not in ['script','iframe']
 def handle_data(self,s):self.text.append(s)
words=0
for ch in chapters:
 if ch=='99-glossary':continue
 path=R/'sources'/(ch+'.html');s=path.read_text();p=Page();p.feed(s);assert p.head.count('h1')==p.head.count('header')==1,ch;words+=len(re.findall(r'\S+',' '.join(p.text)))
 for u in p.links:
  if u.startswith(('https://','http://','#','../')):continue
  assert (R/u.split('#')[0]).is_file(),(ch,u)
 for d in ds:
  if d['chapter']==ch:assert s.count(d['insert_before'])==1,(ch,d['id'])
for c in ref.COMMANDS:
 assert c['chapter'] in chapters and c['volume']=='grafana' and c['name'].startswith(('grafana','python3 '))
 for f in c['flags']:assert all(f.get(x) for x in ['flag','action','when','example','result'])
assert len({x['name'] for x in ref.COMMANDS})==len(ref.COMMANDS)
assert len({x[0].casefold() for x in ref.GLOSSARY})==len(ref.GLOSSARY)
for d in ds:
 nodes={x['id'] for x in d['nodes']};edges={x['id'] for x in d['edges']};assert d['chapter'] in chapters
 for e in d['edges']:assert e['from'] in nodes and e['to'] in nodes
 for s in d['steps']:
  assert set(s['states'])==nodes and set(s['focus'])<=nodes and set(s['active'])<=edges
  assert s['actor'] and all(s['fields'][0].get(x) for x in ['name','before','after','why'])
for p in R.rglob('*.py'):ast.parse(p.read_text())
for p in R.rglob('*.json'):json.loads(p.read_text())
sources=json.loads((R/'labs/verified-sources.json').read_text())
assert sources and all(x.get('status')==200 and x.get('checked')=='2026-11-01' and x.get('sha256') for x in sources)
assert len({x['url'] for x in sources})==len(sources)
assert not (R/'sources/verified-sources.json').exists() # public journal must survive portable/Pages export

for p in (R/'labs').rglob('*.yaml'):list(yaml.safe_load_all(p.read_text()))
b=module(R/'labs/create_dashboard.py','dashboard').build();actual=json.loads((R/'labs/dashboards/go-service.json').read_text());assert b==actual
assert actual['uid']=='go-service-lab' and actual['timezone']=='utc' and len(actual['panels'])==6
assert len({x['id'] for x in actual['panels']})==6
for x in actual['panels']:
 assert x['datasource']['uid']=='prom-local'
 for q in x['targets']:assert q['datasource']['uid']=='prom-local' and ('job="go-lab"' in q['expr'])
assert actual['panels'][1]['fieldConfig']['defaults']['unit']=='percentunit' and '* 100' not in actual['panels'][1]['targets'][0]['expr']
rule=yaml.safe_load((R/'labs/provisioning/alerting/error-ratio-paused.yaml').read_text())['groups'][0]['rules'][0];assert rule['isPaused'] is True and rule['condition']=='C'
assert '$__' not in rule['data'][0]['model']['expr']
assert rule['keepFiringFor']=='30s'
assert yaml.safe_load((R/'labs/provisioning/alerting/error-ratio-paused.yaml').read_text())['groups'][0]['interval']=='20s'
assert 'settings' not in rule['data'][1]['model'] # strict is default; mode='strict' is rejected by native 13.3
sys.path.insert(0,str(R/'labs'))
from query_payload import payload
chapter=(R/'sources/grafana-05-query-path.html').read_text()
literal=re.search(r'<pre id="grafana-query-payload"><code>(.*?)</code></pre>',chapter,re.S).group(1)
assert json.loads(html.unescape(literal))==payload()
frame=re.search(r'<pre id="grafana-query-frame"><code>(.*?)</code></pre>',chapter,re.S).group(1)
trace=json.loads((R/'labs/verified-native.json').read_text())['query_traces']
assert json.loads(html.unescape(frame))==trace[0]['response']
for t in trace:
 f=t['response']['results']['A']['frames'][0]
 assert len(f['schema']['fields'])==len(f['data']['values'])==2
 assert len(f['data']['values'][0])==len(f['data']['values'][1])
 assert f['schema']['fields'][0]['type']=='time' and f['schema']['fields'][1]['type']=='number'
print(f'PASS: {len(chapters)-1} chapters/{words} words, {len(ref.GLOSSARY)} terms, {len(ref.COMMANDS)} cards, {len(ds)} diagrams/{sum(len(x["steps"]) for x in ds)} steps; sources, JSON, YAML, identities and units checked')
