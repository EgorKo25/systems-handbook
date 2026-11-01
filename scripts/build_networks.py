#!/usr/bin/env python3
"""Build the maintained network volume and update its shared catalogue counts."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import json
import re

if __package__:
    from .reader_navigation import normalize_reader_navigation
    from .publication import VOLUME_NUMBERS
else:
    from reader_navigation import normalize_reader_navigation
    from publication import VOLUME_NUMBERS

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'networks'
SRC = HERE / 'sources'


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'pre', 'tr', 'dt', 'dd'): self.parts.append('\n\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.skip -= 1
    def handle_data(self, text):
        if not self.skip: self.parts.append(text)


def plain(value):
    p = Text(); p.feed(value)
    result = re.sub(r'\n\s*\n(?:\s*\n)+', '\n\n', ''.join(p.parts)).strip()
    return '\n'.join(line.rstrip() for line in result.splitlines())


def write(path, text):
    old = path.read_bytes() if path.exists() else b''
    text = text.replace('\r\n', '\n')
    if old.decode().replace('\r\n', '\n') == text: return
    ending = '\r\n' if old and old.count(b'\r\n') == old.count(b'\n') else '\n'
    path.write_bytes(text.replace('\n', ending).encode())


def sketch(data):
    """Use the existing reader's accessible step renderer and print transcript."""
    esc = escape
    labels = {n['id']: n['label'] for n in data['nodes']}
    transcript = []
    for i, step in enumerate(data['steps'], 1):
        states = '; '.join(labels[k]+': '+v for k,v in step['states'].items())
        fields = ''.join('<li><strong>'+esc(f['name'])+':</strong> '+esc(f['before'])+' → '+esc(f['after'])+'. '+esc(f['why'])+'</li>' for f in step['fields'])
        transcript.append('<div class="ds-transcript-step"><h4>'+str(i)+'. '+esc(step['title'])+'</h4><p>'+esc(step['explanation'])+'</p><p>Действует: '+esc(step['actor'])+'.</p><p>'+esc(states)+'</p><ul>'+fields+'</ul></div>')
    encoded = json.dumps(data, ensure_ascii=False).replace('</','<\\/')
    return '<section class="deep-sketch" id="'+data['id']+'" aria-labelledby="'+data['id']+'-title"><div class="ds-eyebrow">Разобрать по шагам</div><h3 id="'+data['id']+'-title">'+esc(data['title'])+'</h3><p class="ds-intro">'+esc(data['intro'])+'</p><details class="ds-assumptions"><summary>Условия этого примера</summary><p>'+esc(data['assumptions'])+'</p></details><div class="ds-live"><div class="ds-navigation"><button type="button" data-ds-prev aria-label="Предыдущий шаг">←</button><div class="ds-stage" aria-live="polite"><span data-ds-count></span><strong data-ds-title></strong></div><button type="button" data-ds-next>Дальше →</button></div><div class="ds-steps" role="group" aria-label="Выбрать шаг"></div><svg class="ds-graph" role="img" aria-label="Участники и направление действия"></svg><div class="ds-flow" aria-live="polite"></div><p class="ds-explanation" data-ds-explanation></p><p class="ds-actor"><strong>Сейчас действует:</strong> <span data-ds-actor></span></p><div class="ds-band-heading">Выберите часть структуры — откроется её смысл</div><div class="ds-bands" role="group" aria-label="Состав данных и состояния"></div><div class="ds-band-detail" aria-live="polite"></div><div class="ds-field-heading">Что изменилось на этом шаге</div><div class="ds-fields"></div></div><details class="ds-transcript"><summary>Все шаги текстом · для чтения и печати</summary>'+''.join(transcript)+'</details><script type="application/json" class="ds-data">'+encoded+'</script></section>'


