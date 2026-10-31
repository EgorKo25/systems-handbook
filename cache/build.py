"""Build the offline cache volume and shared dictionary. No external packages.

Source of truth: sources/*.html, glossary.tsv, diagrams.py, commands.py.
Reader shell is a frozen copy of the existing Bash reader with content removed.
"""
from pathlib import Path
from html import escape, unescape
from html.parser import HTMLParser
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / 'sources'))
from diagrams import DIAGRAMS
from commands import COMMANDS, EXTRA_FLAGS
from course import SECTIONS, RENAME
from artwork import ART, figure, write_assets
from replication import render_replication

# The earlier generic failure sketch is replaced by the explicit sequence model.
DIAGRAMS = [d for d in DIAGRAMS if d['id'] != 'cache-failover']

TITLE = 'Кэш и базы данных в памяти: от ускорения чтения до Redis и Memcached'


def dump(value):
    return json.dumps(value, ensure_ascii=False).replace('</', '<\\/')


def put_json(page, identifier, data):
    pattern = r'(<script[^>]*id="' + identifier + r'"[^>]*>).*?(</script>)'
    result, count = re.subn(pattern, lambda m: m[1] + dump(data) + m[2], page, flags=re.S)
    assert count == 1, identifier
    return result


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if tag in ('h1','h2','h3','h4','p','li','pre','tr','dt','dd'): self.parts.append('\n\n')
        if tag in ('td','th'): self.parts.append(' | ')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def plain(value):
    parser = Text(); parser.feed(value)
    return re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', ''.join(parser.parts)).strip()


def sketch(d):
    esc = escape
    transcript = []
    labels = {n['id']: n['label'] for n in d['nodes']}
    for i,s in enumerate(d['steps'],1):
        fields = ''.join('<li><strong>'+esc(f['name'])+':</strong> '+esc(f['before'])+' → '+esc(f['after'])+'. '+esc(f['why'])+'</li>' for f in s['fields'])
        states = '; '.join(labels[k]+': '+v for k,v in s['states'].items())
        transcript.append(f'<div class="ds-transcript-step"><h4>{i}. {esc(s["title"])}</h4><p>{esc(s["explanation"])}</p><p>Действует: {esc(s["actor"])}.</p><p>{esc(states)}</p><ul>{fields}</ul></div>')
    return f'''<section class="deep-sketch" id="{d['id']}" aria-labelledby="{d['id']}-title">
<div class="ds-eyebrow">Разобрать по шагам</div><h3 id="{d['id']}-title">{esc(d['title'])}</h3><p class="ds-intro">{esc(d['intro'])}</p>
<details class="ds-assumptions"><summary>Условия этого примера</summary><p>{esc(d['assumptions'])}</p></details>
<div class="ds-live"><div class="ds-navigation"><button type="button" data-ds-prev aria-label="Предыдущий шаг">←</button><div class="ds-stage" aria-live="polite"><span data-ds-count></span><strong data-ds-title></strong></div><button type="button" data-ds-next>Дальше →</button></div>
<div class="ds-steps" role="group" aria-label="Выбрать шаг"></div><svg class="ds-graph" role="img" aria-label="Участники и направление действия"></svg>
<div class="ds-flow" aria-live="polite"></div><p class="ds-explanation" data-ds-explanation></p><p class="ds-actor"><strong>Сейчас действует:</strong> <span data-ds-actor></span></p>
<div class="ds-band-heading">Выберите часть структуры — откроется её смысл</div><div class="ds-bands" role="group" aria-label="Состав данных и состояния"></div><div class="ds-band-detail" aria-live="polite"></div>
<div class="ds-field-heading">Что изменилось на этом шаге</div><div class="ds-fields"></div></div>
<details class="ds-transcript"><summary>Все шаги текстом · для чтения и печати</summary>{''.join(transcript)}</details>
<script type="application/json" class="ds-data">{dump(d)}</script></section>'''


