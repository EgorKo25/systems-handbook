#!/usr/bin/env python3
"""Reader-source contracts without building or claiming a live Sonar server."""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

VOLUME = Path(__file__).resolve().parents[1]
ROOT = VOLUME.parent


def load(path):
    spec = importlib.util.spec_from_file_location('sonar_'+path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG = load(VOLUME/'volume_config.py').CONFIG
REFERENCE = load(VOLUME/'sources/reference.py')
DIAGRAMS = load(VOLUME/'sources/diagrams.py').DIAGRAMS
ORDER = [key for _, keys in CONFIG['sections'] for key in keys]
SOURCES = {key: (VOLUME/'sources'/f'{key}.html').read_text() for key in ORDER if key != '99-glossary'}


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__(); self.links = []; self.feed(source)
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)


class SourcesTests(unittest.TestCase):
    def test_every_registered_chapter_has_one_reader_header(self):
        self.assertEqual(len(ORDER), len(set(ORDER)))
        self.assertEqual(set(SOURCES), {p.stem for p in (VOLUME/'sources').glob('*.html')})
        for key, source in SOURCES.items():
            with self.subTest(chapter=key):
                self.assertRegex(source, r'^<header><h1>.+?</h1><p>.+?</p></header>')
                self.assertEqual(source.count('<h1>'), 1)
                self.assertIn('<h2>', source)

    def test_final_reader_relative_links_have_files_and_existing_book_anchors(self):
        for chapter, source in SOURCES.items():
            for href in Links(source).links:
                uri = urlsplit(href)
                if uri.scheme or uri.netloc:
                    continue
                target = (VOLUME/unquote(uri.path)).resolve() if uri.path else VOLUME/'index.html'
                with self.subTest(chapter=chapter, href=href):
                    if target == VOLUME/'index.html':
                        self.assertTrue(uri.fragment in ORDER or uri.fragment.startswith('glossary-term-'))
                    else:
                        self.assertTrue(target.is_file(), str(target))
                        if uri.fragment and target.suffix == '.html':
                            self.assertRegex(target.read_text(), r'id=["\']'+re.escape(unquote(uri.fragment))+r'["\']')

    def test_diagram_steps_refer_to_real_actors_edges_and_insertion_points(self):
        self.assertGreaterEqual(len(DIAGRAMS), 3)
        self.assertEqual(len({d['id'] for d in DIAGRAMS}), len(DIAGRAMS))
        for diagram in DIAGRAMS:
            with self.subTest(diagram=diagram['id']):
                nodes = {node['id'] for node in diagram['nodes']}
                edges = {edge['id'] for edge in diagram['edges']}
                self.assertEqual(len(nodes), len(diagram['nodes']))
                self.assertEqual(len(edges), len(diagram['edges']))
                self.assertEqual(SOURCES[diagram['chapter']].count(diagram['insert_before']), 1)
                for edge in diagram['edges']:
                    self.assertIn(edge['from'], nodes); self.assertIn(edge['to'], nodes)
                for step in diagram['steps']:
                    self.assertTrue(set(step['focus']) <= nodes)
                    self.assertTrue(set(step['active']) <= edges)
                    self.assertEqual(set(step['states']), nodes)
                    self.assertTrue(step['fields'] and step['bands'])

    def test_glossary_is_substantial_unique_and_nonempty(self):
        terms = REFERENCE.GLOSSARY
        self.assertGreaterEqual(len(terms), 100)
        self.assertEqual(len(terms), len({term.casefold() for term, _ in terms}))
        for term, definition in terms:
            self.assertTrue(term.strip()); self.assertGreater(len(definition), 40)

    def test_native_card_has_the_actual_renderers_situation_schema(self):
        self.assertEqual([c['name'] for c in REFERENCE.COMMANDS], ['sonar-scanner'])
        for command in REFERENCE.COMMANDS:
            self.assertIn(command['chapter'], SOURCES)
            self.assertEqual(command['volume'], 'sonarqube')
            for flag in command['flags']:
                for field in ('flag', 'action', 'when', 'example', 'result'):
                    self.assertIsInstance(flag[field], str); self.assertTrue(flag[field])
            for situation in command['situations']:
                for field in ('problem', 'explanation', 'solution'):
                    self.assertIsInstance(situation[field], str); self.assertTrue(situation[field])


if __name__ == '__main__':
    unittest.main()
