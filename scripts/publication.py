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
    return tuple(rows)


PUBLISHED = read_registry(Path(__file__).resolve().parents[1]/'published-volumes.json')
VOLUME_TITLES = {row['slug']: row['title'] for row in PUBLISHED}
MANAGED_VOLUMES = tuple(row['slug'] for row in PUBLISHED if row['build'] == 'managed')
