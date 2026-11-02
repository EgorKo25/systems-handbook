#!/usr/bin/env python3
"""Static source/schema QA only. Does not claim PromQL execution."""
import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def module(path):
    spec = importlib.util.spec_from_file_location('prom_qa_' + path.stem, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'a': self.links.append(d.get('href', ''))
        assert tag not in ('iframe', 'script'), ('unexpected active HTML', tag)
        for name in ('src', 'href'):
            assert not d.get(name, '').startswith(('//', 'http://cdn.', 'https://cdn.'))


def main():
    cfg = module(ROOT / 'volume_config.py').CONFIG
    ref = module(ROOT / 'sources/reference.py')
    diagrams = module(ROOT / 'sources/diagrams.py').DIAGRAMS
    ids = [i for _, group in cfg['sections'] for i in group]
    assert len(ids) == len(set(ids))
    assert all(i in ('00-route', '99-glossary') or i.startswith('prom-') for i in ids)
    words = 0
    for i in ids:
        if i == '99-glossary': continue
        p = ROOT / 'sources' / (i + '.html')
        text = p.read_text()
        assert len(re.findall(r'<h1>', text)) == 1, p
        assert re.match(r'\s*<header><h1>.+?</h1><p>.+?</p></header>', text, re.S), p
        assert '<h2>' in text or '<h2 ' in text, p
        assert 'TODO' not in text and 'TBD' not in text, p
        parser = Tags(); parser.feed(text)
        for link in parser.links:
            if link.startswith('#'):
                assert link[1:] in ids, (p, link)
        words += len(re.sub('<[^>]+>', ' ', text).split())
    terms = [t.casefold() for t, _ in ref.GLOSSARY]
    assert len(terms) == len(set(terms))
    names = [c['name'] for c in ref.COMMANDS]
    assert len(names) == len(set(names))
    for c in ref.COMMANDS:
        assert c['chapter'] in ids and c['volume'] == 'prometheus'
        assert all(c.get(k) is not None for k in ('name', 'purpose', 'syntax', 'source', 'sources', 'flags', 'aliases', 'situations'))
        for f in c['flags']:
            assert all(f[k] for k in ('flag', 'action', 'when', 'example', 'result'))
    for d in diagrams:
        assert d['chapter'] in ids and d['volume'] == 'prometheus'
        nodes = {n['id'] for n in d['nodes']}
        edges = {e['id'] for e in d['edges']}
        assert len(nodes) == len(d['nodes']) and len(edges) == len(d['edges'])
        for e in d['edges']: assert e['from'] in nodes and e['to'] in nodes
        for s in d['steps']:
            assert set(s['states']) == nodes
            assert set(s['focus']) <= nodes and set(s['active']) <= edges
            assert s['actor'] and s['fields']
            for f in s['fields']: assert all(f[k] for k in ('name', 'before', 'after', 'why'))
    print(f'STATIC PASS: {len(ids)} chapters, {words} source words, {len(terms)} terms, {len(names)} commands, {len(diagrams)} diagrams/{sum(len(d["steps"]) for d in diagrams)} steps')


if __name__ == '__main__': main()