def main():
    write_assets(HERE/'assets')
    glossary = [line.split('\t',1) for line in (HERE/'sources/glossary.tsv').read_text(encoding='utf-8').splitlines() if line.strip()]
    assert all(len(x)==2 for x in glossary)
    pages=[]
    for path in sorted((HERE/'sources').glob('[0-9][0-9]-*.html')):
        source=path.read_text(encoding='utf-8')
        for old,new in RENAME.items():
            source=source.replace('<h1>'+old+'</h1>','<h1>'+new+'</h1>').replace('<h2>'+old+'</h2>','<h2>'+new+'</h2>')
        title=unescape(re.search(r'<h1>(.*?)</h1>',source,re.S)[1])
        lead=re.search(r'<header>.*?<p>(.*?)</p>.*?</header>',source,re.S)[1]
        body=re.sub(r'^<header>.*?</header>\s*','',source,flags=re.S)
        body=re.sub(r'<div data-art="([^"]+)"></div>',lambda m:figure(m[1]),body)
        body=body.replace('<div data-replication-lab></div>',render_replication())
        for d in DIAGRAMS:
            body=body.replace(f'<div data-diagram="{d["id"]}"></div>',sketch(d))
        # Tables keep their columns readable while scrolling inside the article on phones.
        body=re.sub(r'(?<!<div class="table-wrap">)(<table\b.*?</table>)',r'<div class="table-wrap">\1</div>',body,flags=re.S)
        assert 'data-diagram=' not in body
        pages.append(dict(id=path.stem,title=title,lead=lead,body=body))
    terms=''.join(f'<dt id="glossary-term-{i}">{escape(term)}</dt><dd>{escape(definition)}</dd>' for i,(term,definition) in enumerate(glossary))
    pages.append(dict(id='99-glossary',title='Словарь терминов и англицизмов',lead='Смысл, границы и связь с механизмами',body='<p>Определения относятся к задачам этого тома. Словарь в боковой панели ищет также по другим томам.</p><dl class="glossary">'+terms+'</dl>'))
    by_id={p['id']:p for p in pages}
    ordered=[]
    for section,identifiers in SECTIONS:
        for local_number,identifier in enumerate(identifiers,1):
            page=by_id[identifier]
            page['part']=section
            page['number']=str(local_number) if section in ('Начало','Справочник') else section.split('.')[0]+'.'+str(local_number)
            ordered.append(page)
    assert len(ordered)==len(pages) and len({p['id'] for p in ordered})==len(pages)
    pages=ordered
    articles=[]; data=[]
    for index,p in enumerate(pages):
        toc=[]
        def heading(m):
            anchor=p['id']+'-section-'+str(len(toc)+1)
            toc.append((anchor,plain(m[1])))
            return f'<h2 id="{anchor}">{m[1]}</h2>'
        body=re.sub(r'<h2>(.*?)</h2>',heading,p['body'],flags=re.S)
        words=len(re.findall(r'\S+',plain(body)))
        data.append(dict(id=p['id'],title=p['title'],words=words,part=p['part'],number=p['number']))
        contents='<details class="local-toc"><summary>Содержание главы</summary><ol>'+''.join(f'<li><a href="#{a}">{escape(t)}</a></li>' for a,t in toc)+'</ol></details>' if toc else ''
        prev='#'+pages[index-1]['id'] if index else '../index.html'
        nxt='#'+pages[index+1]['id'] if index+1<len(pages) else '../index.html'
        articles.append(f'''<article class="chapter" id="{p['id']}"{' hidden' if index else ''}><header class="hero"><div class="eyebrow">Том V · {p['part']} · {p['number']}</div><h1>{escape(p['title'])}</h1><div class="meta">{p['lead']} · {words} слов</div></header>{contents}{body}
<footer class="chapter-footer"><button class="read-toggle" aria-pressed="false">Отметить прочитанной</button><div style="margin-top:20px"><label for="note-{p['id']}">Вопросы и заметки к главе</label><textarea class="note" id="note-{p['id']}" placeholder="Что хочется проверить или перечитать…"></textarea><div class="note-state">Заметки сохраняются в этом браузере. Выгрузите отдельную копию перед переносом.</div></div><div class="footer-nav"><a href="{prev}">← Назад</a><a href="{nxt}">Дальше →</a></div></footer></article>''')
    s=(HERE/'sources/reader-shell.html').read_text(encoding='utf-8')
    s=s.replace('data-volume="bash"','data-volume="cache"').replace('data-storage-key="bash-book-v1"','data-storage-key="cache-book-v1"')
    s=re.sub(r'<title>.*?</title>',lambda _: '<title>'+TITLE+'</title>',s,count=1)
    s=re.sub(r'<meta name="description"[^>]*>', '<meta name="description" content="Redis и Memcached: причины внедрения, расчёты нагрузки, свежесть, память, отказы, метрики и практика.">',s,count=1)
    s=s.replace('<div class="bookname">Bash</div>','<div class="bookname">Кэш и базы в памяти</div>')
    total=sum(c['words'] for c in data)
    s=re.sub(r'<div class="subtitle">.*?</div>',f'<div class="subtitle">Том V · Redis и Memcached<br>{total:,} слов · {len(pages)} глав<br>Редакция 31 октября 2026</div>',s,count=1,flags=re.S)
    nav='<nav class="chapter-nav">'
    for section,identifiers in SECTIONS:
        nav+='<div class="course-label">'+escape(section)+'</div>'
        for identifier in identifiers:
            p=by_id[identifier]
            nav+=f'<a id="nav-{p["id"]}" href="#{p["id"]}"><span class="chapter-num">{p["number"]}</span><span>{escape(p["title"])}</span></a>'
    nav+='</nav>'
    s=re.sub(r'<nav class="chapter-nav">.*?</nav>',lambda _:nav,s,count=1,flags=re.S)
    assert '<article class="chapter"' not in s.split('</main>')[0]
    s=s.replace('</noscript>','</noscript>'+''.join(articles),1)
    s=put_json(s,'book-data',data)
    s=put_json(s,'glossary-data',glossary)
    s=put_json(s,'flag-comparison-data',[])
    # Preserve the proven Bash and system command cards, adding only new names.
    commands=json.loads((ROOT/'bash/commands.json').read_text(encoding='utf-8'))
    additions={c['name']:c for c in COMMANDS}
    commands=[c for c in commands if c.get('volume')!='cache' and c['name'] not in additions]+COMMANDS
    for command in commands:
        command['flags'] += [dict(flag=f.strip(),action=a,when=w,example=e,result=r) for f,a,w,e,r in EXTRA_FLAGS.get(command['name'],[])]
    assert len({c['name'] for c in commands})==len(commands)
    s=put_json(s,'command-reference-data',commands)
    s=s.replace("postgres:'PostgreSQL'", "postgres:'PostgreSQL',cache:'Кэш и базы в памяти'")
    s=s.replace('Термины всех четырёх томов','Термины всех пяти томов')
    # Cache-server cards must never pretend to execute in the shell simulator.
    s=s.replace("'<div data-learning-terminal></div>'+", "(command.volume==='cache'?'<p class=\"callout\">Эта команда выполняется на реальном лабораторном сервере. Браузерная модель её не исполняет.</p>':'<div data-learning-terminal></div>')+")
    s=s.replace('</style></head>', '''.calc-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.calc-fields label{font:14px/1.5 var(--sans)}.calc-fields input{display:block;width:100%;min-width:0;margin-top:5px;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text)}.cache-calculator output{display:block;margin-top:20px;font:16px/1.7 var(--sans);white-space:normal}@media(max-width:600px){.calc-fields{grid-template-columns:1fr}}@media print{.cache-calculator{break-inside:avoid}}
</style></head>''',1)
    calculator=(HERE/'sources/calculator.js').read_text(encoding='utf-8')
    extras=''.join((HERE/'sources'/name).read_text(encoding='utf-8') for name in ['eviction.js','replication.js','resource-labs.js'])
    s=s.replace('</body>', '<script>'+calculator+'\n'+extras+'</script></body>')
    s=s.replace('</style></head>', '''.course-label{font:800 13px/1.5 var(--sans);color:var(--accent);padding:20px 8px 5px;border-top:1px solid var(--line)}.chapter-nav a{grid-template-columns:42px 1fr}.course-paths{display:grid;gap:16px}.course-paths a{display:grid;gap:8px;padding:22px;background:var(--paper);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:8px;text-decoration:none}.course-paths span{font:16px/1.6 var(--sans);color:var(--muted)}.book-figure{margin:30px 0;background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow:hidden}.figure-scroll,.sequence-scroll{overflow-x:auto;max-width:100%}.book-figure img{display:block;width:100%;min-width:650px;height:auto}.book-figure figcaption{font:14px/1.7 var(--sans);padding:16px 20px}.sequence-scroll svg{display:block;min-width:900px;width:100%;height:auto}.step-toolbar{display:flex;gap:12px;align-items:center;justify-content:space-between;margin:18px 0}.step-toolbar strong{font:16px/1.5 var(--sans)}.eviction-trainer label{display:inline-block;max-width:100%;font:14px/1.6 var(--sans);margin:8px}.eviction-trainer input,.eviction-trainer select,.replication-lab select{max-width:100%;padding:8px;background:var(--paper);color:var(--text);border:1px solid var(--line);border-radius:5px}.eviction-trainer [data-trace]{display:block;width:420px;max-width:100%}.cache-slot{display:inline-grid;min-width:100px;padding:12px;margin:5px;border:2px solid var(--accent);border-radius:8px}.cache-slot small{font:12px/1.5 var(--sans)}@media print{.book-figure img{min-width:0}.sequence-scroll svg{min-width:0}.sequence-scroll{display:none}.replication-lab details{display:block}}
</style></head>''',1)
    # Shared glossary is embedded, so file:// requires no fetch or server.
    library=[]
    for volume in ['networks','linux','bash','postgres']:
        existing=(ROOT/volume/'index.html').read_text(encoding='utf-8')
        local=json.loads(re.search(r'<script[^>]*id="glossary-data"[^>]*>(.*?)</script>',existing,re.S)[1])
        library.extend(dict(term=t,definition=d,volume=volume,anchor=f'glossary-term-{i}') for i,(t,d) in enumerate(local))
    library.extend(dict(term=t,definition=d,volume='cache',anchor=f'glossary-term-{i}') for i,(t,d) in enumerate(glossary))
    s=put_json(s,'library-glossary-data',library)
    s=s.replace('min-width:900px;width:100%;height:auto','min-width:740px;width:100%;height:auto;font-family:var(--sans)')
    s=s.replace('</style></head>', '''.resource-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.resource-fields label{font:14px/1.5 var(--sans)}.resource-fields input{display:block;width:100%;min-width:0;padding:9px;margin-top:5px;color:var(--text);background:var(--paper);border:1px solid var(--line);border-radius:5px}.resource-lab output{display:block;margin:20px 0;font:16px/1.7 var(--sans)}.resource-chart{overflow-x:auto}.resource-chart svg{width:100%;min-width:580px;font:17px var(--sans)}.slab-page{margin:12px 0;border:1px solid var(--line);padding:12px}.slab-page strong{font:700 14px var(--sans)}.slab-chunks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.slab-chunk{border:1px solid var(--line);min-height:48px;font:12px/1.7 var(--sans)}.slab-fill{display:flex;height:24px}.slab-chunk small{display:block;padding:5px}.slab-fill span{min-width:0}.resource-lab{overflow:hidden}@media(max-width:600px){.resource-fields{grid-template-columns:1fr}}@media print{.resource-fields{display:none}.resource-chart svg{min-width:0}.resource-lab{break-inside:auto}}
</style></head>''',1)
    (HERE/'index.html').write_text(s,encoding='utf-8')
    for volume in ['networks','linux','bash','postgres']:
        path=ROOT/volume/'index.html'; original=path.read_text(encoding='utf-8')
        updated=put_json(original,'library-glossary-data',library)
        if "cache:'Кэш и базы в памяти'" not in updated:
            updated=updated.replace("postgres:'PostgreSQL'", "postgres:'PostgreSQL',cache:'Кэш и базы в памяти'")
        updated=updated.replace('Термины всех четырёх томов','Термины всех пяти томов')
        if updated!=original: path.write_text(updated,encoding='utf-8')
    (HERE/'Текст-тома.txt').write_text(TITLE+'\n\n'+ '\n\n'.join(plain(a.split('<footer')[0]) for a in articles),encoding='utf-8')
    (HERE/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (HERE/'Справочник-команд.txt').write_text('\n\n'.join(c['name']+'\n'+c['purpose']+'\n'+c['syntax']+'\n'+'\n'.join(f['flag']+' — '+f['action']+'\nКогда: '+f['when']+'\n'+f['example']+'\nРезультат: '+f['result'] for f in c['flags']) for c in commands),encoding='utf-8')
    (HERE/'book-stats.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stats=json.loads((ROOT/'library-stats.json').read_text(encoding='utf-8'))
    stats=[r for r in stats if r['slug']!='cache']+[dict(slug='cache',title=TITLE,volume='V',words=total,chapters=len(pages),terms=len(glossary))]
    (ROOT/'library-stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    home=(ROOT/'index.html').read_text(encoding='utf-8')
    home=re.sub(r'<a class="volume" href="cache/index.html">.*?</a>','',home,flags=re.S)
    card=f'<a class="volume" href="cache/index.html"><div class="tag">Том V</div><h2>Кэш и базы в памяти</h2><p>Причины внедрения → расчёт пользы → свежесть и память → Redis и Memcached → измерения и отказы.</p><div class="counts">{len(pages)} глав · {total:,} слов · словарь: {len(glossary)}</div><span class="open">Открыть том →</span></a>'
    home=home.replace('</div><section class="notes">',card+'</div><section class="notes">',1)
    home=home.replace('Четыре связанных тома: как данные проходят сеть, как ядро предоставляет ресурсы, как оболочка управляет процессами и как база превращает запрос в устойчивое изменение.', 'Пять связанных томов: сеть, ядро Linux, Bash, PostgreSQL и кэширование. От устройства механизма до расчёта ресурсов, наблюдения и восстановления.')
    home=re.sub(r'<details data-cache-map>.*?</details>','',home,flags=re.S)
    links='<details data-cache-map><summary>Кэш · теория, Redis и Memcached</summary><ul>'+''.join(f'<li><a href="cache/index.html#{d["id"]}">{escape(d["title"])}</a> <span class="small">· {len(d["steps"])} шагов</span></li>' for d in DIAGRAMS)+'<li><a href="cache/index.html#cache-failover">Репликация: поток, подтверждения и отказ — 3 сценария</a></li><li><a href="cache/index.html#33-eviction">Тренажёр FIFO, LRU, LFU, CLOCK и OPT</a></li></ul></details>'
    home=home.replace('</section><section class="notes" style="margin-top:22px"><h2>Как читать',links+'</section><section class="notes" style="margin-top:22px"><h2>Как читать',1)
    home=home.replace('21 новых схем:','26 пошаговых схем:')
    (ROOT/'index.html').write_text(home,encoding='utf-8')
    print(json.dumps(dict(words=total,chapters=len(pages),terms=len(glossary),diagrams=len(DIAGRAMS),illustrations=len(ART),steps=sum(len(d['steps']) for d in DIAGRAMS)),ensure_ascii=False))


if __name__=='__main__':
    main()
