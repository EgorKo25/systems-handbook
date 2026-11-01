"""Editorial changes must reach TXT, counts and ETA without altering reader keys."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.legacy_reading import derive, refresh_legacy


ROW = dict(id='first', title='Title', words=2)
STATS = dict(title='Book', volume='II', storage_key='notes-old', chapters=[ROW], words=2, terms=0)
PAGE = '''<html><head><script>const example='<article class="chapter" id="fake">';</script></head><body>
<article id="first" class="chapter"><header><h1>Title</h1><div class="meta">Lead · 2 слов</div></header>
<details class="local-toc"><summary>Contents</summary><ol><li>Repeated heading</li></ol></details>
<h2 id="stable">Meaning</h2><p>Before after why.</p><script type="application/json">{"diagram":"not words"}</script>
<footer class="chapter-footer"><textarea id="notes">Do not count this</textarea></footer></article>
<script type="application/json" id="book-data">[{"id":"first","title":"Title","words":2}]</script>
<script type="application/json" id="glossary-data">[]</script>
<script>localStorage.getItem('notes-old')</script></body></html>'''


class LegacyReadingTests(unittest.TestCase):
    def test_article_text_drives_counts_and_txt_without_controls_or_json(self):
        page, stats, text = derive(PAGE, STATS)
        self.assertEqual(stats['words'], 4)
        self.assertEqual(stats['chapters'][0]['words'], 4)
        self.assertIn('Lead · 4 слов', page)
        self.assertIn('Before after why.', text)
        for excluded in ('Contents', 'Repeated heading', 'not words', 'Do not count this'):
            self.assertNotIn(excluded, text)
        self.assertIn('id="stable"', page)
        self.assertIn("localStorage.getItem('notes-old')", page)
        self.assertEqual(derive(page, stats), (page, stats, text))

    def test_mismatched_manuscript_does_not_silently_drop_a_chapter(self):
        with self.assertRaisesRegex(ValueError, 'metadata differ'):
            derive(PAGE.replace('id="first" class="chapter"', 'id="changed" class="chapter"'), STATS)

    def test_full_refresh_keeps_crlf_and_updates_library_before_home_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'linux').mkdir()
            (root/'linux/index.html').write_bytes(PAGE.replace('\n', '\r\n').encode())
            (root/'linux/book-stats.json').write_text(json.dumps(STATS))
            (root/'library-stats.json').write_text(json.dumps([dict(slug='linux', words=2)]))
            refresh_legacy(root, ('linux',))
            raw = (root/'linux/index.html').read_bytes()
            self.assertEqual(raw.count(b'\r\n'), raw.count(b'\n'))
            self.assertEqual(json.loads((root/'library-stats.json').read_text())[0]['words'], 4)
            self.assertIn('Before after why.', (root/'linux/Текст-тома.txt').read_text())
            refresh_legacy(root, ('linux',))
            self.assertEqual(raw, (root/'linux/index.html').read_bytes())


if __name__ == '__main__':
    unittest.main()
