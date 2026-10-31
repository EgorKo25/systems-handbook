"""Validate generated book, references, data and source/build agreement."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import json
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.links=[];self.active=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if tag=='a' and 'href' in d:self.links.append(d['href'])
        if tag in ['script','img','iframe','link']:
            value=d.get('src',d.get('href',''))
            if value.startswith(('http:','https:','//')):self.active.append(value)


def main():
    cache={}; failures=[]; links=0
    def parse(path):
        if path not in cache:
            obj=Page();obj.feed(path.read_text(encoding='utf-8'));cache[path]=obj
        return cache[path]
    path=ROOT/'cache/index.html';obj=parse(path)
    if len(obj.ids)!=len(set(obj.ids)):failures.append('duplicate IDs')
    if obj.active:failures.append('external active assets')
    for href in obj.links:
        split=urlsplit(href)
        if split.scheme or not href:continue
        target=(path.parent/unquote(split.path)).resolve() if split.path else path
        links+=1
        if not target.exists():failures.append('missing file: '+href)
        elif split.fragment and target.suffix=='.html' and unquote(split.fragment) not in parse(target).ids:
            failures.append('missing anchor: '+href)
    source=path.read_text(encoding='utf-8')
    blocks=re.findall(r'<script([^>]*)>(.*?)</script>',source,re.S)
    diagrams=[json.loads(body) for attrs,body in blocks if 'ds-data' in attrs]
    for d in diagrams:
        nodes={n['id'] for n in d['nodes']};edges={e['id'] for e in d['edges']}
        for edge in d['edges']:
            if edge['from'] not in nodes or edge['to'] not in nodes:failures.append('bad edge '+d['id'])
        for step in d['steps']:
            if set(step['states'])!=nodes or not set(step['focus'])<=nodes or not set(step['active'])<=edges:failures.append('bad state '+d['id'])
    text=(ROOT/'cache/Текст-тома.txt').read_text(encoding='utf-8')
    scenarios=json.loads(re.search(r'<script[^>]*id="replication-scenarios"[^>]*>(.*?)</script>',source,re.S)[1])
    if len(scenarios)!=3:failures.append('replication scenarios missing')
    for scenario in scenarios.values():
        for step in scenario['steps']:
            if step['detail'] not in text:failures.append('missing replication transcript')
    for asset in re.findall(r'<img[^>]*src="([^"]+)"',source):
        if not (path.parent/asset).is_file():failures.append('missing image '+asset)
    if 'data-artwork=' in source or 'data-replication-lab' in source:failures.append('unexpanded source marker')
    for d in diagrams:
        for step in d['steps']:
            if step['explanation'] not in text:failures.append('missing transcript '+d['id'])
    for volume in ['networks','linux','bash','postgres','cache']:
        s=(ROOT/volume/'index.html').read_text(encoding='utf-8')
        g=json.loads(re.search(r'<script[^>]*id="library-glossary-data"[^>]*>(.*?)</script>',s,re.S)[1])
        for term in [x for x in g if x['volume']=='cache']:
            if term['anchor'] not in obj.ids:failures.append('broken shared glossary')
    report=dict(status='PASS' if not failures else 'FAIL',book_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),links=links,anchors=len(obj.ids),
        diagrams=len(diagrams),steps=sum(len(d['steps']) for d in diagrams),replication_scenarios=len(scenarios),failures=failures,
        scope='Static local links, diagram state references, text transcripts, shared dictionary anchors; not server performance.')
    (ROOT/'checks/cache-static.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return bool(failures)


if __name__=='__main__':sys.exit(main())
