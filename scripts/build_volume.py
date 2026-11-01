#!/usr/bin/env python3
"""Build independent technology volumes with the common offline reader."""
from pathlib import Path
from html import escape, unescape
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cache.build import dump, put_json, plain, write_text, sketch
from scripts.volume_config import CONFIGS, TARGETS


def module(path):
    spec = importlib.util.spec_from_file_location('volume_' + '_'.join(path.parts[-3:]).replace('.', '_'), path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def remap_links(body, slug):
    def replace(match):
        href = unescape(match[1])
        # Re-home old links by stable chapter ID, including section anchors.
        parts = href.split('#', 1)
        if len(parts) != 2:
            return match[0]
        path, anchor = parts
        if path not in ('', 'index.html', *('../'+name+'/index.html' for name in CONFIGS)):
            return match[0]
        if anchor in ('90-git-book', '92-jenkins-book'):
            target = 'git' if anchor == '90-git-book' else 'jenkins'
            anchor = '00-route'
        else:
            chapter = next((i for i in TARGETS if anchor == i or anchor.startswith(i+'-section-')), None)
            target = TARGETS.get(chapter)
        if target:
            return 'href="' + ('' if target == slug else '../'+target+'/index.html') + '#' + escape(anchor, quote=True) + '"'
        return match[0]
    return re.sub(r'href="([^"]*)"', replace, body)


def command_catalog():
    original = module(ROOT/'git/sources/git_reference.py').COMMANDS
    extra = module(ROOT/'go/sources/go_deep_reference.py').COMMANDS
    complete = module(ROOT/'go/sources/tool_flag_reference.py').COMMANDS
    merged = {c['name']: dict(c) for c in json.loads((ROOT/'bash/commands.json').read_text())}
    added = [command for slug,cfg in CONFIGS.items()
             for name in cfg.get('command_modules', [])
             for command in module(ROOT/slug/'sources'/f'{name}.py').COMMANDS]
    for c in original + extra + complete + added:
        c = dict(c)
        c['volume'] = TARGETS.get(c['chapter'], c['volume'])
        merged[c['name']] = c
    return list(merged.values())


def reader_commands(page):
    native = "['"+"','".join(CONFIGS)+"']"
    # Go also has the punctuation-named compiler flags -% and -+.
    page = page.replace(r'([+-]{1,2}[A-Za-z0-9][A-Za-z0-9-]*)',
                        r'([+-]{1,2}(?:[A-Za-z0-9_][A-Za-z0-9_-]*|[%+]))')
    # Preserve = for boolean Go options: -N=false must not become -N false.
    page = page.replace('options.push({ name: wholeName, value, hasValue });',
                        'options.push({ name: wholeName, value, hasValue, equals: equals > 0 });')
    page = page.replace("option.name.startsWith('--') ? '=' :", "option.equals || option.name.startsWith('--') ? '=' :")
    old_line = "const line = String(followingText).split(/[\\n|;&]/, 1)[0].slice(0, 240);"
    new_line = r'''const text = String(followingText).slice(0, 240);
    let quote = null, escaped = false, end = text.length;
    for (let i=0;i<text.length;i++) {
        const c=text[i];
        if (escaped) {escaped=false;continue;}
        if (c==='\\' && quote!=="'") {escaped=true;continue;}
        if (quote) {if(c===quote)quote=null;continue;}
        if (c==='"'||c==="'") {quote=c;continue;}
        if ('\n|;&'.includes(c)) {end=i;break;}
    }
    const line=text.slice(0,end);'''
    assert page.count(old_line) == 1
    page = page.replace(old_line,new_line)
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
    page = page.replace(old, "("+native+".includes(command.volume)?'<p class=\"callout\">Эта команда выполняется в отдельном учебном окружении. <a href=\"'+escapeHTML(chapter)+'\" data-reference-chapter>Условия и практический разбор →</a></p>':'<div data-learning-terminal></div>')+")
    old = '''<button type="button" data-try-example="'+flagIndex+'">В терминал ↑</button>'''
    assert old in page
    page = page.replace(old, "'+("+native+".includes(command.volume)?'':'<button type=\"button\" data-try-example=\"'+flagIndex+'\">В терминал ↑</button>')+'")
    page = page.replace('commands.some(command => matchesCommand(command, token))',
                        'commands.some(command => commandPrefix(command, tokenizeQuery(input.value)))')
    page = page.replace('function mount(container,command){for(const details',
                        "function mount(container,command){if("+native+".includes(command.volume))return;for(const details")
    return page


def build(slug):
    cfg = CONFIGS[slug]
    here = ROOT/slug
    sections = cfg['sections']
    order = [i for _, ids in sections for i in ids]
    reference = module(ROOT/'git/sources/git_reference.py')
    terms = [reference.GLOSSARY[i] for i in cfg['base_terms']]
    for name in cfg['term_modules']:
        terms += module(here/'sources'/f'{name}.py').GLOSSARY
    combined = {}
    for term, definition in terms:
        combined.setdefault(term.casefold(), (term, definition))
    glossary = list(combined.values())
    diagrams = []
    for name in cfg['diagram_modules']:
        diagrams += module(here/'sources'/f'{name}.py').DIAGRAMS
    pages = {}
    for identifier in order:
        if identifier == '99-glossary':
            continue
        source = (here/'sources'/f'{identifier}.html').read_text(encoding='utf-8')
        title = re.sub(r'^\d+[.)]\s*', '', plain(re.search(r'<h1>(.*?)</h1>', source, re.S)[1]))
        lead = re.search(r'<header>.*?<p>(.*?)</p>.*?</header>', source, re.S)[1]
        body = re.sub(r'^\s*<header>.*?</header>\s*', '', source, flags=re.S)
        for diagram in diagrams:
            if diagram['chapter'] == identifier:
                marker = diagram.get('insert_before')
                if marker:
                    assert body.count(marker) == 1, (slug, identifier, marker)
                    body = body.replace(marker, sketch(diagram)+'\n'+marker, 1)
                else:
                    body += '\n'+sketch(diagram)
        # Existing source wrappers must not be nested by the builder.
        body = re.sub(r'(?<!<div class="table-wrap">)(<table\b.*?</table>)', r'<div class="table-wrap">\1</div>', body, flags=re.S)
        pages[identifier] = dict(id=identifier, title=title, lead=lead, body=remap_links(body,slug))
    definitions = ''.join(f'<dt id="glossary-term-{i}">{escape(t)}</dt><dd>{escape(d)}</dd>' for i,(t,d) in enumerate(glossary))
    pages['99-glossary'] = dict(id='99-glossary',title='Словарь · '+cfg['short'],lead='Понятия и их связь с наблюдаемыми механизмами',body='<p>Словарь в боковой панели также ищет определения во всех остальных томах.</p><dl class="glossary">'+definitions+'</dl>')
    toc = ''.join('<h3>'+escape(section)+'</h3><ol>'+''.join('<li><a href="#'+i+'">'+escape(pages[i]['title'])+'</a></li>' for i in ids if i not in {'00-route','91-build-book','99-glossary'})+'</ol>' for section,ids in sections if any(i not in {'00-route','91-build-book','99-glossary'} for i in ids))
    for p in pages.values():
        p['body'] = p['body'].replace('<div data-volume-toc></div>', '<div class="volume-toc">'+toc+'</div>')
    articles = []; stats = []; nav = '<nav class="chapter-nav">'; headings = set(); chapter_number = 0
    for section, identifiers in sections:
        nav += '<div class="course-label">'+escape(section)+'</div>'
        for identifier in identifiers:
            p = pages[identifier]
            if identifier not in {'00-route','91-build-book','99-glossary'}:
                chapter_number += 1
                number = str(chapter_number)
            else:
                number = '•'
            nav += f'<a id="nav-{identifier}" href="#{identifier}"><span class="chapter-num">{number}</span><span>{escape(p["title"])}</span></a>'
            local_toc = []
            def heading(match):
                anchor = match[1] or identifier+'-section-'+str(len(local_toc)+1)
                assert anchor not in headings, (slug, anchor)
                headings.add(anchor)
                local_toc.append((anchor, plain(match[2])))
                return f'<h2 id="{anchor}">{match[2]}</h2>'
            body = re.sub(r'<h2(?: id="([^"]+)")?>(.*?)</h2>', heading, p['body'], flags=re.S)
            words = len(re.findall(r'\S+', plain(body)))
            stats.append(dict(id=identifier,title=p['title'],words=words,part=section,number=number))
            index = order.index(identifier)
            prev = '#'+order[index-1] if index else '../index.html'
            nxt = '#'+order[index+1] if index+1<len(order) else '../index.html'
            contents = '<details class="local-toc"><summary>Содержание главы</summary><ol>'+''.join(f'<li><a href="#{a}">{escape(t)}</a></li>' for a,t in local_toc)+'</ol></details>' if local_toc else ''
            articles.append(f'''<article class="chapter" id="{identifier}"{' hidden' if index else ''}><header class="hero"><div class="eyebrow">Том {cfg['volume']} · {escape(section)}</div><h1>{escape(p['title'])}</h1><div class="meta">{p['lead']} · {words} слов</div></header>{contents}{body}
<footer class="chapter-footer"><button class="read-toggle" aria-pressed="false">Отметить прочитанной</button><div style="margin-top:20px"><label for="note-{identifier}">Вопросы и заметки к главе</label><textarea class="note" id="note-{identifier}" placeholder="Что хочется проверить или перечитать…"></textarea><div class="note-state">Заметки сохраняются в этом браузере. Выгрузите отдельную копию перед переносом.</div></div><div class="footer-nav"><a href="{prev}">← Назад</a><a href="{nxt}">Дальше →</a></div></footer></article>''')
    nav += '</nav>'
    page = (ROOT/'cache/sources/reader-shell.html').read_text(encoding='utf-8')
    page = page.replace('data-volume="bash"',f'data-volume="{slug}"').replace('data-storage-key="bash-book-v1"',f'data-storage-key="{slug}-book-v1"')
    page = re.sub(r'<title>.*?</title>',lambda _: '<title>'+escape(cfg['title'])+'</title>',page,count=1)
    page = re.sub(r'<meta name="description"[^>]*>',lambda _: '<meta name="description" content="'+escape(cfg['description'],quote=True)+'">',page,count=1)
    page = page.replace('<div class="bookname">Bash</div>','<div class="bookname">'+cfg['short']+'</div>')
    total = sum(r['words'] for r in stats)
    page = re.sub(r'<div class="subtitle">.*?</div>',f'<div class="subtitle">Том {cfg["volume"]}<br>{total:,} слов · {len(stats)} глав<br>Редакция {cfg.get("revision", "31 октября 2026")}</div>',page,count=1,flags=re.S)
    page = re.sub(r'<nav class="chapter-nav">.*?</nav>',lambda _: nav,page,count=1,flags=re.S)
    page = page.replace('</noscript>','</noscript>'+''.join(articles),1)
    commands = command_catalog()
    for identifier,data in [('book-data',stats),('glossary-data',glossary),('flag-comparison-data',[]),('command-reference-data',commands)]:
        page = put_json(page,identifier,data)
    page = reader_commands(page)
    page = page.replace('</style></head>', '.inner-books a{display:block;padding:20px;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;text-decoration:none}.inner-books strong{display:block;font:750 20px/1.4 var(--sans)}.inner-books span{display:block;margin-top:9px;color:var(--muted);font:16px/1.6 var(--sans)}\n</style></head>',1)
    page = page.replace('Object.values(state.read).filter(Boolean).length','data.filter(c=>state.read[c.id]).length')
    if slug in {'go','jenkins'}:
        # Copy only this volume's notes on first opening. Preserve the old store.
        migration = '<script>(()=>{try{const key='+dump(slug+'-book-v1')+';if(localStorage.getItem(key)!==null)return;const old=JSON.parse(localStorage.getItem("git-book-v1")||"null");if(!old||typeof old!=="object")return;const ids='+dump(order)+';const next={theme:old.theme,size:old.size};for(const field of ["notes","read","scroll"])next[field]=Object.fromEntries(Object.entries(old[field]||{}).filter(([id])=>ids.includes(id)));if(ids.includes(old.current))next.current=old.current;localStorage.setItem(key,JSON.stringify(next));}catch(e){}})();</script>'
        page = re.sub(r'(<body[^>]*>)',lambda m:m[1]+migration,page,count=1)
    page = page.replace('</style></head>','.course-label{font:800 13px/1.5 var(--sans);color:var(--accent);padding:20px 8px 5px;border-top:1px solid var(--line)}.chapter-nav a{grid-template-columns:35px 1fr}.volume-toc{border-left:3px solid var(--accent);padding-left:20px}.volume-toc li{margin-bottom:8px}.command-chapter{display:inline-block}.callout a{color:inherit}@media(max-width:600px){.command-syntax{font-size:12px}}\n</style></head>',1)
    if slug == 'git':
        legacy = json.loads((here/'sources/legacy-links.json').read_text())
        targets = {}
        links = []
        for anchor, destination in legacy.items():
            target_slug = destination['volume']
            target_anchor = destination['chapter']
            # Keep the old position when the destination still has that heading.
            if target_slug != slug and (ROOT/target_slug/'index.html').exists():
                target_page = (ROOT/target_slug/'index.html').read_text()
                if f'id="{anchor}"' in target_page: target_anchor = anchor
            href = ('' if target_slug == slug else '../'+target_slug+'/index.html')+'#'+target_anchor
            targets[anchor] = href
            if anchor not in order and anchor not in headings:
                links.append(f'<a id="{anchor}" href="{href}">{escape(anchor)}</a>')
        page = page.replace('</main>','<div hidden data-legacy-links>'+''.join(links)+'</div></main>',1)
        redirect = '<script>(()=>{const moved='+dump(targets)+';function follow(){let key;try{key=decodeURIComponent(location.hash.slice(1));}catch(e){return;}if(moved[key])location.replace(moved[key]);}addEventListener("hashchange",follow);follow();})();</script>'
        page = re.sub(r'(<body[^>]*>)', lambda m:m[1]+redirect, page, count=1)
    write_text(here/'index.html',page)
    write_text(here/'Текст-тома.txt',cfg['title']+'\n\n'+'\n\n'.join(plain(a.split('<footer')[0]) for a in articles))
    write_text(here/'book-stats.json',json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    write_text(here/'commands.json',json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
    write_text(here/'Справочник-команд.txt','\n\n'.join(c['name']+'\n'+c['purpose']+'\n'+c['syntax']+'\n'+'\n'.join(f['flag']+' — '+f['action']+'\nКогда: '+f['when']+'\n'+f['example']+'\nРезультат: '+f['result'] for f in c['flags']) for c in commands))
    library = json.loads((ROOT/'library-stats.json').read_text())
    library = [r for r in library if r['slug'] != slug]+[dict(slug=slug,title=cfg['title'],volume=cfg['volume'],words=total,chapters=len(stats),terms=len(glossary))]
    write_text(ROOT/'library-stats.json',json.dumps(library,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(volume=slug,words=total,chapters=len(stats),terms=len(glossary),commands=len(commands),diagrams=len(diagrams),steps=sum(len(d['steps']) for d in diagrams)),ensure_ascii=False))


def home():
    page = (ROOT/'index.html').read_text(encoding='utf-8')
    stats = {r['slug']:r for r in json.loads((ROOT/'library-stats.json').read_text())}
    if any(slug not in stats or not (ROOT/slug/'index.html').exists() for slug in CONFIGS):
        return
    for slug,cfg in CONFIGS.items():
        page = re.sub(r'<a class="volume" href="'+slug+r'/index.html">.*?</a>','',page,flags=re.S)
        row = stats[slug]
        card = f'<a class="volume" href="{slug}/index.html"><div class="tag">Том {cfg["volume"]}</div><h2>{cfg["short"]}</h2><p>{cfg["blurb"]}</p><div class="counts">{row["chapters"]} глав · {row["words"]:,} слов · словарь: {row["terms"]}</div><span class="open">Открыть том →</span></a>'
        page = page.replace('</div><section class="notes">',card+'</div><section class="notes">',1)
    cards = {slug: re.search(r'<a class="volume" href="'+slug+r'/index.html">.*?</a>',page,re.S)[0] for slug in ['networks','linux','bash','postgres','cache',*CONFIGS]}
    page = re.sub(r'(<div class="grid">).*?(</div><section class="notes">)',lambda m:m[1]+''.join(cards.values())+m[2],page,count=1,flags=re.S)
    page = re.sub(r'<section class="notes" data-inner-books>.*?</section>','',page,flags=re.S)
    page = re.sub(r'<p class="lead">.*?</p>', '<p class="lead">Девять связанных томов: сети, Linux, Bash, PostgreSQL, кэширование, Git, Go, Jenkins и GitLab. От устройства механизма до расчёта ресурсов, наблюдения и восстановления.</p>', page, count=1, flags=re.S)
    for slug in ('networks','linux','bash','postgres','cache'):
        row = stats[slug]
        counts = f'<div class="counts">{row["chapters"]} глав · {row["words"]:,} слов · словарь: {row["terms"]}</div>'
        page = re.sub(r'(<a class="volume" href="'+slug+r'/index.html">.*?)<div class="counts">.*?</div>', lambda m: m[1]+counts, page, count=1, flags=re.S)
    for slug,cfg in CONFIGS.items():
        page = re.sub(r'<details data-'+slug+r'-map>.*?</details>','',page,flags=re.S)
        diagrams = [d for name in cfg['diagram_modules'] for d in module(ROOT/slug/'sources'/f'{name}.py').DIAGRAMS]
        links = '<details data-'+slug+'-map><summary>'+cfg['short']+' · '+str(len(diagrams))+' схем</summary><ul>'+''.join(f'<li><a href="{slug}/index.html#{d["id"]}">{escape(d["title"])}</a> <span class="small">· {len(d["steps"])} шагов</span></li>' for d in diagrams)+'</ul></details>'
        page = page.replace('</section><section class="notes" style="margin-top:22px"><h2>Как читать',links+'</section><section class="notes" style="margin-top:22px"><h2>Как читать',1)
    depth_path = ROOT/'networks/sources/depth-diagrams.json'
    if depth_path.exists():
        page = re.sub(r'<li data-network-depth>.*?</li>', '', page, flags=re.S)
        diagrams = json.loads(depth_path.read_text())
        links = ''.join('<li data-network-depth><a href="networks/index.html#'+d['id']+'">'+escape(d['title'])+'</a> <span class="small">· '+str(len(d['steps']))+' шагов</span></li>' for d in diagrams)
        page = re.sub(r'<details><summary>Сети · \d+ схем</summary><ul>(.*?)</ul></details>', lambda m:'<details><summary>Сети · '+str(m[1].count('<li')+len(diagrams))+' схем</summary><ul>'+m[1]+links+'</ul></details>', page, count=1, flags=re.S)
    write_text(ROOT/'index.html',page)


if __name__ == '__main__':
    for slug in sys.argv[1:] or CONFIGS: build(slug)
    if all((ROOT/slug/'index.html').exists() for slug in CONFIGS): home()
