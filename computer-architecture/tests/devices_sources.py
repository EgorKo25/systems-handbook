#!/usr/bin/env python3
"""Read-only checks for the DEVICES-owned source package; no renderer or hardware."""
import ast
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
NUMBERS = [19, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
checks = 0

def require(condition, message):
    global checks
    if not condition:
        raise AssertionError(message)
    checks += 1

def load(name):
    p = ROOT / 'sources' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('src', 'href'):
                self.links.append((k, v))

chapters = sorted(p for p in (ROOT/'sources').glob('ca-*.html') if int(p.stem[3:5]) in NUMBERS)
require(len(chapters) == 12, 'Twelve owned chapters')
texts = {p.stem: p.read_text() for p in chapters}
for p in chapters:
    s = p.read_text()
    require(s.startswith('<header><h1>') and '</p></header>' in s, p.name + ': header')
    require(not re.search(r'/home/(eko|documents)|file://|TODO|FIXME', s), p.name + ': private path/placeholder')
    links = Links(); links.feed(s)
    for kind, url in links.links:
        if re.match('https?://', url):
            require(kind != 'src', p.name + ': active network script')
        elif not url.startswith('#'):
            require((ROOT/url.split('#',1)[0]).exists(), p.name + ': local link ' + url)
ref = load('reference_devices')
require(ref.COMMANDS == [], 'Hardware book does not require host command cards')
require(len(ref.GLOSSARY) >= 40, 'Substantive device glossary')
require(len({x[0].casefold() for x in ref.GLOSSARY}) == len(ref.GLOSSARY), 'Unique owned terms')
for term in ref.GLOSSARY:
    require(len(term) == 2 and all(isinstance(x,str) and x.strip() for x in term), 'Glossary schema')
ds = load('diagrams_devices').DIAGRAMS
require(len(ds) == 12, 'One selected mechanism per owned chapter')
require({d['chapter'] for d in ds} == set(texts), 'Chapter diagram coverage')
for d in ds:
    require(d['volume'] == 'computer-architecture' and d['id'].startswith('ca-devices-'), 'Diagram namespace')
    require(texts[d['chapter']].count(d['insert_before']) == 1, d['id'] + ': placement')
    nodes = {n['id'] for n in d['nodes']}; edges = {e['id'] for e in d['edges']}
    require(len(nodes) == len(d['nodes']) and len(edges) == len(d['edges']), d['id'] + ': unique nodes/edges')
    for e in d['edges']:
        require(e['from'] in nodes and e['to'] in nodes, d['id'] + ': edge endpoint')
    for step in d['steps']:
        require(set(step['states']) == nodes and all(step['states'].values()), d['id'] + ': full states')
        require(set(step['focus']) <= nodes and set(step['active']) <= edges, d['id'] + ': highlights')
        require(bool(step['fields']) and bool(step['bands']), d['id'] + ': fields/bands')
# Check literal source bytes as well as the independent JS encoders.
nvme = next(v for k,v in texts.items() if k.startswith('ca-28-'))
blocks = re.findall(r'<pre><code>(.*?)</code></pre>', nvme, re.S)
sqe = bytes.fromhex(' '.join(' '.join(line.split()[1:]) for line in blocks[0].strip().splitlines()[1:]))
expected = bytearray(64)
for offset,value in [(0,2),(2,17),(4,1),(0x19,0x20),(0x28,7)]:
    expected[offset] = value
require(sqe == expected, 'NVMe literal READ64B offsets/values')
require(bytes.fromhex(blocks[1].splitlines()[0].split(':',1)[1]) == bytes.fromhex('00 00 00 00 00 00 00 00 01 00 02 00 11 00 01 00'), 'NVMe literal CQE16B')
pcie = next(v for k,v in texts.items() if k.startswith('ca-25-'))
require('00 00 00 80 |01 00 5A FF |00 00 20 00' in pcie, 'PCIe literal MRd32')
require('4A 00 00 10 |00 00 02 00 |01 00 5A 00' in pcie, 'PCIe literal CplD')
nic = next(v for k,v in texts.items() if k.startswith('ca-26-'))
require('00 82 00 00  00 60 00 00  00 00 00 00  00 00 00 00' in nic, 'LAN743x literal owned descriptor')
for file in ['model.html', 'boundaries.html']:
    s = (ROOT/'labs/devices'/file).read_text(); links = Links(); links.feed(s)
    require('id="model-theme"' in s and '../m32/appearance.js' in s, file + ': shared preferences')
    require('type="module"' not in s and 'fetch(' not in s, file + ': classic offline')
    for _, url in links.links:
        require(not re.match('https?://', url), file + ': external active dependency')
        if url.startswith('../../index.html#'):
            require(url.split('#',1)[1] in texts, file + ': generated reader anchor')
        else:
            require((ROOT/'labs/devices'/url.split('#')[0]).exists(), file + ': local dependency ' + url)
require((ROOT/'labs/devices/README.txt').is_file() and (ROOT/'SOURCES-devices.txt').is_file(), 'Reader documents')
print(json.dumps({'passed': True, 'kind': 'read-only source checks, no native hardware', 'checks': checks,
                  'chapters': len(chapters), 'terms': len(ref.GLOSSARY), 'diagrams': len(ds),
                  'steps': sum(len(d['steps']) for d in ds)}, ensure_ascii=False))
