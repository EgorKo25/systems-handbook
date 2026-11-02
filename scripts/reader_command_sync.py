"""Synchronize reference data/parser without rebuilding legacy reader UI.

Only the two existing, uniquely marked regions are replaced. All readers are
validated before the first write; this is not a crash-atomic file transaction.
"""
import json
from pathlib import Path
import re

START = 'function tokenizeQuery(value) {'
END = '// Mark only a command position, not words inside strings or configuration fields.'
OWNED_CARDS = frozenset({'bash', 'printf', 'set', 'trap', 'flock'})
DATA = re.compile(r'(<script\b[^>]*\bid="command-reference-data"[^>]*>)(.*?)(</script>)', re.S)


def synchronize_page(page, commands, parser):
    matches = list(DATA.finditer(page))
    if len(matches) != 1 or page.count(START) != 1 or page.count(END) != 1:
        raise ValueError('Reader reference regions must occur exactly once')
    if parser.count(START) != 1 or re.search(r'</script\b', parser, re.I):
        raise ValueError('Invalid standalone reference parser source')
    # The reusable source has a leading comment outside the replaceable region.
    # Do not prepend it again every time this page is synchronized.
    parser = parser[parser.index(START):]
    start, end = page.index(START), page.index(END)
    if start >= end:
        raise ValueError('Reversed reference parser markers')
    # Both markers must belong to the same executable script, not an article,
    # a sample code block or the JSON dataset.
    script = next((m for m in re.finditer(r'<script\b([^>]*)>(.*?)</script>', page, re.S)
                   if m.start(2) <= start < end <= m.end(2)), None)
    if script is None or 'application/json' in script[1].lower():
        raise ValueError('Reference parser is outside an executable script')
    existing = page[start:end]
    ending = '\r\n' if existing.count('\n') and existing.count('\r\n') == existing.count('\n') else '\n'
    replacement = parser.replace('\r\n', '\n').rstrip('\n').replace('\n', ending) + ending
    page = page[:start] + replacement + page[end:]
    existing_cards = json.loads(matches[0][2])
    replacements = {card['name']: card for card in commands if card['name'] in OWNED_CARDS}
    # Preserve local-only cards and newer volume-specific explanations verbatim.
    merged = [replacements.get(card['name'], card) for card in existing_cards]
    present = {card['name'] for card in merged}
    merged.extend(card for card in commands if card['name'] in OWNED_CARDS and card['name'] not in present)
    encoded = json.dumps(merged, ensure_ascii=False).replace('</', '<\\/')
    return DATA.sub(lambda m: m[1] + encoded + m[3], page, count=1)


def synchronize_readers(root, slugs, commands, parser):
    root = Path(root).resolve()
    plans = []
    for slug in slugs:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', slug):
            raise ValueError('Invalid published reader slug')
        path = root / slug / 'index.html'
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('Reader path leaves the publication root')
        before = path.read_bytes()
        after = synchronize_page(before.decode('utf-8'), commands, parser).encode('utf-8')
        plans.append((path, before, after))
    for path, before, after in plans:
        if before != after:
            path.write_bytes(after)
    return sum(before != after for _, before, after in plans)
