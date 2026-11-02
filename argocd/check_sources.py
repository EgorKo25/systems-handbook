#!/usr/bin/env python3
"""Own-volume static review only. Does not invoke shared builders or services."""
from pathlib import Path
from html.parser import HTMLParser
import importlib.util,json,re
ROOT=Path(__file__).resolve().parent

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
config=load('argocd_config',ROOT/'volume_config.py').CONFIG
reference=load('argocd_reference',ROOT/'sources/reference.py')
diagrams=load('argocd_diagrams',ROOT/'sources/diagrams.py').DIAGRAMS
ids=[i for _,group in config['sections'] for i in group]
assert len(ids)==len(set(ids))
assert all(i in ['00-route','99-glossary'] or i.startswith('argocd-') for i in ids)
class Scan(HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[];self.stack=[];self.words=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.hrefs += [v for k,v in attrs if k=='href']
 def handle_data(self,data):self.words.append(data)
word_count=0;local_links=0;inline_svg_count=0
for i in ids:
 if i=='99-glossary':continue
 path=ROOT/'sources'/f'{i}.html';s=path.read_text();assert '<h1>' in s and re.search(r'<h2(?: id="[^"]+")?>Источники и версия</h2>',s),i
 inline_svg_count+=len(re.findall(r'<svg\b',s))
 scan=Scan();scan.feed(s);word_count+=len(' '.join(scan.words).split())
 for href in scan.hrefs:
  if href.startswith(('https://','http://','#','../')):continue
  target=ROOT/href.split('#')[0];assert target.exists(),(i,href);local_links+=1
for c in reference.COMMANDS:
 assert c['chapter'] in ids and c['volume']=='argocd' and c['name'].startswith('argocd')
 chapter=(ROOT/'sources'/f"{c['chapter']}.html").read_text()
 assert f"<code>{c['name']}</code>" in chapter,c['name']
 for f in c.get('flags',[]):
  assert all(f.get(k) for k in ['flag','action','when','example','result']),(c['name'],f)
assert len({x[0] for x in reference.GLOSSARY})==len(reference.GLOSSARY)
for d in diagrams:
 assert d['id'].startswith('argocd-') and d['chapter'] in ids
 assert d['insert_before'] in (ROOT/'sources'/f"{d['chapter']}.html").read_text()
 nodes={x['id'] for x in d['nodes']};edges={x['id'] for x in d['edges']}
 for edge in d['edges']:assert edge['from'] in nodes and edge['to'] in nodes
 for step in d['steps']:
  assert set(step['states'])==nodes and set(step['focus'])<=nodes and set(step['active'])<=edges
  assert all(k in step['fields'][0] for k in ['name','before','after','why'])
for f in ROOT.rglob('*'):
 # The generated shared reader contains intentional home-directory sandbox
 # fixtures from the common runtime. This check scans authored inputs.
 if f == ROOT/'index.html':continue
 if not f.is_file() or '__pycache__' in f.parts:continue
 raw=f.read_bytes();assert not raw.startswith(b'\x7fELF'),f
 if f.suffix in ['.py','.html','.txt','.json','.yaml','.sh','.csv']:
  s=raw.decode();assert not re.search(re.escape('/'+'home'+'/')+r'[A-Za-z0-9_.-]+/',s),(f,'private home path')
  assert ('-----BEGIN '+'PRIVATE KEY-----') not in s and ('-----BEGIN '+'OPENSSH PRIVATE KEY-----') not in s,f
for f in ['README.txt','results.json','bundle-lock.json','test_guards.py','test_bundle.py']:
 assert (ROOT/'labs'/f).exists()
assert config['volume']=='XXV'
print(json.dumps({'status':'PASS','source_chapters':len(ids)-1,'html_words':word_count,'commands':len(reference.COMMANDS),'flag_cards':sum(len(c['flags']) for c in reference.COMMANDS),'glossary':len(reference.GLOSSARY),'diagrams':len(diagrams)+inline_svg_count,'legacy_diagrams':len(diagrams),'inline_svg_figures':inline_svg_count,'steps':sum(len(d['steps']) for d in diagrams),'local_links':local_links,'limits':'static source checks, no browser/shared build/server acceptance'},ensure_ascii=False,indent=2))
