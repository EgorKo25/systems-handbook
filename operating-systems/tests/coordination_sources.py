"""Static source/diagram/asset contracts; never builds or touches a host service."""
from pathlib import Path
from html.parser import HTMLParser
import ast, json, re, runpy
ROOT=Path(__file__).resolve().parents[1]
IDS=['os-14-interleavings','os-15-atomics-locks','os-16-wait-wakeup','os-17-deadlocks','os-23-ipc','os-24-sockets','os-25-events-async-io','os-26-security-identities','os-27-isolation','os-28-hypervisors','os-32-resource-accounting','os-33-portability']
ROUTE={f'os-{i:02}-'+suffix for i,suffix in enumerate(['purpose','kernel-model','program-process-thread','address-spaces','syscalls-exceptions','process-lifecycle','context-switch','scheduling','multiprocessor-scheduling','page-tables-faults','allocation','working-set-reclaim','commit-swap-oom','interleavings','atomics-locks','wait-wakeup','deadlocks','open-files','filesystems','io-path','durability-recovery','storage-volumes','ipc','sockets','events-async-io','security-identities','isolation','hypervisors','boot-services-shutdown','cpu-observation','memory-io-observation','resource-accounting','portability','lifecycle-failures','end-to-end','source-map'],1)}
class Page(HTMLParser):
 def __init__(self):super().__init__();self.stack=[];self.ids=[];self.links=[]
 def handle_starttag(self,t,a):
  if t not in {'br','hr','img','input','meta','link','source','wbr'}:self.stack.append(t)
  d=dict(a)
  if 'id'in d:self.ids.append(d['id'])
  if 'href'in d:self.links.append(d['href'])
  if 'src'in d:self.links.append(d['src'])
 def handle_endtag(self,t):assert self.stack and self.stack.pop()==t,(t,self.stack)
pages={};words={}
for cid in IDS:
 text=(ROOT/'sources'/(cid+'.html')).read_text();p=Page();p.feed(text);assert not p.stack,cid
 assert text.count('<h1>')==1 and text.count('<h2>Проверяемая модель</h2>')==1,cid
 assert 'record.bin'not in text and not re.search(r'(?:VA|адрес)[ =]*0x1000(?:[^0-9A-Fa-f]|$)',text),cid
 assert not re.search(r'<(?:script|link)[^>]+(?:src|href)="https?://',text),cid
 for href in p.links:
  if href.startswith('#'):assert href[1:]in ROUTE,(cid,href)
  elif not href.startswith(('https:','http:','mailto:')):
   target=href.split('#',1)[0];assert (ROOT/target).resolve().is_file(),(cid,href)
 pages[cid]=text;words[cid]=len(re.findall(r'[\wА-Яа-яЁё]+',re.sub('<[^>]+>',' ',text)))
for name in ['reference_coordination.py','diagrams_coordination.py']:ast.parse((ROOT/'sources'/name).read_text())
ref=runpy.run_path(str(ROOT/'sources/reference_coordination.py'));assert ref['COMMANDS']==[];assert all(len(x)==2 and all(isinstance(v,str)and v for v in x)for x in ref['GLOSSARY']);assert len({x[0].casefold()for x in ref['GLOSSARY']})==len(ref['GLOSSARY'])
diagrams=runpy.run_path(str(ROOT/'sources/diagrams_coordination.py'))['DIAGRAMS'];assert len(diagrams)==13
for d in diagrams:
 assert d['chapter']in pages and d['volume']=='operating-systems';assert pages[d['chapter']].count(d['insert_before'])==1
 nodes={x['id']for x in d['nodes']};edges={x['id']for x in d['edges']};assert len(d['steps'])>=4
 for e in d['edges']:assert e['from']in nodes and e['to']in nodes
 for step in d['steps']:
  assert set(step['states'])==nodes and set(step['focus'])<=nodes and set(step['active'])<=edges
  assert step['actor']and step['explanation']and step['fields']
  for f in step['fields']:assert {'name','before','after','why'}<=set(f)
assert len({d['id']for d in diagrams})==13
lab=(ROOT/'labs/coordination/index.html').read_text();p=Page();p.feed(lab);assert not p.stack
for href in p.links:
 if href=='../../index.html#os-14-interleavings':continue # shared generated book, coordinator-owned
 if not href.startswith('#'):assert (ROOT/'labs/coordination'/href).resolve().is_file(),href
scenario_ids=set(re.findall(r'<option value="([^"]+)">',lab))
for cid,text in pages.items():
 for scenario in re.findall(r'labs/coordination/index.html#([\w-]+)',text):assert scenario in scenario_ids,(cid,'missing lab scenario',scenario)
assert '<meta name="viewport"'in lab and 'http://'not in lab and 'https://'not in lab
css=(ROOT/'labs/coordination/lab.css').read_text();assert 'prefers-reduced-motion'in css and 'min-height:44px'in css and '@media print'in css
js=(ROOT/'labs/coordination/lab.js').read_text();assert 'innerHTML'not in js and 'fetch('not in js and 'setInterval('not in js
print(json.dumps({'status':'PASS','scope':'owned source contracts, not full build or visual UI','chapters':len(IDS),'words':words,'total_words':sum(words.values()),'glossary':len(ref['GLOSSARY']),'diagrams':len(diagrams),'diagram_steps':sum(len(d['steps'])for d in diagrams),'source_rows':len(ref['SOURCES'])},ensure_ascii=False,indent=2))
