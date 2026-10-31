#!/usr/bin/env python3
"""Build volume VI from original HTML chapters and offline reference data.

Uses the established reader and step-diagram renderer of the cache volume.
No network requests, installations or external Python packages are needed.
"""
from pathlib import Path
from html import escape, unescape
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from cache.build import dump, put_json, plain, write_text, sketch
sys.path.insert(0, str(HERE / 'sources'))
from git_reference import GLOSSARY, COMMANDS
from git_state_diagrams import DIAGRAMS as STATE_DIAGRAMS
from git_diagrams import DIAGRAMS as BUILD_DIAGRAMS
sys.path.insert(0, str(ROOT / 'scripts'))
from library_catalog import refresh

TITLE = 'Git и воспроизводимая сборка: от байтов файла до проверенного выпуска'
DIAGRAMS = STATE_DIAGRAMS + BUILD_DIAGRAMS
SECTIONS = [
    ('Начало', ['00-route']),
    ('1. Устройство репозитория', ['01-repository-model', '02-objects', '03-index', '04-history']),
    ('2. Изменение истории', ['05-branches', '06-diffs', '07-merge', '08-rewrite', '09-recovery']),
    ('3. Совместная работа и хранение', ['10-remotes', '11-collaboration', '12-attributes', '13-storage-performance']),
    ('4. Получение результата', ['14-build-process', '15-dependencies', '16-reproducibility', '17-build-cache']),
    ('5. Автоматизация и измерение', ['18-jenkins-architecture', '19-jenkinsfile', '20-checks-artifacts', '21-measurement']),
    ('6. Практикум и выпуск', ['22-lab', '23-release']),
    ('Справочник', ['99-glossary']),
]


def reader_commands(page):
    # A subcommand is part of the name. Select the longest matching token prefix.
    marker = 'function parseOptions(tokens, specifications, settings = {}) {'
    helper = '''function commandPrefix(command, tokens) {
    return Math.max(0, ...[command.name, ...(command.aliases || [])].map(name => {
        const parts = tokenizeQuery(name);
        return parts.length && parts.every((part, i) => normalizeText(part) === normalizeText(tokens[i] || '')) ? parts.length : 0;
    }));
}
'''
    assert page.count(marker) == 1
    page = page.replace(marker, helper + marker)
    old = '''const explicit = !!tokens.length && matchesCommand(command, tokens[0]);
    if (explicit) tokens = tokens.slice(1);'''
    assert old in page
    page = page.replace(old, '''const prefix = commandPrefix(command, tokens);
    const explicit = prefix > 0;
    if (explicit) tokens = tokens.slice(prefix);''')
    old = '''const tokens = tokenizeQuery(query), first = tokens[0];
    const exact = first === undefined ? null : commands.find(command => matchesCommand(command, first));'''
    assert old in page
    page = page.replace(old, '''const tokens = tokenizeQuery(query);
    const candidates = commands.map(command => ({command, prefix: commandPrefix(command, tokens)})).filter(item => item.prefix);
    candidates.sort((a,b) => b.prefix-a.prefix);
    const exact = candidates[0]?.command || null;''')
    old = "'<div data-learning-terminal></div>'+"
    assert page.count(old) == 1
    page = page.replace(old, "(command.volume==='git'?'<p class=\"callout\">Выполните эту команду в <a href=\"#22-lab\" data-reference-chapter>настоящем учебном репозитории</a>. Состояние сохраняется между упражнениями.</p>':'<div data-learning-terminal></div>')+")
    old = '''<button type="button" data-try-example="'+flagIndex+'">В терминал ↑</button>'''
    assert old in page
    page = page.replace(old, """'+(command.volume==='git'?'':'<button type="button" data-try-example="'+flagIndex+'">В терминал ↑</button>')+'""")
    page = page.replace('commands.some(command => matchesCommand(command, token))',
                        'commands.some(command => commandPrefix(command, tokenizeQuery(input.value)))')
    page = page.replace('function mount(container,command){for(const details',
                        "function mount(container,command){if(command.volume==='git')return;for(const details")
    return page


