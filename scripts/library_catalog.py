"""Refresh the common offline dictionary after building individual volumes."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VOLUMES = {'networks': 'Сети', 'linux': 'Linux', 'bash': 'Bash',
           'postgres': 'PostgreSQL', 'cache': 'Кэш и базы в памяти',
           'git': 'Git и воспроизводимая сборка'}


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
        write(path, page)
    stats_path = ROOT / 'library-stats.json'
    stats = json.loads(stats_path.read_text(encoding='utf-8'))
    stats.sort(key=lambda row: list(VOLUMES).index(row['slug']))
    write(stats_path, json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    return len(library)


if __name__ == '__main__':
    print(refresh())