def main():
    order = json.loads((SRC / 'chapter-order.json').read_text())
    assert len(order) == len(set(order))
    base = {r['id']: r for r in json.loads((SRC / 'base-stats.json').read_text())}
    glossary = json.loads((SRC / 'base-glossary.json').read_text())
    extra = json.loads((SRC / 'depth-glossary.json').read_text())
    terms = {t.casefold() for t, _ in glossary}
    extra = [(t,d) for t,d in extra if t.casefold() not in terms]
    glossary += extra
    diagrams = json.loads((SRC / 'depth-diagrams.json').read_text())
    articles = []; stats = []; seen = set()
    for number, identifier in enumerate(order, 1):
        article = (SRC / (identifier + '.html')).read_text().strip()
        for diagram in diagrams:
            if diagram['chapter'] == identifier:
                marker = '<div data-depth-diagram="'+diagram['id'].removeprefix('net-')+'"></div>'
                assert article.count(marker) == 1, (identifier, marker)
                article = article.replace(marker, sketch(diagram), 1)
        title = plain(re.search(r'<h1>(.*?)</h1>', article, re.S)[1])
        if identifier == '12-glossary' and extra:
            definitions = ''.join('<dt id="glossary-term-'+str(i)+'">'+escape(t)+'</dt><dd>'+escape(d)+'</dd>' for i,(t,d) in enumerate(extra, len(glossary)-len(extra)))
            article = article.replace('<footer class="chapter-footer">','<h2 id="network-depth-terms">Физический канал, надёжность и радиоэфир</h2><dl class="glossary">'+definitions+'</dl><footer class="chapter-footer">',1)
        # Old chapter and heading IDs remain exactly the same: notes and external links survive.
        headings = re.findall(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', article, re.S)
        for anchor, _ in headings:
            assert anchor not in seen, anchor
            seen.add(anchor)
        toc = '<details class="local-toc"><summary>В этой главе: '+str(len(headings))+' разделов</summary><ol>'+''.join('<li><a href="#'+a+'">'+escape(plain(t))+'</a></li>' for a,t in headings)+'</ol></details>'
        article = re.sub(r'<details class="local-toc">.*?</details>', '', article, count=1, flags=re.S)
        article = article.replace('</header>', '</header>'+toc, 1)
        article = re.sub(r'<article[^>]+>', '<article id="'+identifier+'" class="chapter"'+(' hidden' if number>1 else '')+'>', article, count=1)
        article = re.sub(r'<div class="eyebrow">.*?</div>', '<div class="eyebrow">Том '+VOLUME_NUMBERS['networks']+' · Сети · Глава '+str(number).zfill(2)+'</div>', article, count=1)
        prev = '#'+order[number-2] if number>1 else '../index.html'
        nxt = '#'+order[number] if number<len(order) else '../index.html'
        footer = '<div class="footer-nav"><a href="'+prev+'">← Предыдущая глава</a><a href="'+nxt+'">Следующая глава →</a></div>'
        article = re.sub(r'<div class="footer-nav">.*?</div>', footer, article, count=1, flags=re.S)
        body = article.split('</header>',1)[1].split('<footer class="chapter-footer">',1)[0]
        body = re.sub(r'<details class="local-toc">.*?</details>', '', body, count=1, flags=re.S)
        words = base[identifier]['words'] if identifier in base and identifier != '12-glossary' else len(re.findall(r'\S+',plain(body)))
        stats.append(dict(id=identifier,title=title,words=words))
        articles.append(article)
    page = (SRC / 'reader-shell.html').read_text()
    page = page.replace('</head>', '<style id="network-theory-model-style">.network-theory-lab label{display:grid;gap:8px;font:600 16px/1.5 var(--sans)}.network-theory-lab input{font:400 16px/1.4 var(--mono);max-width:100%;width:16ch;box-sizing:border-box;min-height:44px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--paper);color:var(--text)}.network-theory-lab output{display:block;padding:14px;border:1px solid var(--line);border-radius:8px;overflow-wrap:anywhere;font:500 16px/1.6 var(--sans);color:var(--text);background:var(--paper)}.network-theory-lab output[data-error]{border-color:var(--accent)}</style></head>',1)
    nav = '<nav class="chapter-nav">'+''.join('<a id="nav-'+r['id']+'" href="#'+r['id']+'"><span class="chapter-num">'+str(i).zfill(2)+'</span><span>'+escape(r['title'])+'</span></a>' for i,r in enumerate(stats,1))+'</nav>'
    assert page.count('<!-- NETWORK_NAV -->') == page.count('<!-- NETWORK_CHAPTERS -->') == 1
    page = page.replace('<!-- NETWORK_NAV -->',nav).replace('<!-- NETWORK_CHAPTERS -->','\n'.join(articles))
    for identifier, data in [('book-data',stats),('glossary-data',glossary)]:
        encoded = json.dumps(data, ensure_ascii=False).replace('</','<\\/')
        page,n = re.subn(r'(<script[^>]*id="'+identifier+r'"[^>]*>).*?(</script>)', lambda m:m[1]+encoded+m[2],page,flags=re.S)
        assert n==1,identifier
    total = sum(r['words'] for r in stats)
    page = re.sub(r'<div class="subtitle">.*?</div>', '<div class="subtitle">Том '+VOLUME_NUMBERS['networks']+' · От сигнала до приложения<br>'+f'{total:,}'+' слов · '+str(len(stats))+' глав<br>Редакция 1 ноября 2026</div>',page,count=1,flags=re.S)
    page = page.replace('</body>', '<script src="labs/theory-models.js"></script></body>',1)
    write(HERE / 'index.html',normalize_reader_navigation(page))
    write(HERE / 'Учебник-сети.txt','СЕТИ: ОТ СИГНАЛА ДО ПРИЛОЖЕНИЯ\n\n'+'\n\n'.join(plain(a.split('<footer class="chapter-footer">')[0]) for a in articles)+'\n')
    result = dict(date='2026-11-01',words=total,chapters=stats,terms=len(glossary),external_assets=0,edition='physical-link-wireless-depth')
    write(HERE / 'book-stats.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    library = json.loads((ROOT / 'library-stats.json').read_text())
    for row in library:
        if row['slug'] == 'networks':
            row.update(title='Сети: от сигнала до приложения', volume=VOLUME_NUMBERS['networks'], words=total,
                       chapters=len(stats), terms=len(glossary))
    write(ROOT / 'library-stats.json',json.dumps(library,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('words','terms','edition')} | {'chapters':len(stats)},ensure_ascii=False))


if __name__ == '__main__': main()
