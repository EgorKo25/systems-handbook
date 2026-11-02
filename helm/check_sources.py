#!/usr/bin/env python3
"""Read-only source contract check, independent of shared builders/catalogs."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import importlib.util,re,json
BASE=Path(__file__).resolve().parent

def module(path):
    spec=importlib.util.spec_from_file_location('helm_check_'+path.stem,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cfg=module(BASE/'volume_config.py').CONFIG
ref=module(BASE/'sources/reference.py')
diags=module(BASE/'sources/diagrams.py').DIAGRAMS
ids=[i for _,group in cfg['sections'] for i in group]
assert len(ids)==len(set(ids))
assert all(i in ('00-route','99-glossary') or '-helm-' in i for i in ids)
words=0
for identifier in ids:
    if identifier=='99-glossary':continue
    s=(BASE/'sources'/f'{identifier}.html').read_text()
    assert len(re.findall('<h1>',s))==1
    assert re.search(r'<header>.*?<p>.*?</p>.*?</header>',s,re.S)
    assert s.count('<h2>Первичные источники и версия</h2>')==1
    assert not re.search(r'/home/[^/\s]+/',s)
    assert '/tmp/helm-' not in s
    assert '<script src=' not in s and 'fonts.googleapis' not in s
    assert '\x00' not in s
    words+=len(re.findall(r'\S+',re.sub('<[^>]+>',' ',s)))
for command in ref.COMMANDS:
    assert command['volume']=='helm' and command['chapter'] in ids
    assert all(k in command for k in ['name','purpose','syntax','sources','source','flags','situations'])
    assert all(set(f)=={'flag','action','when','example','result'} for f in command['flags'])
assert len({c['name'] for c in ref.COMMANDS})==len(ref.COMMANDS)
assert len({term.casefold() for term,_ in ref.GLOSSARY})==len(ref.GLOSSARY)
assert len({d['id'] for d in diags})==len(diags)
for d in diags:
    assert d['volume']=='helm' and d['chapter'] in ids and len(d['steps'])>=5
    source=(BASE/'sources'/f"{d['chapter']}.html").read_text()
    assert source.count(d['insert_before'])==1
    nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
    assert all(e['from'] in nodes and e['to'] in nodes for e in d['edges'])
    for s in d['steps']:
        assert set(s['states'])==nodes
        assert set(s['focus'])<=nodes and set(s['active'])<=edges
        assert s['fields'] and s['bands']
# Only local artifact links are checked here; final cross-volume links need integration.
for p in (BASE/'sources').glob('*.html'):
    for target in re.findall(r'href="([^"#]+)',p.read_text()):
        if target.startswith(('https://','http://','../')):continue
        assert (BASE/target).is_file(),(p.name,target)
print(json.dumps(dict(status='PASS',content_chapters=len(ids)-1,rendered_chapters_with_glossary=len(ids),words_approx=words,terms=len(ref.GLOSSARY),commands=len(ref.COMMANDS),flags=sum(len(c['flags']) for c in ref.COMMANDS),diagrams=len(diags),steps=sum(len(d['steps']) for d in diags)),ensure_ascii=False))
