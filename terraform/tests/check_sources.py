#!/usr/bin/env python3
"""Read-only contract checks for this volume; no library registration/build."""
from pathlib import Path
from html.parser import HTMLParser
from html import unescape
import ast
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parents[1]

def module(path):
    spec=importlib.util.spec_from_file_location('tf_'+path.stem,path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded

class Parser(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.errors=[];self.ids=[];self.refs=[];self.figures=[]
    def handle_starttag(self,tag,attrs):
        attributes=dict(attrs)
        if 'id' in attributes:self.ids.append(attributes['id'])
        for key in ('aria-labelledby','aria-describedby'):
            if key in attributes:self.refs+=attributes[key].split()
        if self.stack and self.stack[-1]=='figure':self.figures[-1].append(tag)
        if tag=='figure':self.figures.append([])
        if tag not in {'br','hr','img','input','meta','link','source','wbr'}:self.stack.append(tag)
    def handle_endtag(self,tag):
        if not self.stack or self.stack[-1]!=tag:self.errors.append((tag,self.stack[-3:]))
        else:self.stack.pop()

cfg=module(ROOT/'volume_config.py').CONFIG
ref=module(ROOT/'sources/reference.py')
diagrams=module(ROOT/'sources/diagrams.py').DIAGRAMS
ids=[i for _,group in cfg['sections'] for i in group]
assert len(ids)==len(set(ids))
assert all(i in {'00-route','99-glossary'} or i.startswith('tf-') for i in ids)
pages={}
for name in ids:
    if name=='99-glossary':continue
    source=(ROOT/'sources'/(name+'.html')).read_text()
    assert len(re.findall('<h1>',source))==1,name
    assert re.search(r'<header>.*?<h1>.+?</h1>.*?<p>.+?</p>.*?</header>',source,re.S),name
    parser=Parser();parser.feed(source)
    assert not parser.errors and not parser.stack,(name,parser.errors,parser.stack)
    assert len(parser.ids)==len(set(parser.ids)),name
    assert set(parser.refs)<=set(parser.ids),(name,parser.refs)
    assert all(children and (children[0]=='figcaption' or children[-1]=='figcaption')
               for children in parser.figures),(name,parser.figures)
    assert not re.search(r'<(?:script|link)\b[^>]*(?:src|href)="https?://',source),name
    assert not re.search(r'\b(?:TODO|TBD|FIXME)\b',source),name
    pages[name]=source
assert set(p.stem for p in (ROOT/'sources').glob('*.html'))==set(pages)
for name,source in pages.items():
    for target in re.findall(r'href="#([^"]+)"',source):assert target in ids,(name,target)
terms=[t.casefold() for t,_ in ref.GLOSSARY]
assert len(terms)==len(set(terms))
command_names=[]
for c in ref.COMMANDS:
    assert c['chapter'] in pages,c['name']
    assert c['volume']=='terraform'
    assert all(k in c for k in ['name','aliases','purpose','syntax','source','sources','flags','situations'])
    for f in c['flags']:assert set(f)=={'flag','action','when','example','result'}
    for situation in c['situations']:
        assert isinstance(situation,dict),(c['name'],'reader requires structured situation')
        assert all(isinstance(situation.get(k),str) and situation[k].strip()
                   for k in ('problem','explanation','solution')),c['name']
    command_names.append(c['name'])
assert len(command_names)==len(set(command_names))
all_ids=set()
for d in diagrams:
    assert d['chapter'] in pages and d['volume']=='terraform'
    assert pages[d['chapter']].count(d['insert_before'])==1,(d['id'],d['insert_before'])
    assert d['id'] not in all_ids;all_ids.add(d['id'])
    nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
    assert len(nodes)==len(d['nodes']) and len(edges)==len(d['edges'])
    assert all(e['from'] in nodes and e['to'] in nodes for e in d['edges'])
    for s in d['steps']:
        assert set(s['states'])==nodes,(d['id'],s['title'])
        assert set(s['focus'])<=nodes and set(s['active'])<=edges
        assert s['actor'] and s['fields'] and all(f['before'] and f['after'] and f['why'] for f in s['fields'])
    json.dumps(d,ensure_ascii=False)
for p in ROOT.rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
for p in ROOT.rglob('*'):
    if not p.is_file() or p.suffix not in {'.html','.py','.tf','.txt','.json'}:continue
    text=p.read_text()
    assert not re.search(r'/home/(?:eko|documents)/',text),str(p)
words=sum(len(re.findall(r'\S+',unescape(re.sub('<[^>]+>',' ',s)))) for s in pages.values())
print(json.dumps({'chapters_with_glossary':len(ids),'html_sources':len(pages),'words_in_sources':words,
                  'terms':len(ref.GLOSSARY),'commands':len(ref.COMMANDS),
                  'flags':sum(len(c['flags']) for c in ref.COMMANDS),'diagrams':len(diagrams),
                  'diagram_steps':sum(len(d['steps']) for d in diagrams),'result':'PASS'},ensure_ascii=False))
