"""Regression fixtures for failures invisible in a root-only link smoke test."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_site.py"
spec = importlib.util.spec_from_file_location("check_site", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class CheckSiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def put(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def errors(self):
        checker = module.SiteChecker(self.root)
        checker.check()
        return "\n".join(checker.errors)

    def test_query_encoded_fragment_and_directory_index(self):
        self.put("index.html", '<a href="chapter/?mode=read#%D1%81%D0%B5%D1%82%D1%8C">Read</a>')
        self.put("chapter/index.html", '<h1 id="сеть">Сеть</h1><a href="../index.html">Back</a><pre>/home/alice/data and http://localhost are examples</pre>')
        self.assertEqual(self.errors(), "")
        self.put("chapter/index.html", '<h1 id="other">Wrong chapter</h1>')
        self.assertIn("missing anchor 'сеть'", self.errors())

    def test_project_absolute_and_machine_urls_fail_but_source_link_is_ok(self):
        self.put("index.html", '<a href="/linux/index.html">Broken under project base</a><a href="file:///home/alice/book.html">Private</a><a href="http://localhost:8766/">Dev server</a><a href="https://www.postgresql.org/docs/">Source</a>')
        errors = self.errors()
        self.assertIn("absolute path", errors)
        self.assertEqual(errors.count("machine-specific URL"), 2)
        self.assertNotIn("postgresql.org", errors)

    def test_dynamic_command_glossary_and_search_targets(self):
        commands = [{"name": "ip", "purpose": "Explain", "syntax": "ip", "volume": "missing", "chapter": "network", "flags": []}, {"name": "ps", "purpose": "Processes", "syntax": "ps", "volume": "linux", "chapter": "removed-chapter", "flags": []}]
        terms = [{"term": "Socket", "definition": "Endpoint", "volume": "linux", "anchor": "gone"}]
        self.put("linux/index.html", '<h1 id="chapter">Linux</h1>' + ''.join('<script type="application/json" id="'+key+'">'+json.dumps(value)+'</script>' for key, value in {"book-data": [{"id": "chapter"}], "glossary-data": [], "command-reference-data": [], "library-glossary-data": [], "flag-comparison-data": []}.items()))
        self.put("index.html", '<script type="application/json" id="command-reference-data">'+json.dumps(commands)+'</script><script type="application/json" id="library-glossary-data">'+json.dumps(terms)+'</script><script>window.BOOK_SEARCH=[{"url":"index.html#missing"}];</script>')
        errors = self.errors()
        self.assertIn("unknown volume 'missing'", errors)
        self.assertIn("missing target linux/index.html#removed-chapter", errors)
        self.assertIn("missing target linux/index.html#gone", errors)
        self.assertIn("BOOK_SEARCH: missing anchor 'missing'", errors)

    def test_duplicate_ids_bad_json_external_css_and_runtime_network(self):
        self.put("index.html", '<h1 id="same">A</h1><h2 id="same">B</h2><script type="application/json">{broken}</script><link rel="stylesheet" href="style.css"><script>fetch("data.json")</script>')
        self.put("style.css", '@import "https://example.net/font.css"; body{background:url(missing.png)}')
        errors = self.errors()
        for expected in ("duplicate HTML ID", "invalid embedded JSON", "external active resource", "missing local file", "runtime network API"):
            self.assertIn(expected, errors)


if __name__ == "__main__":
    unittest.main()
