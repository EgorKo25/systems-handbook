#!/usr/bin/env python3
"""Source-only checks; not a render, CLI install or database acceptance."""
from pathlib import Path
import ast
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
import zlib

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


cfg=load('flyway_config',ROOT/'volume_config.py').CONFIG
ref=load('flyway_reference',ROOT/'sources/reference.py')
diagrams=load('flyway_diagrams',ROOT/'sources/diagrams.py').DIAGRAMS
order=[identifier for _,ids in cfg['sections'] for identifier in ids]
assert len(order)==len(set(order))
assert all(identifier in ('00-route','99-glossary') or identifier.startswith('flyway-') for identifier in order)
words=0;blocks=0
for identifier in order:
    if identifier=='99-glossary':continue
    file=ROOT/'sources'/(identifier+'.html');text=file.read_text()
    assert text.count('<h1>')==text.count('</h1>')==1,file
    assert re.search(r'<header>.*?<p>.*?</p>.*?</header>',text,re.S),file
    assert '<script' not in text and '<iframe' not in text and '@import' not in text,file
    assert not re.search(r'\b(?:fetch\(|src="https?://)',text),file
    assert text.count('<pre>')==text.count('</pre>'),file
    for href in re.findall(r'href="([^"]+)"',text):
        if href.startswith(('https://','http://','#','../')):continue
        assert (ROOT/href).exists(),(file,href)
    words+=len(re.findall(r'\S+',re.sub('<[^>]+>',' ',text)));blocks+=text.count('<pre>')
for d in diagrams:
    text=(ROOT/'sources'/(d['chapter']+'.html')).read_text()
    assert text.count(d['insert_before'])==1,d['id']
    nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
    assert d['id'].startswith('flyway-') and len(d['steps'])>=5
    for step in d['steps']:
        assert set(step['states'])==nodes
        assert set(step['focus'])<=nodes and set(step['active'])<=edges
        assert step['actor'] and step['fields']
for c in ref.COMMANDS:
    assert c['name'].startswith('flyway') and c['chapter'] in order
    for f in c['flags']:
        assert all(f.get(k) for k in ['flag','action','when','example','result'])
for file in ROOT.rglob('*'):
    if not file.is_file():continue
    assert file.suffix not in ('.jar','.pem','.key','.dump','.tar','.gz','.class'),file
    assert '.private' not in file.parts and 'PG_VERSION'!=file.name,file
    if file.suffix=='.py':ast.parse(file.read_text(),filename=str(file))
# Inline subject SVGs and standalone offline assets must stay identical.
for stem,chapter in [('flyway-history-rows','flyway-07-history'),('flyway-backfill-rows','flyway-12-backfill-index')]:
    source=(ROOT/'assets'/(stem+'.svg')).read_text().strip()
    assert source in (ROOT/'sources'/(chapter+'.html')).read_text()
    tree=ET.fromstring(source);ns={'s':'http://www.w3.org/2000/svg'}
    assert tree.find('s:title',ns).text and tree.find('s:desc',ns).text
    ids=[e.attrib['id'] for e in tree.iter() if 'id' in e.attrib]
    assert len(ids)==len(set(ids)) and all(i.startswith('flyway-') for i in ids)
    assert 'http://' not in source.replace('http://www.w3.org/2000/svg','')
    assert 'href=' not in source and 'reader-paper' in source
for name,expected in [('V1__create_notes.sql',1528097600),('R__note_count.sql',-1073421979),('V2__expand_title.sql',-143682903)]:
    text=(ROOT/'labs/migrations'/name).read_text().lstrip('\ufeff')
    crc=zlib.crc32(''.join(text.splitlines()).encode('utf-8'))
    if crc>=2**31:crc-=2**32
    assert crc==expected,(name,crc)
assert (ROOT/'labs/.gitignore').is_file()
conf=(ROOT/'labs/flyway.conf').read_text()
for required in ['flyway.defaultSchema=flyway_meta','flyway.schemas=flyway_meta,app','flyway.cleanDisabled=true','flyway.postgresql.transactional.lock=false','flyway.createSchemas=false']:
    assert required in conf,required
assert (ROOT/'labs/migrations/V5__index_title.sql.conf').read_text().strip()=='executeInTransaction=false'
assert 'app_runtime' in (ROOT/'labs/migrations/V1__create_notes.sql').read_text()
print(json.dumps(dict(kind='static-source-only',chapters=len(order),words=words,executable_blocks=blocks,
                     commands=len(ref.COMMANDS),terms=len(ref.GLOSSARY),diagrams=len(diagrams),steps=sum(len(d['steps']) for d in diagrams),passed=True),ensure_ascii=False))
