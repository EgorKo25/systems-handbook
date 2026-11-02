"""Offline SVG embedding keeps real artwork, fallbacks and a strict asset boundary."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts import svg_theme

REPO = Path(svg_theme.__file__).resolve().parents[1]


class SvgThemeTests(unittest.TestCase):
    def fixture(self, root, slugs=('cache', 'docker', 'computer-architecture')):
        pages = {}
        for slug in slugs:
            tags = []
            for src in svg_theme.ASSETS[slug]:
                target = root / slug / src
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((REPO / slug / src).read_bytes())
                tags.append(f'<img src="{src}" alt="Byte 43 &amp; named object" loading="lazy">')
            # The helper must not try to read/embed an unlisted image.
            tags.append('<img src="unlisted.svg" alt="Independent local fallback">')
            page = ('<!doctype html>\r\n<html><body>\r\n' + '\r\n'.join(tags)
                    + '\r\n</body></html>\r\n').encode()
            (root / slug / 'index.html').write_bytes(page)
            pages[slug] = page
        return pages

    def test_all_24_real_svg_templates_preserve_labels_values_and_geometry(self):
        self.assertEqual({slug: len(paths) for slug, paths in svg_theme.ASSETS.items()},
                         {'cache': 16, 'docker': 1, 'computer-architecture': 7})
        for slug, paths in svg_theme.ASSETS.items():
            for src in paths:
                with self.subTest(asset=f'{slug}/{src}'):
                    path = REPO / slug / src
                    raw = path.read_bytes()
                    rendered = svg_theme.template(raw.decode(), f'{slug}/{src}')
                    self.assertIsNone(svg_theme.HEX.search(rendered))
                    tokens = set(re.findall(r'__LIBRARY_SVG_([A-Za-z]+)__', rendered))
                    self.assertTrue(tokens)
                    self.assertLessEqual(tokens, set(svg_theme.COLOURS) | {'onAccent'})
                    before, after = list(ET.fromstring(raw).iter()), list(ET.fromstring(rendered).iter())
                    self.assertEqual(len(before), len(after))
                    for old, new in zip(before, after):
                        self.assertEqual(old.tag, new.tag)
                        self.assertEqual(old.tail, new.tail)
                        if old.tag.rsplit('}', 1)[-1] != 'style':
                            self.assertEqual(old.text, new.text)
                        self.assertEqual(set(old.attrib), set(new.attrib))
                        for name in old.attrib:
                            if name not in {'fill', 'stroke', 'style'}:
                                self.assertEqual(old.attrib[name], new.attrib[name])
                    self.assertEqual(path.read_bytes(), raw)
                    if slug == 'docker':
                        self.assertIn('.light{fill:__LIBRARY_SVG_onAccent__}', rendered)

    def test_embedded_json_escaping_local_fallbacks_and_repeat_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self.fixture(root)
            # A harmless SVG comment must not terminate its enclosing HTML script.
            sample = root / 'cache/assets/book-map.svg'
            sample.write_bytes(sample.read_bytes().replace(
                b'</svg>', b'<!-- literal </script> boundary --></svg>', 1))
            originals = {f'{slug}/{src}': (root / slug / src).read_bytes()
                         for slug, paths in svg_theme.ASSETS.items() for src in paths}
            self.assertEqual(svg_theme.apply_svg_themes(root, list(before)),
                             {'readers': 3, 'changed': 3, 'assets': 24})
            first = {}
            for slug in before:
                first[slug] = (root / slug / 'index.html').read_bytes()
                html = first[slug].decode()
                self.assertEqual(svg_theme.BLOCK.sub('', html).encode(), before[slug])
                match = re.search(r'<script type="application/json" id="library-svg-theme-data-v1">'
                                  r'(.*?)</script>', html, re.S)
                self.assertIsNotNone(match)
                self.assertNotIn('<', match[1])
                entries = json.loads(match[1])
                self.assertEqual(set(entries), set(svg_theme.ASSETS[slug]))
                self.assertNotIn('unlisted.svg', entries)
                for src, entry in entries.items():
                    original = originals[f'{slug}/{src}']
                    self.assertEqual(entry['sha256'], hashlib.sha256(original).hexdigest())
                    self.assertEqual(entry['svg'], svg_theme.template(original.decode(), f'{slug}/{src}'))
                    ET.fromstring(entry['svg'])
                    self.assertEqual((root / slug / src).read_bytes(), original)
                if slug == 'cache':
                    self.assertIn('<!-- literal </script> boundary -->', entries['assets/book-map.svg']['svg'])
            self.assertEqual(svg_theme.apply_svg_themes(root, list(before)),
                             {'readers': 3, 'changed': 0, 'assets': 24})
            for slug in first:
                self.assertEqual((root / slug / 'index.html').read_bytes(), first[slug])

    def test_rejects_active_external_and_unreviewed_svg_content(self):
        wrap = lambda body: '<svg xmlns="http://www.w3.org/2000/svg">' + body + '</svg>'
        cases = {
            'script': wrap('<script>alert(1)</script>'),
            'foreign object': wrap('<foreignObject/>'),
            'event handler': wrap('<rect onclick="alert(1)"/>'),
            'external href': wrap('<g href="file:///outside.svg"/>'),
            'external CSS': wrap('<style>@import "https://example.invalid/style.css";</style>'),
            'external paint': wrap('<rect fill="url(https://example.invalid/paint.svg)"/>'),
            'unreviewed colour': wrap('<rect fill="#123456"/>'),
            'doctype': '<!DOCTYPE svg SYSTEM "file:///outside.dtd">' + wrap(''),
            'entity': '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///outside">]>' + wrap(''),
        }
        for name, source in cases.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                svg_theme.template(source, 'cache/assets/book-map.svg')

    def test_missing_or_symlink_asset_is_rejected_without_changing_page(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            before = self.fixture(root, ('docker',))['docker']
            asset = root / 'docker/labs/elf09-cutaway.svg'
            external = Path(outside) / 'external.svg'
            external.write_bytes(asset.read_bytes())
            asset.unlink()
            with self.assertRaises(FileNotFoundError):
                svg_theme.apply_svg_themes(root, ['docker'])
            self.assertEqual((root / 'docker/index.html').read_bytes(), before)
            asset.symlink_to(external)
            with self.assertRaises(ValueError):
                svg_theme.apply_svg_themes(root, ['docker'])
            self.assertEqual((root / 'docker/index.html').read_bytes(), before)

    def test_invalid_later_reader_does_not_partially_write_earlier_readers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self.fixture(root)
            asset = root / 'computer-architecture/labs/illustrations/cmos-inverter-paths.svg'
            asset.write_bytes(asset.read_bytes().replace(b'#172b38', b'#123456'))
            with self.assertRaises(ValueError):
                svg_theme.apply_svg_themes(root, list(before))
            for slug, page in before.items():
                self.assertEqual((root / slug / 'index.html').read_bytes(), page)

    def test_unpublished_readers_are_not_read_or_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = self.fixture(root, ('docker',))['docker']
            # Even an absent allowlisted file is irrelevant to an unpublished reader.
            (root / 'docker/labs/elf09-cutaway.svg').unlink()
            self.assertEqual(svg_theme.apply_svg_themes(root, ['git']),
                             {'readers': 0, 'changed': 0, 'assets': 0})
            self.assertEqual((root / 'docker/index.html').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
