"""A first build must put newly created readers on the visible home shelf."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_library, build_volume, library_catalog


class FirstBuildTests(unittest.TestCase):
    def test_new_readers_appear_after_a_single_build_from_missing_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'index.html').write_text(
                '<html><head></head><body><main><div class="grid"></div>'
                '<section class="notes">Notes</section></main></body></html>')
            (root/'library-stats.json').write_text('[]')
            slugs = ('computer-architecture', 'operating-systems')
            configs = {slug: dict(volume=number, short=slug, blurb=slug, diagram_modules=[])
                       for slug, number in zip(slugs, ('XXIX', 'XXX'))}
            published = [dict(slug=slug, build='managed') for slug in slugs]
            built = []

            def build_reader(command, **kwargs):
                if Path(command[1]).name == 'build_networks.py':
                    return
                slug = Path(command[1]).parent.name
                self.assertIn(slug, slugs)
                self.assertFalse((root/slug/'index.html').exists())
                (root/slug).mkdir()
                (root/slug/'index.html').write_text('<h1>New reader</h1>')
                stats = json.loads((root/'library-stats.json').read_text())
                stats.append(dict(slug=slug, volume=configs[slug]['volume'],
                                  chapters=36, words=58000, terms=210))
                (root/'library-stats.json').write_text(json.dumps(stats))
                built.append(slug)

            def final_catalog():
                # The catalog enhances the final home; it must not preserve a
                # shelf that still says the newly built readers are missing.
                page = (root/'index.html').read_text()
                data = re.search(r'<script[^>]*id="library-route-data"[^>]*>(.*?)</script>', page, re.S)
                self.assertIsNotNone(data)
                route = json.loads(data[1])
                self.assertEqual(built, list(slugs))
                for slug in slugs:
                    self.assertEqual(route['books'][slug]['status'], 'available')
                    self.assertEqual(route['books'][slug]['href'], slug+'/index.html')
                    self.assertIn('href="'+slug+'/index.html"', page)
                self.assertEqual(route['order'][:3], [*slugs, 'linux'])
                return 420

            with patch.object(build_library, 'ROOT', root), \
                 patch.object(build_library, 'PUBLISHED', published), \
                 patch.object(build_library, 'refresh_legacy', return_value={}), \
                 patch.object(build_library.subprocess, 'run', side_effect=build_reader), \
                 patch.object(build_volume, 'ROOT', root), \
                 patch.object(build_volume, 'CONFIGS', configs), \
                 patch.object(library_catalog, 'refresh', side_effect=final_catalog):
                build_library.main()


if __name__ == '__main__':
    unittest.main()
