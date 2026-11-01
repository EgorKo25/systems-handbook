"""Publication remains an explicit permission, independent of authoring folders."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts import publication, prepare_site, library_catalog, volume_config


class PublicationTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'registry.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            return publication.read_registry(path)

    def test_build_catalog_export_and_configs_agree_on_public_books(self):
        self.assertEqual(prepare_site.BOOKS, set(publication.VOLUME_TITLES))
        self.assertEqual(library_catalog.VOLUMES, publication.VOLUME_TITLES)
        self.assertEqual(tuple(volume_config.CONFIGS), publication.MANAGED_VOLUMES)
        self.assertEqual(len(prepare_site.BOOKS), len(publication.PUBLISHED))

    def test_registry_rejects_ambiguous_duplicate_and_traversal_entries(self):
        row = dict(slug='book', title='Book', build='managed')
        invalid = [None, {}, {'format': True, 'volumes': [row]},
                   {'format': 1, 'volumes': []},
                   {'format': 1, 'volumes': [row, row]}]
        for changed in ({'slug': '../private'}, {'slug': '/private'}, {'title': ''},
                        {'build': 'discover'}, {'build': []}, {'extra': 'silent'}):
            invalid.append({'format': 1, 'volumes': [{**row, **changed}]})
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.read(data)

    def test_an_unlisted_authoring_tree_is_not_an_export_permission(self):
        self.assertFalse(prepare_site.is_reading_file('unreviewed/index.html'))
        self.assertFalse(prepare_site.is_reading_file('unreviewed/labs/key.txt'))
        self.assertTrue(prepare_site.is_reading_file('gitlab/index.html'))
        self.assertTrue(prepare_site.is_reading_file('published-volumes.json'))
        self.assertFalse(prepare_site.is_reading_file('gitlab/sources/chapter.html'))


if __name__ == '__main__':
    unittest.main()
