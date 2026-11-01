"""Derive reading metadata from the three maintained legacy HTML manuscripts.

The articles remain authoritative. No prose, anchors or reader state are rebuilt.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from cache.build import plain, write_text
from scripts.publication import VOLUME_NUMBERS


class Chapters(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source, self.current, self.spans = source, None, []
        self.lines = [0]
        self.lines.extend(match.end() for match in re.finditer('\n', source))
        self.feed(source)
        self.close()
        if self.current:
            raise ValueError('Unclosed chapter article')

    def position_index(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article' and 'chapter' in attrs.get('class', '').split():
            if self.current or not attrs.get('id'):
                raise ValueError('Nested chapter or missing chapter ID')
            self.current = (attrs['id'], self.position_index())

    def handle_endtag(self, tag):
        if tag == 'article' and self.current:
            identifier, start = self.current
            end = self.source.index('>', self.position_index()) + 1
            self.spans.append((identifier, start, end))
            self.current = None


def derive(page, stats):
    """Validate first, return new page/stats/text without writing any files."""
    data_match = re.search(r'(<script\b[^>]*\bid="book-data"[^>]*>)(.*?)(</script>)', page, re.S)
    if not data_match:
        raise ValueError('Legacy book-data is missing')
    rows = json.loads(data_match[2])
    glossary_match = re.search(r'<script\b[^>]*\bid="glossary-data"[^>]*>(.*?)</script>', page, re.S)
    glossary = json.loads(glossary_match[1]) if glossary_match else None
    if not isinstance(glossary, list):
        raise ValueError('Legacy glossary data is missing or malformed')
    spans = Chapters(page).spans
    ids = [identifier for identifier, _, _ in spans]
    if (len(ids) != len(set(ids)) or ids != [row['id'] for row in rows] or
            ids != [row['id'] for row in stats['chapters']]):
        raise ValueError('Legacy articles and chapter metadata differ')
    result = page
    chapters, texts, replacements = [], [], []
    for row, (_, start, end) in zip(rows, spans):
        article = page[start:end]
        if '</header>' not in article or '<footer class="chapter-footer">' not in article:
            raise ValueError('Legacy chapter header/footer is missing: '+row['id'])
        header, body = article.split('</header>', 1)
        body = body.split('<footer class="chapter-footer">', 1)[0]
        body = re.sub(r'<details class="local-toc">.*?</details>', '', body, count=1, flags=re.S)
        words = len(re.findall(r'\S+', plain(body)))
        meta = re.search(r'(<div class="meta">)(.*?)(</div>)', header, re.S)
        if not meta or not re.search(r' · [\d\s,\u202f]+ слов(?:а|о)?$', meta[2]):
            raise ValueError('Legacy chapter word label is missing: '+row['id'])
        label = re.sub(r' · [\d\s,\u202f]+ слов(?:а|о)?$',
                       ' · '+format(words, ',').replace(',', ' ')+' слов', meta[2])
        new_header = header[:meta.start(2)] + label + header[meta.end(2):]
        new_article = new_header + '</header>' + article.split('</header>', 1)[1]
        replacements.append((start, end, new_article))
        chapters.append({**row, 'words': words})
        # Include the chapter heading, but not notes, navigation or reader UI.
        text = re.sub(r'<details class="local-toc">.*?</details>', '',
                      new_article.split('<footer class="chapter-footer">', 1)[0], count=1, flags=re.S)
        texts.append(plain(text))
    for start, end, value in reversed(replacements):
        result = result[:start] + value + result[end:]
    encoded = json.dumps(chapters, ensure_ascii=False).replace('</', '<\\/')
    result = re.sub(r'(<script\b[^>]*\bid="book-data"[^>]*>).*?(</script>)',
                    lambda match: match[1] + encoded + match[2], result, count=1, flags=re.S)
    updated = {**stats, 'chapters': chapters, 'words': sum(row['words'] for row in chapters), 'terms': len(glossary)}
    text = stats['title']+'\nТом '+stats['volume']+'\nРедакция 1 ноября 2026\n\n'+'\n\n'.join(texts)+'\n'
    return result, updated, text


def refresh_legacy(root, slugs=('linux', 'bash', 'postgres')):
    root = Path(root)
    library_path = root/'library-stats.json'
    library = json.loads(library_path.read_text(encoding='utf-8'))
    by_slug = {row['slug']: row for row in library}
    plans = []
    for slug in slugs:
        here = root/slug
        stats = json.loads((here/'book-stats.json').read_text(encoding='utf-8'))
        stats['volume'] = VOLUME_NUMBERS[slug]
        page = (here/'index.html').read_text(encoding='utf-8')
        page = re.sub(r'(<div class="(?:subtitle|eyebrow)">)Том [IVXLCDM]+',
                      lambda m: m[1]+'Том '+stats['volume'], page)
        page, stats, text = derive(page, stats)
        def subtitle(match):
            label = re.sub(r'[0-9 ,\u202f]+ слов(?:а|о)?', format(stats['words'], ',').replace(',', ' ')+' слов', match[2], count=1)
            return match[1]+label+match[3]
        page = re.sub(r'(<div class="subtitle">)(.*?)(</div>)', subtitle, page, count=1, flags=re.S)
        if slug not in by_slug:
            raise ValueError('Legacy book missing from library stats: '+slug)
        by_slug[slug].update(volume=stats['volume'], words=stats['words'], chapters=len(stats['chapters']), terms=stats['terms'])
        plans.append((here, page, stats, text))
    for here, page, stats, text in plans:
        write_text(here/'index.html', page)
        write_text(here/'book-stats.json', json.dumps(stats, ensure_ascii=False, indent=2)+'\n')
        write_text(here/'Текст-тома.txt', text)
    write_text(library_path, json.dumps(library, ensure_ascii=False, indent=2)+'\n')
    return {here.name: stats['words'] for here, _, stats, _ in plans}
