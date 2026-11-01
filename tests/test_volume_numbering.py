"""Displayed book numbers follow the route and cannot publish an extra book."""
import json
from pathlib import Path
import re
import tempfile
import unittest

from scripts.publication import PUBLICATION_ORDER, VOLUME_NUMBERS, read_registry
from scripts.library_structure import RECOMMENDED_ORDER
from scripts.volume_config import CONFIGS


ROOT = Path(__file__).resolve().parents[1]


class NumbersTests(unittest.TestCase):
    def test_foundations_precede_linux_and_every_published_book_has_one_number(self):
        self.assertEqual(PUBLICATION_ORDER, tuple(s for s in RECOMMENDED_ORDER if s in VOLUME_NUMBERS))
        self.assertEqual([VOLUME_NUMBERS[s] for s in PUBLICATION_ORDER[:5]], ['I', 'II', 'III', 'IV', 'V'])
        self.assertEqual(PUBLICATION_ORDER[:3], ('computer-architecture', 'operating-systems', 'linux'))
        self.assertEqual(len(set(VOLUME_NUMBERS.values())), len(VOLUME_NUMBERS))
        for slug, cfg in CONFIGS.items():
            self.assertEqual(cfg['volume'], VOLUME_NUMBERS[slug], slug)

    def test_incomplete_duplicate_and_unregistered_reading_orders_are_rejected(self):
        row = dict(slug='linux', title='Linux', build='legacy')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'registry.json'
            for order in ([], ['linux', 'linux'], ['secret'], [None], 'linux'):
                path.write_text(json.dumps(dict(format=1, volumes=[row], reading_order=order)))
                with self.subTest(order=order), self.assertRaises(ValueError):
                    read_registry(path)
            path.write_text(json.dumps(dict(format=1, volumes=[row], reading_order=['linux'])))
            self.assertEqual(read_registry(path), (row,))

    def test_actual_headers_and_home_cards_agree_with_the_same_registry(self):
        home = (ROOT/'index.html').read_text(encoding='utf-8')
        rows = {r['slug']: r for r in json.loads((ROOT/'library-stats.json').read_text())}
        for slug, number in VOLUME_NUMBERS.items():
            with self.subTest(slug=slug):
                self.assertEqual(rows[slug]['volume'], number)
                page = (ROOT/slug/'index.html').read_text(encoding='utf-8')
                labels = re.findall(r'<div class="(?:eyebrow|subtitle)">Том ([IVXLCDM]+)(?=[ ·<])', page)
                self.assertTrue(labels)
                self.assertEqual(set(labels), {number})
                card = re.search(r'<a class="volume" href="'+re.escape(slug)+r'/index.html"[^>]*>(.*?)</a>', home, re.S)
                self.assertIsNotNone(card)
                self.assertIn('<div class="tag">Том '+number+'</div>', card[1])


if __name__ == '__main__':
    unittest.main()