def main():
    assert len({term.casefold() for term, _ in GLOSSARY}) == len(GLOSSARY)
    pages = {}
    for path in sorted((HERE / 'sources').glob('[0-9][0-9]-*.html')):
        source = path.read_text(encoding='utf-8')
        title = unescape(re.search(r'<h1>(.*?)</h1>', source, re.S)[1])
        lead = re.search(r'<header>.*?<p>(.*?)</p>.*?</header>', source, re.S)[1]
        body = re.sub(r'^\s*<header>.*?</header>\s*', '', source, flags=re.S)
        for diagram in DIAGRAMS:
            if diagram['chapter'] == path.stem:
                marker = diagram['insert_before']
                assert body.count(marker) == 1, (path.stem, marker)
                body = body.replace(marker, sketch(diagram) + '\n' + marker, 1)
        body = re.sub(r'(?<!<div class="table-wrap">)(<table\b.*?</table>)', r'<div class="table-wrap">\1</div>', body, flags=re.S)
        pages[path.stem] = dict(id=path.stem, title=title, lead=lead, body=body)
    terms = ''.join(f'<dt id="glossary-term-{i}">{escape(t)}</dt><dd>{escape(d)}</dd>' for i, (t,d) in enumerate(GLOSSARY))
    pages['99-glossary'] = dict(id='99-glossary', title='Словарь: от объекта Git до очереди сборки',
        lead='Определения и связи с наблюдаемыми механизмами', body='<p>Уточняйте термин при первом встреченном употреблении. Общий словарь в боковой панели ищет также по остальным томам.</p><dl class="glossary">'+terms+'</dl>')
    order = [identifier for _, identifiers in SECTIONS for identifier in identifiers]
    assert set(order) == set(pages) and len(order) == len(pages)
    articles = []; stats = []; nav = '<nav class="chapter-nav">'
    for section, identifiers in SECTIONS:
        nav += '<div class="course-label">'+escape(section)+'</div>'
        for identifier in identifiers:
            p = pages[identifier]
            number = str(int(identifier[:2])) if identifier[:2] not in ('00','99') else '•'
            nav += f'<a id="nav-{identifier}" href="#{identifier}"><span class="chapter-num">{number}</span><span>{escape(p["title"])}</span></a>'
            toc = []
            def heading(match):
                anchor = match[1] or identifier+'-section-'+str(len(toc)+1)
                toc.append((anchor, plain(match[2])))
                return f'<h2 id="{anchor}">{match[2]}</h2>'
            body = re.sub(r'<h2(?: id="([^"]+)")?>(.*?)</h2>', heading, p['body'], flags=re.S)
            words = len(re.findall(r'\S+', plain(body)))
            stats.append(dict(id=identifier, title=p['title'], words=words, part=section, number=number))
            index = order.index(identifier)
            prev = '#'+order[index-1] if index else '../index.html'
            nxt = '#'+order[index+1] if index+1<len(order) else '../index.html'
            contents = '<details class="local-toc"><summary>Содержание главы</summary><ol>'+''.join(f'<li><a href="#{a}">{escape(t)}</a></li>' for a,t in toc)+'</ol></details>' if toc else ''
            articles.append(f'''<article class="chapter" id="{identifier}"{' hidden' if index else ''}><header class="hero"><div class="eyebrow">Том VI · {escape(section)} · {number}</div><h1>{escape(p['title'])}</h1><div class="meta">{p['lead']} · {words} слов</div></header>{contents}{body}
<footer class="chapter-footer"><button class="read-toggle" aria-pressed="false">Отметить прочитанной</button><div style="margin-top:20px"><label for="note-{identifier}">Вопросы и заметки к главе</label><textarea class="note" id="note-{identifier}" placeholder="Что хочется проверить или перечитать…"></textarea><div class="note-state">Заметки сохраняются в этом браузере. Выгрузите отдельную копию перед переносом.</div></div><div class="footer-nav"><a href="{prev}">← Назад</a><a href="{nxt}">Дальше →</a></div></footer></article>''')
    nav += '</nav>'
    page = (ROOT / 'cache/sources/reader-shell.html').read_text(encoding='utf-8')
    page = page.replace('data-volume="bash"','data-volume="git"').replace('data-storage-key="bash-book-v1"','data-storage-key="git-book-v1"')
    page = re.sub(r'<title>.*?</title>', lambda _: '<title>'+TITLE+'</title>', page, count=1)
    page = re.sub(r'<meta name="description"[^>]*>', '<meta name="description" content="Git от объектов и индекса до совместной работы. Сборка, воспроизводимость, Jenkins, измерения и настоящая локальная лаборатория.">', page, count=1)
    page = page.replace('<div class="bookname">Bash</div>', '<div class="bookname">Git и сборка</div>')
    total = sum(row['words'] for row in stats)
    page = re.sub(r'<div class="subtitle">.*?</div>', f'<div class="subtitle">Том VI · Git и воспроизводимая сборка<br>{total:,} слов · {len(stats)} глав<br>Редакция 31 октября 2026</div>', page, count=1, flags=re.S)
    page = re.sub(r'<nav class="chapter-nav">.*?</nav>', lambda _: nav, page, count=1, flags=re.S)
    assert '<article class="chapter"' not in page.split('</main>')[0]
    page = page.replace('</noscript>', '</noscript>'+''.join(articles),1)
    base = json.loads((ROOT / 'bash/commands.json').read_text(encoding='utf-8'))
    names = {c['name'] for c in COMMANDS}
    commands = [c for c in base if c['name'] not in names] + COMMANDS
    assert len({c['name'] for c in commands}) == len(commands)
    for identifier, data in [('book-data',stats), ('glossary-data',GLOSSARY), ('flag-comparison-data',[]), ('command-reference-data',commands)]:
        page = put_json(page, identifier, data)
    page = reader_commands(page)
    page = page.replace('</style></head>', '''.course-label{font:800 13px/1.5 var(--sans);color:var(--accent);padding:20px 8px 5px;border-top:1px solid var(--line)}.chapter-nav a{grid-template-columns:35px 1fr}.command-chapter{display:inline-block}.callout a{color:inherit}@media(max-width:600px){.command-syntax{font-size:12px}}\n</style></head>''',1)
    write_text(HERE/'index.html',page)
    write_text(HERE/'Текст-тома.txt',TITLE+'\n\n'+'\n\n'.join(plain(a.split('<footer')[0]) for a in articles))
    write_text(HERE/'book-stats.json',json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    write_text(HERE/'commands.json',json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
    write_text(HERE/'Справочник-команд.txt','\n\n'.join(c['name']+'\n'+c['purpose']+'\n'+c['syntax']+'\n'+'\n'.join(f['flag']+' — '+f['action']+'\nКогда: '+f['when']+'\n'+f['example']+'\nРезультат: '+f['result'] for f in c['flags']) for c in commands))
    library = json.loads((ROOT/'library-stats.json').read_text(encoding='utf-8'))
    library = [r for r in library if r['slug']!='git']+[dict(slug='git',title=TITLE,volume='VI',words=total,chapters=len(stats),terms=len(GLOSSARY))]
    write_text(ROOT/'library-stats.json',json.dumps(library,ensure_ascii=False,indent=2)+'\n')
    home = (ROOT/'index.html').read_text(encoding='utf-8')
    home = re.sub(r'<a class="volume" href="git/index.html">.*?</a>', '', home, flags=re.S)
    card = f'<a class="volume" href="git/index.html"><div class="tag">Том VI</div><h2>Git и воспроизводимая сборка</h2><p>Байты и объекты → история и совместная работа → сборка → Jenkins → измерения и выпуск. Лаборатория сохраняет состояние.</p><div class="counts">{len(stats)} глав · {total:,} слов · словарь: {len(GLOSSARY)}</div><span class="open">Открыть том →</span></a>'
    home = home.replace('</div><section class="notes">', card+'</div><section class="notes">',1)
    home = home.replace('Пять связанных томов: сеть, ядро Linux, Bash, PostgreSQL и кэширование.', 'Шесть связанных томов: сеть, ядро Linux, Bash, PostgreSQL, кэширование, Git и сборка.')
    # Keep cards in the reading order even when an individual builder runs first.
    cards = re.findall(r'<a class="volume" href="([^"]+)/index.html">.*?</a>', home, re.S)
    card_html = {slug: re.search(r'<a class="volume" href="'+slug+r'/index.html">.*?</a>',home,re.S)[0] for slug in cards}
    home = re.sub(r'(<div class="grid">).*?(</div><section class="notes">)',lambda m:m[1]+''.join(card_html[v] for v in ['networks','linux','bash','postgres','cache','git'])+m[2],home,count=1,flags=re.S)
    home = re.sub(r'<details data-git-map>.*?</details>', '', home, flags=re.S)
    links = '<details data-git-map><summary>Git и сборка · 6 схем</summary><ul>'+''.join(f'<li><a href="git/index.html#{d["id"]}">{escape(d["title"])}</a> <span class="small">· {len(d["steps"])} шагов</span></li>' for d in DIAGRAMS)+'</ul></details>'
    home = home.replace('</section><section class="notes" style="margin-top:22px"><h2>Как читать',links+'</section><section class="notes" style="margin-top:22px"><h2>Как читать',1)
    write_text(ROOT/'index.html',home)
    terms = refresh()
    print(json.dumps(dict(volume='VI',words=total,chapters=len(stats),terms=len(GLOSSARY),commands=len(COMMANDS),diagrams=len(DIAGRAMS),steps=sum(len(d['steps']) for d in DIAGRAMS),shared_terms=terms),ensure_ascii=False))


if __name__ == '__main__':
    main()
