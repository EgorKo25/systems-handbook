#!/usr/bin/env python3
"""Static source/schema/link checks; no claims about native server or rendered UI."""
import importlib.util,json,pathlib,re,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(path):
 s=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cfg=load(ROOT/'volume_config.py').CONFIG;r=load(ROOT/'sources/reference.py');d=load(ROOT/'sources/diagrams.py')
ids=[i for _,group in cfg['sections'] for i in group];assert len(ids)==len(set(ids))
assert all(i in ('00-route','99-glossary') or i.startswith('vault-') for i in ids)
words=0
for identifier in ids:
 if identifier=='99-glossary':continue
 path=ROOT/'sources'/f'{identifier}.html';s=path.read_text()
 assert re.search('<header>.*?<h1>.+?</h1>.*?<p>.+?</p>.*?</header>',s,re.S)
 assert '<script' not in s and 'fetch(' not in s
 words+=len(re.sub('<[^>]*>',' ',s).split())
 for href in re.findall('href="([^"]+)"',s):
  if re.match(r'https?://|#|\.\./',href):continue
  assert (ROOT/href.split('#')[0]).exists(),(path.name,href)
for diagram in d.DIAGRAMS:
 s=(ROOT/'sources'/f"{diagram['chapter']}.html").read_text();assert s.count(diagram['insert_before'])==1
 nodes={n['id'] for n in diagram['nodes']};edges={e['id'] for e in diagram['edges']}
 assert all(set(st['states'])==nodes and set(st['focus'])<=nodes and set(st['active'])<=edges for st in diagram['steps'])
assert len({c['name'] for c in r.COMMANDS})==len(r.COMMANDS)
assert all(c['chapter'] in ids and c['volume']=='vault' for c in r.COMMANDS)
assert not {'go','python3','curl'}&{c['name'] for c in r.COMMANDS}
for path in list(ROOT.rglob('*.py')):
 if '__pycache__' not in path.parts:compile(path.read_text(),str(path),'exec')
res=subprocess.run(['node',str(ROOT/'tests/reference_parser.js')],input=json.dumps(r.COMMANDS),text=True,capture_output=True,check=True)
print(res.stdout.strip())
print(json.dumps(dict(kind='static source check',chapters=len(ids)-1,words=words,commands=len(r.COMMANDS),terms=len(r.GLOSSARY),diagrams=len(d.DIAGRAMS)),ensure_ascii=False))
