"""Integrity of mission contracts, dependency order and real handbook links."""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent


class Ids(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.ids.update(value for key, value in attrs if key == "id")


class MissionMapTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((LAB / "chapter-map.json").read_text())
        self.stages = self.data["stages"]

    def test_complete_contracts_and_existing_assets(self):
        for stage in self.stages:
            with self.subTest(stage=stage["id"]):
                for key in ("ticket", "context", "access_constraints", "symptoms", "success_evidence", "rollback"):
                    self.assertGreater(len(stage["mission"][key]), 20)
                self.assertTrue(stage["resources"]["estimate_not_measured"])
                self.assertTrue(stage["implementation_status"])
                for item in stage["assets"]:
                    path = (LAB / item).resolve()
                    self.assertIn(REPO, path.parents)
                    self.assertTrue(path.exists(), item)

    def test_dependency_order_is_acyclic_and_complete(self):
        names = [item["id"] for item in self.stages]
        self.assertEqual(len(names), len(set(names)))
        ordered = self.data["recommended_order"]
        self.assertEqual(set(ordered), set(names))
        self.assertEqual(len(ordered), len(names))
        for stage in self.stages:
            for dependency in stage["depends_on"]:
                self.assertIn(dependency, names)
                self.assertLess(ordered.index(dependency), ordered.index(stage["id"]))

    def test_every_chapter_anchor_exists(self):
        cache = {}
        for stage in self.stages:
            for link in stage["chapters"]:
                with self.subTest(stage=stage["id"], href=link["href"]):
                    url = urlsplit(link["href"])
                    self.assertFalse(url.scheme)
                    path = (LAB / unquote(url.path)).resolve()
                    self.assertIn(REPO, path.parents)
                    self.assertTrue(path.is_file(), link["href"])
                    if path not in cache:
                        cache[path] = Ids(path.read_text()).ids
                    self.assertIn(unquote(url.fragment), cache[path], link["href"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
