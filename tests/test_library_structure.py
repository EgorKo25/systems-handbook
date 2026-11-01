"""The learning route must survive partial builds without inventing ready books."""
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_volume
from scripts import library_structure as structure


PUBLICATION = dict(networks='I', linux='II', bash='III', postgres='IV', cache='V',
                   git='VI', go='VII', jenkins='VIII', gitlab='IX', practicum='X')
NEW_TECHNOLOGIES = {'docker', 'sonarqube', 'nexus', 'artifactory', 'terraform',
                    'ansible', 'flyway', 'mongodb', 's3', 'minio', 'ceph', 'vault',
                    'kubernetes', 'helm', 'argocd', 'prometheus', 'grafana'}


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.cards, self.links = [], [], []
        self.route, self._route = '', False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs['href'])
            if attrs.get('class') == 'volume':
                self.cards.append(attrs['href'])
        if tag == 'script' and attrs.get('id') == 'library-route-data':
            self._route = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self._route = False

    def handle_data(self, data):
        if self._route:
            self.route += data


TEMPLATE = '''<!doctype html><html><head><title>Library</title>
<style id="library-card-interaction-style">main .volume::before{opacity:0}</style>
<style id="library-phone-style">.home-masthead{display:flex}</style>
<script id="library-preferences-bootstrap-v1">const themeKeys=['paper','night','white','black','sepia','graphite','midnight','forest'];</script>
</head><body><main><div class="home-masthead"><div class="eyebrow">Библиотека</div><button id="home-theme-toggle">Тема</button></div>
<h1>Library</h1><p class="lead">Old lead with ten names</p>
<div class="grid"><a class="volume" href="networks/index.html"><div class="tag">Том I</div>old</a></div><section class="notes"><h2>Existing notes</h2><p>Keep this text.</p></section>
<section class="notes" id="sketches"><h2>Diagrams</h2><details data-docker-map><summary>Old unbuilt Docker</summary></details></section><section class="notes" style="margin-top:22px"><h2>Как читать и проверять</h2><a href="ПЛАН-РАЗВИТИЯ.txt">План десяти новых томов</a></section>
</main></body></html>'''


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stats = {}
        self.configs = {}
        for slug, number in PUBLICATION.items():
            (self.root/slug).mkdir()
            (self.root/slug/'index.html').write_text('<html>built reading book</html>', encoding='utf-8')
            self.stats[slug] = dict(slug=slug, title=slug, volume=number, chapters=21, words=12345, terms=42)
            if slug not in structure.BASE_SLUGS:
                self.configs[slug] = dict(volume=number, short=structure.BOOKS[slug]['title'],
                                          blurb='A real built book', diagram_modules=[])

    def route(self):
        return structure.reading_map(self.root, self.stats, self.configs)

    def test_all_technology_directions_have_one_home_without_duplicate_fundamentals(self):
        route = self.route()
        ordered = [slug for group in route['groups'] for slug in group['volumes']]
        self.assertEqual(set(ordered), set(PUBLICATION) | NEW_TECHNOLOGIES)
        self.assertEqual(len(ordered), len(set(ordered)))
        self.assertEqual(ordered, route['order'])
        self.assertEqual([book['id'] for book in route['deferred']], ['sql-depth'])
        self.assertEqual(route['deferred'][0]['status'], 'deferred')

    def test_mechanisms_precede_tools_and_ci_platforms_remain_alternative_paths(self):
        order = {slug: index for index, slug in enumerate(self.route()['order'])}
        for slug, book in self.route()['books'].items():
            for prerequisite in book['prerequisites']:
                self.assertLess(order[prerequisite], order[slug], (slug, prerequisite))
        self.assertIn('docker', structure.BOOKS['kubernetes']['prerequisites'])
        self.assertIn('kubernetes', structure.BOOKS['helm']['prerequisites'])
        self.assertIn('helm', structure.BOOKS['argocd']['prerequisites'])
        self.assertIn('postgres', structure.BOOKS['flyway']['prerequisites'])
        self.assertIn('s3', structure.BOOKS['minio']['prerequisites'])
        self.assertIn('prometheus', structure.BOOKS['grafana']['prerequisites'])
        self.assertNotIn('jenkins', structure.BOOKS['gitlab']['prerequisites'])
        self.assertNotIn('terraform', structure.BOOKS['ansible']['prerequisites'])
        self.assertEqual(structure.BOOKS['practicum']['prerequisites'], ('linux', 'bash'))

    def test_published_numbers_and_urls_do_not_become_learning_sequence_numbers(self):
        books = self.route()['books']
        for slug, number in PUBLICATION.items():
            self.assertEqual(books[slug]['publication_volume'], number)
            self.assertEqual(books[slug]['href'], slug+'/index.html')
        self.assertEqual(self.route()['order'][0], 'linux')
        self.assertEqual(books['linux']['publication_volume'], 'II')

    def test_empty_missing_unregistered_and_boolean_stats_cannot_publish_a_card(self):
        self.configs['docker'] = dict(volume='XI', short='Docker', blurb='Docker', diagram_modules=[])
        self.stats['docker'] = dict(slug='docker', volume='XI', chapters=0, words=0, terms=0)
        (self.root/'docker').mkdir()
        (self.root/'docker/index.html').write_text('placeholder')
        self.assertIsNone(self.route()['books']['docker']['href'])
        self.stats['docker'].update(chapters=18, words=50000)
        self.assertEqual(self.route()['books']['docker']['status'], 'available')
        self.stats['docker']['chapters'] = True
        self.assertEqual(self.route()['books']['docker']['status'], 'authoring')
        self.stats['docker']['chapters'] = 18
        del self.configs['docker']
        self.assertEqual(self.route()['books']['docker']['status'], 'authoring')
        (self.root/'linux/index.html').unlink()
        self.assertEqual(self.route()['books']['linux']['status'], 'unavailable')
        self.assertIsNone(self.route()['books']['linux']['href'])

    def test_registration_without_build_does_not_hide_already_available_books(self):
        self.configs['docker'] = dict(volume='XI', short='Docker', blurb='In progress', diagram_modules=[])
        self.assertEqual(sum(book['status'] == 'available' for book in self.route()['books'].values()), 10)
        self.assertEqual(self.route()['books']['docker']['status'], 'authoring')

    def test_unmapped_new_technology_and_publication_number_conflict_are_actionable(self):
        with patch.dict(self.configs, alien=dict(volume='L')):
            with self.assertRaisesRegex(ValueError, 'library_structure.py: alien'):
                self.route()
        self.configs['git']['volume'] = 'I'
        with self.assertRaisesRegex(ValueError, 'Publication number.*git'):
            self.route()

    def test_embedded_route_and_visible_cards_agree_and_all_group_links_resolve(self):
        document = Page(structure.render_shelves(self.route()))
        public = json.loads(document.route)
        self.assertEqual(set(document.cards), {slug+'/index.html' for slug in PUBLICATION})
        self.assertEqual(len(document.ids), len(set(document.ids)))
        for href in document.links:
            if href.startswith('#'):
                self.assertIn(href[1:], document.ids)
            else:
                self.assertTrue((self.root/href).is_file(), href)
        for slug, book in public['books'].items():
            self.assertEqual(book['href'] is not None, book['status'] == 'available', slug)
        source = json.dumps(public, ensure_ascii=False)
        self.assertNotIn('practicum.yandex', source)
        self.assertNotIn('work/library', source)
        self.assertNotIn('external-fork', source)

    def test_html_and_json_metadata_are_escaped(self):
        self.configs['go'].update(short='Go <script>bad</script>', blurb='a & b <img src=x>')
        rendered = structure.render_shelves(self.route())
        self.assertNotIn('<script>bad', rendered)
        self.assertNotIn('<img src=x>', rendered)
        self.assertIn('Go &lt;script&gt;bad&lt;/script&gt;', rendered)
        self.assertIn('Go <script>bad</script>', json.loads(Page(rendered).route)['books']['go']['title'])

    def test_home_preserves_masthead_theme_and_notes_and_is_idempotent(self):
        self.configs['docker'] = dict(volume='XI', short='Docker', blurb='In progress', diagram_modules=[])
        (self.root/'index.html').write_text(TEMPLATE, encoding='utf-8')
        (self.root/'library-stats.json').write_text(json.dumps(list(self.stats.values())), encoding='utf-8')
        with patch.object(build_volume, 'ROOT', self.root), patch.object(build_volume, 'CONFIGS', self.configs):
            build_volume.home()
            first = (self.root/'index.html').read_text(encoding='utf-8')
            build_volume.home()
            second = (self.root/'index.html').read_text(encoding='utf-8')
        self.assertEqual(first, second)
        self.assertEqual(first.count('id="library-structure-style"'), 1)
        self.assertEqual(first.count('id="library-route-data"'), 1)
        self.assertEqual(first.count('id="home-theme-toggle"'), 1)
        self.assertIn('<div class="home-masthead">', first)
        self.assertIn('id="library-card-interaction-style"', first)
        self.assertIn("['paper','night','white','black','sepia','graphite','midnight','forest']", first)
        self.assertIn('Keep this text.', first)
        self.assertNotIn('data-docker-map', first)
        self.assertNotIn('Old lead with ten names', first)
        self.assertNotIn('План десяти новых томов', first)
        self.assertEqual(len(Page(first).cards), 10)

    def test_home_rejects_missing_shelf_without_overwriting_the_page(self):
        (self.root/'index.html').write_text('<html><head></head><body>Unrelated content</body></html>')
        (self.root/'library-stats.json').write_text(json.dumps(list(self.stats.values())))
        original = (self.root/'index.html').read_bytes()
        with patch.object(build_volume, 'ROOT', self.root), patch.object(build_volume, 'CONFIGS', self.configs):
            with self.assertRaisesRegex(ValueError, 'preserve the existing page'):
                build_volume.home()
        self.assertEqual((self.root/'index.html').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
