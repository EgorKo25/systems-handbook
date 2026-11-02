#!/usr/bin/env python3
"""Check this volume only; optional real shared-builder render in TemporaryDirectory."""
import argparse
import importlib.util
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
VOLUME = ROOT / 'nexus'


def module(path):
    spec = importlib.util.spec_from_file_location('nexus_check_' + path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Parse(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.stack = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise AssertionError(f'bad nesting {tag}, stack {self.stack[-5:]}')
        self.stack.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    cfg = module(VOLUME / 'volume_config.py').CONFIG
    ref = module(VOLUME / 'sources' / 'reference.py')
    diagrams = module(VOLUME / 'sources' / 'diagrams.py').DIAGRAMS
    order = [key for _, identifiers in cfg['sections'] for key in identifiers]
    assert len(order) == len(set(order))
    assert all(key in {'00-route','99-glossary'} or 'nexus' in key for key in order)
    ids = set(order)
    links = []
    words = 0
    for chapter in order:
        if chapter == '99-glossary':
            continue
        source = (VOLUME / 'sources' / (chapter + '.html')).read_text()
        parsed = Parse()
        parsed.feed(source)
        assert not parsed.stack, (chapter, parsed.stack)
        assert re.search(r'<header>.*?<h1>.+?</h1>.*?<p>.+?</p>.*?</header>', source, re.S)
        for identity in parsed.ids:
            assert identity not in ids, identity
            ids.add(identity)
        links.extend(parsed.links)
        words += len(re.findall(r'\S+', re.sub('<[^>]+>', ' ', source)))
        assert not re.search(r'/home/[^/\s]+/', source), chapter
    for item in diagrams:
        assert item['chapter'] in order
        assert item['id'] not in ids
        ids.add(item['id'])
        body = (VOLUME / 'sources' / (item['chapter'] + '.html')).read_text()
        assert body.count(item['insert_before']) == 1
        nodes = {n['id'] for n in item['nodes']}
        edges = {e['id'] for e in item['edges']}
        assert len(nodes) == len(item['nodes']) and len(edges) == len(item['edges'])
        assert all(e['from'] in nodes and e['to'] in nodes for e in item['edges'])
        for step in item['steps']:
            assert set(step['focus']) <= nodes
            assert set(step['active']) <= edges
            assert set(step['states']) == nodes
            assert all(all(key in field for key in ('name','before','after','why')) for field in step['fields'])
    for href in links:
        if href.startswith('#'):
            assert href[1:] in ids, href
        elif not re.match(r'https?://', href):
            path = href.split('#')[0]
            assert (VOLUME / path).exists(), href
    names = set()
    for card in ref.COMMANDS:
        assert card['name'] not in names
        names.add(card['name'])
        assert card['chapter'] in order and card['volume'] == 'nexus'
        for field in ('purpose','syntax','source','sources','flags','situations'):
            assert field in card
        for scenario in card['situations']:
            assert isinstance(scenario, dict), card['name']
            assert all(isinstance(scenario.get(key), str) and scenario[key].strip()
                       for key in ('problem', 'explanation', 'solution')), card['name']
        for flag in card['flags']:
            assert all(flag.get(key) for key in ('flag','action','when','example','result'))
    assert len({term.casefold() for term,_ in ref.GLOSSARY}) == len(ref.GLOSSARY)
    ledger = json.loads((VOLUME / 'sources' / 'source-ledger.json').read_text())
    assert all(s['checked_on'] in {'2026-11-01', '2026-11-02'} and s['url'].startswith('https://') for s in ledger)
    report = dict(scope='nexus source contracts; no server execution', chapters=len(order),
                  html_sources=len(order)-1, source_words_approx=words, glossary=len(ref.GLOSSARY),
                  commands=len(ref.COMMANDS), flags=sum(len(c['flags']) for c in ref.COMMANDS),
                  diagrams=len(diagrams), diagram_steps=sum(len(d['steps']) for d in diagrams),
                  primary_sources=len(ledger), source_checks='passed')
    if args.render:
        with tempfile.TemporaryDirectory(prefix='nexus-isolated-render-') as temporary:
            target = Path(temporary)
            shutil.copytree(VOLUME, target / 'nexus', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'cache', target / 'cache', ignore=shutil.ignore_patterns('index.html','assets','labs','__pycache__'))
            for relative in ('scripts/build_volume.py','scripts/reader_navigation.py','scripts/command_reference_parser.js','bash/commands.json',
                             'git/sources/git_reference.py','go/sources/go_deep_reference.py','go/sources/tool_flag_reference.py'):
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            (target / 'scripts' / 'volume_config.py').write_text(
                'from nexus.volume_config import CONFIG\n'
                'CONFIGS = {"nexus": CONFIG}\n'
                'TARGETS = {key:"nexus" for _,ids in CONFIG["sections"] for key in ids if key not in {"00-route","99-glossary"}}\n')
            (target / 'library-stats.json').write_text('[]\n')
            result = subprocess.run([sys.executable, '-B', '-c', 'from scripts.build_volume import build; build("nexus")'],
                                    cwd=target, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            page = (target / 'nexus' / 'index.html').read_text()
            assert page.count('class="deep-sketch"') == len(diagrams)
            assert 'nexus-book-v1' in page
            for identifier in ('book-data','glossary-data','command-reference-data'):
                match = re.search(r'<script[^>]*id="'+identifier+r'"[^>]*>(.*?)</script>', page, re.S)
                assert match
                json.loads(match[1])
            for diagram in diagrams:
                assert 'id="' + diagram['id'] + '"' in page
            report['isolated_shared_builder'] = json.loads(result.stdout.strip())
            report['rendered_bytes'] = len(page.encode())
            report['render_checks'] = 'passed; temporary output removed; shared repository not rendered'
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(encoded)
    print(encoded)


if __name__ == '__main__':
    main()
