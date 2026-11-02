#!/usr/bin/env python3
"""Read-only checks for the DEVICES-owned source package; no renderer or hardware."""
import ast
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
NUMBERS = [19, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
checks = 0
NVME_CHAPTER = "ca-28-nvme-queues-durability"

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
        self.ids = []
        self.images = []
        self.figures = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if tag == 'figure':
            self.figures.append(values)
        if tag == 'img':
            self.images.append((values, self.figures[-1] if self.figures else {}))
        for k, v in attrs:
            if k in ('src', 'href'):
                self.links.append((k, v))

    def handle_endtag(self, tag):
        if tag == 'figure' and self.figures:
            self.figures.pop()

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
require(len(ds) == 11, 'Eleven retained interactive device mechanisms')
require({d['chapter'] for d in ds} == set(texts) - {NVME_CHAPTER},
        'All other owned chapters retain their interactive diagrams')
require(len({d['id'] for d in ds}) == len(ds), 'Unique interactive diagram IDs')
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
nvme = texts[NVME_CHAPTER]
# NVMe now has three subject drawings instead of a generic deep-sketch. Check
# their actual SVG bytes and field labels, not a replacement graph-count alone.
artwork = {
    'labs/illustrations/nvme-sqe-read.svg': (
        (400, 625), 'nvme-record', [
            'SQ2 · SQ[0], 64 B', '00..03 CDW0 = 00110002h',
            '02 00 11 00 → Read / CID 0011h', '04..07 NSID = 1',
            '08..17 CDW2/3 = 0; MPTR = 0', '18..1F PRP1 = 2000h',
            '00 20 00 00 00 00 00 00', '20..27 PRP2 = 0',
            '28..2F SLBA = 7', '07 00 00 00 00 00 00 00',
            '30..33 CDW12 = 00000000h', 'NLB=0 → 1 блок × 512 B; FUA=0']),
    'labs/illustrations/nvme-cqe-phase.svg': (
        (400, 640), 'nvme-record', [
            'CQ2 · CQ[0], 16 B', '08..09 SQHD = 1', '0A..0B SQID = 2',
            '0C..0D CID = 0011h', '0E..0F Status/P = 0001h',
            '01 00 → P=1; SC=0; SCT=0', 'слоты: 0 → 1 → 2 → 3 → 0',
            'host ждёт: 1 1 1 1 0',
            'В старом CQ[0] P=1: ещё не новая CQE.',
            'Read не доказывает durability.']),
    'labs/illustrations/nvme-queue-memory.svg': (
        (400, 1390), 'nvme-memory', [
            'После CQE, до передачи CQ head', 'RAM host · DMA-адрес = PA',
            '2000..21FFh · 512 B', '2A 00 00 00 + 508 нулей',
            'host читает · 4×16=64 B', 'контроллер читает · 4×64 B',
            '5000 [0] CID 11h P=1', '6000 [0] Read CID 11h',
            'host: head=0; ждёт P=1', 'tail=1 задаёт host',
            'head=1 продвинул контроллер', 'SQHD=1: значение SQ head',
            'Ранее host: SQ2 tail 0 → 1', 'Затем host: CQ2 head 0 → 1',
            'Host пишет индексы, не payload.', 'Doorbell не завершает I/O.']),
}
links = Links(); links.feed(nvme)
require(links.ids.count('ca-devices-nvme') == 1, 'NVMe legacy bookmark occurs once')
require(len(links.images) == 3 and {v['src'] for v, _ in links.images} == set(artwork),
        'NVMe chapter covers all three subject SVGs exactly once')
SVG = '{http://www.w3.org/2000/svg}'
normalize = lambda value: ' '.join(value.split())
for image, figure in links.images:
    name = image['src']; dimensions, kind, expected_labels = artwork[name]
    require('nvme-artwork' in figure.get('class', '').split() and
            kind in figure.get('class', '').split(), name + ': subject figure placement')
    if kind == 'nvme-memory':
        require(figure.get('id') == 'ca-devices-nvme', name + ': legacy memory bookmark')
    require(bool(image.get('alt', '').strip()), name + ': accessible chapter explanation')
    require((image.get('width'), image.get('height')) == tuple(map(str, dimensions)),
            name + ': chapter dimensions match asset')
    asset = ROOT / name
    require(asset.is_file() and not asset.is_symlink(), name + ': regular local SVG')
    xml = ET.fromstring(asset.read_bytes())
    require(xml.tag == SVG + 'svg' and xml.get('viewBox') ==
            '0 0 ' + ' '.join(map(str, dimensions)), name + ': SVG viewport')
    ids = [node.get('id') for node in xml.iter() if node.get('id')]
    require(len(ids) == len(set(ids)), name + ': unique SVG IDs')
    require(xml.get('role') == 'img' and xml.get('aria-labelledby') and
            set(xml.get('aria-labelledby').split()) <= set(ids), name + ': labelled SVG')
    require(xml.find(SVG + 'title') is not None and xml.find(SVG + 'desc') is not None,
            name + ': title and text alternative')
    require(not any(node.tag == SVG + 'script' for node in xml.iter()) and
            all(not key.endswith('href') or value.startswith('#')
                for node in xml.iter() for key, value in node.attrib.items()),
            name + ': no executable or external SVG dependency')
    labels = {normalize(''.join(node.itertext())) for node in xml.iter(SVG + 'text')}
    for label in expected_labels:
        require(label in labels, name + ': field/read-path label ' + label)
require('IOMMU выключен и DMA-адрес совпадает с PA' in nvme,
        'NVMe picture states its DMA mapping assumption')
require('Нарисована Read; гарантии устойчивой Write и Flush разобраны ниже.' in nvme,
        'NVMe picture does not claim a durability experiment')
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
                  'chapters': len(chapters), 'terms': len(ref.GLOSSARY), 'diagrams': len(ds), 'subject_svg_chapters': 1, 'subject_svgs': len(artwork),
                  'steps': sum(len(d['steps']) for d in ds)}, ensure_ascii=False))
