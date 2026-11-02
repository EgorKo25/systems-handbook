#!/usr/bin/env python3
"""Volume-only static contract audit; never builds the library or changes files."""
from pathlib import Path
import importlib.util,json,re,ast
from html.parser import HTMLParser
R=Path(__file__).resolve().parents[1]
def module(p):
 spec=importlib.util.spec_from_file_location(p.stem,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
config=module(R/'volume_config.py').CONFIG
ref=module(R/'sources/reference.py');diagrams=module(R/'sources/diagrams.py').DIAGRAMS
chapters=[x for _,items in config['sections'] for x in items]
assert len(set(chapters))==len(chapters)
assert all('k8s' in x for x in chapters if x not in ['00-route','99-glossary'])
class Content(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=[];self.head=[];self.text=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if 'id' in a:self.ids.append(a['id'])
  if t=='a':self.links.append(a.get('href',''))
  if t in ['h1','header']:self.head.append(t)
  assert t not in ['iframe','script'],('active source',t)
 def handle_data(self,s):self.text.append(s)
words=0
for ch in chapters:
 if ch=='99-glossary':continue
 p=R/'sources'/f'{ch}.html';s=p.read_text();h=Content();h.feed(s)
 assert h.head.count('h1')==1 and h.head.count('header')==1,ch
 words+=len(re.findall(r'\S+',' '.join(h.text)))
 assert len(h.ids)==len(set(h.ids)),ch
 for link in h.links:
  if link.startswith(('https://','http://','#','../')):continue
  target=link.split('#')[0]
  assert (R/target).is_file(),(ch,link)
 for d in diagrams:
  if d['chapter']==ch:assert s.count(d['insert_before'])==1,(ch,d['id'])
for c in ref.COMMANDS:
 assert c['chapter'] in chapters and c['volume']=='kubernetes'
 for situation in c['situations']:
  assert isinstance(situation,dict) and all(isinstance(situation.get(k),str) and situation[k].strip() for k in ['problem','explanation','solution']),('situation contract',c['name'])
 for f in c['flags']:assert all(f[k] for k in ['flag','action','when','example','result'])
assert len({c['name'] for c in ref.COMMANDS})==len(ref.COMMANDS)
for d in diagrams:
 assert d['chapter'] in chapters and d['volume']=='kubernetes'
 nodes={x['id'] for x in d['nodes']};edges={x['id'] for x in d['edges']}
 assert len(nodes)==len(d['nodes']) and len(edges)==len(d['edges'])
 for e in d['edges']:assert e['from'] in nodes and e['to'] in nodes
 for s in d['steps']:
  assert set(s['states'])==nodes and set(s['focus'])<=nodes and set(s['active'])<=edges
  assert s['actor'] and all(s['fields'][0][k] for k in ['name','before','after','why'])
for p in R.rglob('*.py'):ast.parse(p.read_text())
for p in R.rglob('*.json'):json.loads(p.read_text())
print(f'PASS: {len(chapters)-1} authored chapters, {words} body words, {len(ref.GLOSSARY)} terms, {len(ref.COMMANDS)} cards, {len(diagrams)} diagrams/{sum(len(d["steps"]) for d in diagrams)} steps; source links and IDs checked')
