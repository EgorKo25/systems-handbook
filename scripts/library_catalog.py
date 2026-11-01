"""Refresh the common offline dictionary after building individual volumes."""
import json
from pathlib import Path
import re

if __package__:
    from .reader_preferences import enhance as theme_preferences
    from .reader_theme_picker import enhance as theme_picker
    from .reader_selection import enhance as selection_lookup
    from .reader_navigation import normalize_reader_navigation
    from .reader_reading_time import enhance as reading_time
else:
    from reader_preferences import enhance as theme_preferences
    from reader_theme_picker import enhance as theme_picker
    from reader_selection import enhance as selection_lookup
    from reader_navigation import normalize_reader_navigation
    from reader_reading_time import enhance as reading_time

ROOT = Path(__file__).resolve().parents[1]
VOLUMES = {'networks': 'Сети', 'linux': 'Linux', 'bash': 'Bash',
           'postgres': 'PostgreSQL', 'cache': 'Кэш и базы в памяти',
           'git': 'Git', 'go': 'Go', 'jenkins': 'Jenkins', 'gitlab': 'GitLab', 'practicum':'Практикум'}


def write(path, value):
    old = path.read_bytes() if path.exists() else b''
    value = value.replace('\r\n', '\n')
    if old.decode('utf-8').replace('\r\n', '\n') != value:
        ending = '\r\n' if old and old.count(b'\r\n') == old.count(b'\n') else '\n'
        path.write_bytes(value.replace('\n', ending).encode('utf-8'))


def refresh():
    library = []
    pages = {}
    for slug in VOLUMES:
        path = ROOT / slug / 'index.html'
        if not path.exists():
            continue
        page = path.read_text(encoding='utf-8')
        local = json.loads(re.search(r'<script[^>]*id="glossary-data"[^>]*>(.*?)</script>', page, re.S)[1])
        library.extend(dict(term=t, definition=d, volume=slug, anchor=f'glossary-term-{i}')
                       for i, (t, d) in enumerate(local))
        pages[path] = page
    encoded = json.dumps(library, ensure_ascii=False).replace('</', '<\\/')
    labels = json.dumps({slug: title for slug, title in VOLUMES.items()
                        if ROOT / slug / 'index.html' in pages}, ensure_ascii=False)
    for path, page in pages.items():
        page = re.sub(r'(<script[^>]*id="library-glossary-data"[^>]*>).*?(</script>)',
                      lambda m: m[1] + encoded + m[2], page, flags=re.S)
        page = re.sub(r'const volumeTitles=\{[^;]*\};', lambda _: 'const volumeTitles=' + labels + ';', page)
        page = re.sub(r'Термины всех (?:четырёх |пяти |шести )?томов', 'Термины всех томов', page)
        page = theme_preferences(page)
        if __package__:
            from .reader_mobile import enhance as mobile_preferences
        else:
            from reader_mobile import enhance as mobile_preferences
        write(path, reading_time(theme_picker(selection_lookup(mobile_preferences(normalize_reader_navigation(page))))))
    home_path = ROOT / 'index.html'
    if home_path.exists():
        home = theme_preferences(home_path.read_text(encoding='utf-8'), home=True)
        if __package__:
            from .reader_mobile import enhance as mobile_preferences
        else:
            from reader_mobile import enhance as mobile_preferences
        write(home_path, theme_picker(mobile_preferences(home, home=True)))
    portal_path = ROOT/'labs-personal/index.html'
    if portal_path.exists():
        if __package__:
            from .reader_mobile import palette_css
        else:
            from reader_mobile import palette_css
        portal = theme_preferences(portal_path.read_text(), home=True)
        portal = re.sub(r'<style id="lab-portal-theme">.*?</style>','',portal,flags=re.S)
        css = palette_css()+'\n:root{color-scheme:light}:root[data-theme=dark]{color-scheme:dark}code{background:var(--reader-code);color:var(--reader-code-text)}.portal-toolbar{display:flex;justify-content:space-between;align-items:center;gap:18px}.portal-toolbar button{min-height:44px;padding:9px 16px;border:1px solid var(--line);border-radius:24px;color:var(--text);background:var(--paper);font:600 14px system-ui;cursor:pointer;touch-action:manipulation}'
        portal = portal.replace('</head>','<style id="lab-portal-theme">'+css+'</style></head>',1)
        write(portal_path, theme_picker(portal))
    stats_path = ROOT / 'library-stats.json'
    stats = json.loads(stats_path.read_text(encoding='utf-8'))
    stats.sort(key=lambda row: list(VOLUMES).index(row['slug']))
    write(stats_path, json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    return len(library)


if __name__ == '__main__':
    print(refresh())
