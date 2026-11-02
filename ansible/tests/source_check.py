#!/usr/bin/env python3
"""Read-only validation for this volume's maintained sources."""
from pathlib import Path
from html.parser import HTMLParser
import html
import importlib.util
import re
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location('ansible_source_' + path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.ids = []; self.commands = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'href' in attrs: self.links.append(attrs['href'])
        if 'id' in attrs: self.ids.append(attrs['id'])
        if 'data-command-name' in attrs: self.commands.append(attrs['data-command-name'])
        if tag in ('script','iframe','link','img'):
            assert not attrs.get('src','').startswith(('https://','http://','//'))
            assert not (tag == 'link' and attrs.get('rel') == 'stylesheet')


cfg = module(ROOT/'volume_config.py').CONFIG
ref = module(ROOT/'sources/reference.py')
diagrams = module(ROOT/'sources/diagrams.py').DIAGRAMS
order = [identifier for _, ids in cfg['sections'] for identifier in ids]
assert len(order) == len(set(order))
assert all(i in ('00-route','99-glossary') or i.startswith('an-') for i in order)
assert len(ref.GLOSSARY) == len({t.casefold() for t,_ in ref.GLOSSARY})
assert len(ref.COMMANDS) == len({c['name'] for c in ref.COMMANDS})
commands = {c['name'] for c in ref.COMMANDS}
for command in ref.COMMANDS:
    assert command['chapter'] in order and command['volume'] == 'ansible'
    assert command['purpose'] and command['syntax'] and command['sources']
    assert len(command['flags']) == len({f['flag'] for f in command['flags']})
    for flag in command['flags']:
        assert all(flag.get(key) for key in ('flag','action','when','example','result'))

parsers = {}; sources = {}; words = 0
for chapter in order:
    if chapter == '99-glossary': continue
    source = (ROOT/'sources'/f'{chapter}.html').read_text()
    assert len(re.findall(r'<h1>',source)) == 1
    assert re.match(r'\s*<header>.*?</header>',source,re.S)
    assert '<header><h1>' in source and '</h1><p>' in source
    assert not re.search(r'/home/(?!documents/systems-handbook)|/Users/|[A-Za-z]:\\Users\\',source)
    parser = Links(); parser.feed(source)
    assert len(parser.ids) == len(set(parser.ids))
    assert all(name in commands for name in parser.commands)
    parsers[chapter]=parser; sources[chapter]=source
    words += len(html.unescape(re.sub('<[^>]+>',' ',source)).split())
anchors=set(order)|{i for p in parsers.values() for i in p.ids}
for chapter,parser in parsers.items():
    for link in parser.links:
        if link.startswith(('https://','http://','mailto:')): continue
        file, _, anchor = link.partition('#')
        if not file: assert anchor in anchors,(chapter,link)
        else: assert (ROOT/file).exists(),(chapter,link)
assert len(diagrams) == len({d['id'] for d in diagrams})
for d in diagrams:
    assert d['chapter'] in order and d['volume']=='ansible'
    assert d['assumptions'] and d['intro']
    if d.get('insert_before'): assert sources[d['chapter']].count(d['insert_before'])==1
    nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
    assert len(nodes)==len(d['nodes']) and len(edges)==len(d['edges'])
    for edge in d['edges']: assert edge['from'] in nodes and edge['to'] in nodes
    for step in d['steps']:
        assert step['actor'] and step['explanation'] and step['fields']
        assert set(step['states'])==nodes
        assert set(step['focus'])<=nodes and set(step['active'])<=edges
        for field in step['fields']: assert all(field[k] for k in ('name','before','after','why'))
for path in ROOT.rglob('*.py'): compile(path.read_text(),str(path),'exec')
try:
    import yaml
except ImportError:
    print('SKIP YAML parser (use prepared runtime for this additional static check)')
else:
    paths=list((ROOT/'labs').rglob('*.yml'))
    for path in paths: yaml.safe_load(path.read_text())
    print('PASS YAML parse:',len(paths),'source files; no tasks executed')
print('PASS metadata, headers, source links/anchors, command cards, diagrams, Python syntax')
print('COUNTS',len(order),'reader chapters including glossary;',len(sources),'HTML sources;',words,'source words;',len(ref.GLOSSARY),'terms;',len(ref.COMMANDS),'commands;',sum(len(c['flags']) for c in ref.COMMANDS),'flags;',len(diagrams),'diagrams;',sum(len(d['steps']) for d in diagrams),'steps')
