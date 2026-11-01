"""Explicit publication allowlist; an author's directory alone cannot publish it."""
import json
from pathlib import Path
import re


def read_registry(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or type(data.get('format')) is not int or data['format'] != 1:
        raise ValueError('Unsupported published-volumes registry format')
    rows = data.get('volumes')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Publication registry must contain volumes')
    slugs = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'slug', 'title', 'build'}:
            raise ValueError('Invalid publication entry')
        slug, title = row['slug'], row['title']
        if not isinstance(slug, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', slug):
            raise ValueError('Unsafe publication slug')
        if slug in slugs:
            raise ValueError('Duplicate publication slug: '+slug)
        slugs.add(slug)
        if not isinstance(title, str) or not title.strip() or title != title.strip():
            raise ValueError('Invalid publication title: '+slug)
        if not isinstance(row['build'], str) or row['build'] not in {'network', 'legacy', 'cache', 'managed'}:
            raise ValueError('Unknown build kind: '+slug)
    order = data.get('reading_order', [row['slug'] for row in rows])
    if not isinstance(order, list) or any(not isinstance(slug, str) for slug in order) or len(order) != len(set(order)) or set(order) != slugs:
        raise ValueError('Reading order must contain each published volume exactly once')
    return tuple(rows)


PUBLISHED = read_registry(Path(__file__).resolve().parents[1]/'published-volumes.json')
VOLUME_TITLES = {row['slug']: row['title'] for row in PUBLISHED}
MANAGED_VOLUMES = tuple(row['slug'] for row in PUBLISHED if row['build'] == 'managed')


def roman_number(number):
    if type(number) is not int or not 1 <= number <= 3999:
        raise ValueError('Volume number must be an integer in 1..3999')
    result = ''
    for value, token in ((1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')):
        count, number = divmod(number, value)
        result += token * count
    return result


_registry = json.loads((Path(__file__).resolve().parents[1]/'published-volumes.json').read_text(encoding='utf-8'))
PUBLICATION_ORDER = tuple(_registry.get('reading_order', [row['slug'] for row in PUBLISHED]))
VOLUME_NUMBERS = {slug: roman_number(i) for i, slug in enumerate(PUBLICATION_ORDER, 1)}


def refresh_publication_metadata(root):
    path = Path(root)/'library-stats.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    for row in rows:
        if row['slug'] in VOLUME_NUMBERS:
            row['volume'] = VOLUME_NUMBERS[row['slug']]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for slug, number in VOLUME_NUMBERS.items():
        for name in ('README.txt', 'ПРОВЕРКИ.txt'):
            document = Path(root)/slug/name
            if document.is_file():
                source = document.read_bytes().decode('utf-8')
                updated = re.sub(r'\AТом [IVXLCDM]+(?=[ .:—·])', 'Том '+number, source, count=1)
                if updated != source:
                    document.write_bytes(updated.encode('utf-8'))
