"""Validate the learner's whole route, not just the chapter renderer.

The real prepare() runs against a temporary source/world tree. No VM, Docker,
package installation, network connection or shared source rewrite is performed.
"""
from collections import Counter
import contextlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "practicum/sources"
LAB = REPO / "labs-personal"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normal(text):
    return " ".join(text.split())


class Document(HTMLParser):
    """Read real HTML semantics: sections, hidden hints, anchors and links."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.text = []
        self.details_text = []
        self.section_count = Counter()
        self.technology_count = 0
        self.parts = {key: [] for key in ("analysis", "hints", "debrief")}
        self.section_stack = []
        self.details_depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in ("a", "img"):
            value = attrs.get("href" if tag == "a" else "src")
            if value:
                self.links.append((value, self.getpos()[0]))
        if tag == "details":
            self.details_depth += 1
        if tag == "section":
            if "data-technology-start" in attrs:
                self.technology_count += 1
            markers = [key.removeprefix("data-mission-") for key in attrs
                       if key.startswith("data-mission-")]
            self.section_count.update(markers)
            inherited = self.section_stack[-1] if self.section_stack else None
            self.section_stack.append(markers[0] if len(markers) == 1 else inherited)

    def handle_endtag(self, tag):
        if tag == "details":
            self.details_depth -= 1
        if tag == "section" and self.section_stack:
            self.section_stack.pop()

    def handle_data(self, data):
        self.text.append(data)
        if self.details_depth:
            self.details_text.append(data)
        if self.section_stack and self.section_stack[-1] in self.parts:
            self.parts[self.section_stack[-1]].append(data)


class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curriculum = json.loads((LAB / "chapter-map.json").read_text(encoding="utf-8"))
        cls.stages = cls.curriculum["stages"]
        cls.by_id = {stage["id"]: stage for stage in cls.stages}
        cls.config = runpy.run_path(REPO / "practicum/volume_config.py")["CONFIG"]
        cls.technology = runpy.run_path(SOURCE / "technology_starts.py")
        cls.temporary = tempfile.TemporaryDirectory(prefix="practicum-curriculum-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.temp_root = Path(cls.temporary.name)
        cls.temp_source = cls.temp_root / "practicum/sources"
        shutil.copytree(SOURCE, cls.temp_source, ignore=shutil.ignore_patterns("__pycache__"))
        (cls.temp_root / "labs-personal").mkdir()
        shutil.copyfile(LAB / "chapter-map.json", cls.temp_root / "labs-personal/chapter-map.json")
        # chapter_label() reads actual built-volume metadata. Copy only those
        # pages, rather than mocking the title resolver or symlinking writable
        # shared files into the temporary tree.
        chapter_pages = {
            (REPO / "practicum" / unquote(urlsplit(link["href"]).path)).resolve()
            for stage in cls.stages for link in stage.get("chapters", [])
        }
        for page in chapter_pages:
            destination = cls.temp_root / page.relative_to(REPO)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(page, destination)

        # A pre-existing learner branch is present before chapter preparation.
        # It is deliberately not a real disk; no QEMU operation may touch it.
        cls.runtime = cls.temp_root / "labs-personal/runtime"
        (cls.runtime / "disks").mkdir(parents=True)
        cls.progress_disk = cls.runtime / "disks/my-existing-progress.qcow2"
        cls.progress_disk.write_bytes(b"learner mistake and saved data: preserve verbatim\n")
        config = json.loads((LAB / "vm/world.example.json").read_text())
        (cls.runtime / "world.json").write_text(json.dumps({
            "schema": 1, "world_id": "curriculum-test-existing-world", "config": config,
            "active_disk": "disks/my-existing-progress.qcow2", "state": "supplied-image"
        }), encoding="utf-8")
        cls.runtime_before = cls.tree_bytes(cls.runtime)
        builder = module_from(SOURCE / "prepare.py", "practicum.sources._prepare_under_test")
        with patch.object(builder, "ROOT", cls.temp_root), patch.object(builder, "SRC", cls.temp_source):
            builder.prepare()
        cls.rendered = {
            stage["id"]: (cls.temp_source / (stage["id"] + ".html")).read_text(encoding="utf-8")
            for stage in cls.stages
        }
        cls.anchor_cache = {}

    @staticmethod
    def tree_bytes(path):
        return {item.relative_to(path).as_posix(): item.read_bytes()
                for item in path.rglob("*") if item.is_file()}

    def test_every_numbered_mission_has_one_full_work_contract(self):
        self.assertEqual(self.curriculum["schema"], 1)
        names = [stage["id"] for stage in self.stages]
        self.assertEqual(len(names), len(set(names)), "Duplicate IDs overwrite another learner mission")
        numbers = []
        for stage in self.stages:
            with self.subTest(mission=stage["id"]):
                match = re.fullmatch(r"P(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*", stage["id"])
                self.assertIsNotNone(match)
                numbers.append(int(match.group(1)))
                self.assertTrue(stage["title"].strip())
                for key in ("ticket", "context", "access_constraints", "symptoms", "success_evidence", "rollback"):
                    self.assertIsInstance(stage["mission"][key], str)
                    self.assertGreater(len(stage["mission"][key].strip()), 20, key)
                resources = stage["resources"]
                estimate = resources["guest_memory_mib_estimate"]
                self.assertTrue(estimate is None or (type(estimate) is int and estimate >= 512))
                self.assertIs(resources["estimate_not_measured"], True)
        self.assertGreaterEqual(max(numbers), 22, "The current route must include all P00–P22 missions")
        self.assertEqual(sorted(numbers), list(range(max(numbers) + 1)), "A numbered mission disappeared")

    def assert_topological_order(self, order, label):
        self.assertEqual(len(order), len(set(order)), label + ": duplicated mission")
        self.assertEqual(set(order), set(self.by_id), label + ": missing or unknown mission")
        position = {name: number for number, name in enumerate(order)}
        for stage in self.stages:
            for dependency in stage["depends_on"]:
                with self.subTest(route=label, mission=stage["id"], prerequisite=dependency):
                    self.assertIn(dependency, self.by_id)
                    self.assertLess(position[dependency], position[stage["id"]],
                                    "The learner reaches a mission before its required world exists")

    def test_recommended_route_has_no_missing_or_future_prerequisites(self):
        self.assert_topological_order(self.curriculum["recommended_order"], "recommended_order")

    def test_actual_book_next_chapter_order_respects_dependencies(self):
        chapters = [name for _, section in self.config["sections"] for name in section]
        self.assertEqual(len(chapters), len(set(chapters)), "TOC repeats a chapter")
        order = [name for name in chapters if name.startswith("P")]
        self.assert_topological_order(order, "CONFIG/Next chapter")
        for name in ("00-route", "pc-work-method", "99-glossary"):
            self.assertIn(name, chapters)

    def test_mission_explanation_hints_and_solution_survive_real_preparation(self):
        for stage in self.stages:
            identifier = stage["id"]
            with self.subTest(mission=identifier):
                original = Document((SOURCE / "missions" / (identifier + ".html")).read_text())
                self.assertEqual(original.section_count, {"analysis": 1, "hints": 1, "debrief": 1},
                                 "A missing/duplicate block silently changes the exercise")
                rendered = Document(self.rendered[identifier])
                all_text = normal(" ".join(rendered.text))
                hidden_text = normal(" ".join(rendered.details_text))
                for key in ("analysis", "hints", "debrief"):
                    content = normal(" ".join(original.parts[key]))
                    self.assertGreater(len(content), 80, key + " is empty or only a placeholder")
                    self.assertTrue(content in all_text, key + " content was lost/truncated by prepare()")
                    if key != "analysis":
                        self.assertTrue(content in hidden_text, key + " should remain optional while investigating")

    def test_first_use_setup_is_present_before_the_investigation(self):
        starts = self.technology["TECHNOLOGY_STARTS"]
        stage_metadata = self.technology["STAGE_TECHNOLOGIES"]
        origin = {
            technology: identifier
            for identifier, row in stage_metadata.items()
            for technology in (*row["introduced"], *row.get("optional", ()))
        }
        self.assertEqual(set(starts), set(self.by_id), "A new mission lost its setup/continuation entry")
        self.assertGreaterEqual(len(self.technology["PASSPORT_FIELDS"]), 8,
                                "The common acquisition/configuration/recovery passport was shortened")
        with self.assertRaises(KeyError):
            self.technology["technology_start"]("P99-unknown-stage")
        for identifier, setup_html in starts.items():
            with self.subTest(mission=identifier):
                setup = Document(setup_html)
                rendered = Document(self.rendered[identifier])
                original = Document((SOURCE / "missions" / (identifier + ".html")).read_text())
                self.assertEqual(setup.technology_count, 1)
                self.assertEqual(rendered.technology_count, 1)
                setup_text = normal(" ".join(setup.text))
                analysis = normal(" ".join(original.parts["analysis"]))
                body = normal(" ".join(rendered.text))
                self.assertGreater(len(setup_text), 200, "Only a setup title remains")
                self.assertTrue(setup_text in body, "Setup disappeared from the delivered chapter")
                self.assertLess(body.index(setup_text), body.index(analysis),
                                "The learner reaches troubleshooting before acquiring/configuring the tool")
                metadata = stage_metadata[identifier]
                if metadata.get("introduced") or metadata.get("optional"):
                    # A component such as pg_dump may come from the already
                    # chosen PostgreSQL distribution. Requiring a second
                    # download here would contradict instance continuity.
                    provenance_links = list(setup.links)
                    for continued in metadata["continues"]:
                        if continued in origin:
                            provenance_links.extend(Document(starts[origin[continued]]).links)
                    self.assertTrue(any(urlsplit(href).scheme == "https" for href, _ in provenance_links),
                                    "Acquisition needs a source here or in its explicitly continued distribution")

    def test_the_same_technology_is_introduced_once_then_continued(self):
        metadata = self.technology["STAGE_TECHNOLOGIES"]
        self.assertEqual(set(metadata), set(self.by_id))
        # These are learner-created contracts, not downloadable programs. They
        # arise from the named missions and can subsequently be carried forward.
        contract_origins = {
            "P03-packet-path": ("address-plan",),
            "P06-service-socket": ("service-config",),
            "P13-observability": ("measurement-contract",),
        }
        known = {}
        order = [name for _, group in self.config["sections"] for name in group if name.startswith("P")]
        for identifier in order:
            row = metadata[identifier]
            with self.subTest(mission=identifier):
                for technology in row["continues"]:
                    self.assertIn(technology, known,
                                  "A continued instance/contract has no preceding setup in the actual route")
                for technology in (*row["introduced"], *row.get("optional", ())):
                    self.assertNotIn(technology, known,
                                     "A later stage silently reintroduces an existing instance")
                    known[technology] = identifier
                for contract in contract_origins.get(identifier, ()):
                    known[contract] = identifier

    def test_checkpoint_names_fit_the_actual_vm_and_are_not_reused(self):
        world = module_from(LAB / "vm/world.py", "practicum_world_checkpoint_contract")
        names = []
        for stage in self.stages:
            for key in ("before", "after"):
                value = stage["checkpoints"][key]
                with self.subTest(mission=stage["id"], checkpoint=key):
                    self.assertIsNotNone(world.NAME.fullmatch(value), "The launcher cannot save this checkpoint name")
                    self.assertIn(value, self.rendered[stage["id"]])
                names.append(value)
        self.assertEqual(len(names), len(set(names)), "Two stages overwrite/confuse the same checkpoint")

    def test_prepared_recipes_are_not_reported_as_boot_tested_runtime(self):
        safety = self.curriculum["safety"]
        self.assertIs(safety["instructor_rescue_console"], True)
        self.assertIs(safety["network_access_rules_not_all_enforced_yet"], True)
        self.assertIs(safety["secrets_or_progress_in_git"], False)
        checks = json.loads((LAB / "checks.json").read_text())
        self.assertEqual(checks["status"], "preparation-prototype")
        self.assertTrue(any("boot" in value.lower() for value in checks["not_tested"]))
        self.assertIs(checks["installed_or_downloaded_programs"], False)
        self.assertIs(checks["work_network_changed"], False)
        for stage in self.stages:
            with self.subTest(mission=stage["id"]):
                self.assertTrue(stage["implementation_status"].strip())
                body = normal(" ".join(Document(self.rendered[stage["id"]]).text)).lower()
                self.assertRegex(body, r"не подтвержд[её]н|не проверен|не испытан|ещ[её] предстоит",
                                 "A preparation-only mission needs a visible runtime limitation")
                self.assertNotRegex(body, r"\bnone\s+миб", "Unknown resource budget was printed as a number")

    def assert_public_local_link(self, href, source):
        url = urlsplit(href)
        self.assertIn(url.scheme, ("", "https", "http"), source + ": nonportable/executable URL")
        if url.scheme or url.netloc:
            return
        if not url.path:
            self.assertIn(unquote(url.fragment), {
                name for _, section in self.config["sections"] for name in section
            }, source + ": unresolved chapter jump")
            return
        target = (REPO / "practicum" / unquote(url.path)).resolve()
        self.assertIn(REPO, target.parents, source + ": link escapes the public repository")
        self.assertFalse({".git", "private", "runtime", "exports", "saves"} & set(target.relative_to(REPO).parts),
                         source + ": link exposes personal state")
        self.assertTrue(target.exists(), source + ": missing target " + href)
        if target.is_dir():
            self.assertTrue((target / "index.html").is_file(),
                            source + ": directory is not a working Pages URL; link to a real file: " + href)
            target = target / "index.html"
        if url.fragment:
            self.assertEqual(target.suffix, ".html", source + ": fragment on a non-HTML asset")
            if target not in self.anchor_cache:
                self.anchor_cache[target] = Document(target.read_text(encoding="utf-8")).ids
            self.assertIn(unquote(url.fragment), self.anchor_cache[target], source + ": missing anchor " + href)

    def test_rendered_chapter_and_asset_links_resolve_without_private_state(self):
        for stage in self.stages:
            identifier = stage["id"]
            for href, line in Document(self.rendered[identifier]).links:
                with self.subTest(mission=identifier, href=href):
                    self.assert_public_local_link(href, identifier + ":" + str(line))
            for asset in stage.get("assets", []):
                with self.subTest(mission=identifier, asset=asset):
                    self.assertFalse(urlsplit(asset).scheme)
                    self.assertFalse(Path(asset).is_absolute())
                    self.assert_public_local_link("../labs-personal/" + asset, identifier + " asset")

    def test_preparing_next_missions_and_previewing_vm_preserve_existing_progress(self):
        self.assertEqual(self.tree_bytes(self.runtime), self.runtime_before,
                         "Preparing the next chapter reset or changed the learner's world")
        world = module_from(LAB / "vm/world.py", "practicum_world_continuity_contract")
        for mode in ("serial", "window"):
            with self.subTest(console=mode):
                with contextlib.redirect_stdout(io.StringIO()) as result:
                    code = world.main(["--root", str(self.runtime), "start", "--dry-run",
                                       "--accel", "tcg", "--console", mode])
                self.assertEqual(code, 0)
                command = json.loads(result.getvalue())["argv"]
                self.assertNotIn("-snapshot", command, "Temporary writes would lose the learner's changes")
                self.assertNotIn("-virtfs", command, "The guest must not receive an implicit host folder")
                drive = command[command.index("-drive") + 1]
                self.assertIn("my-existing-progress.qcow2", drive)
                network = command[command.index("-netdev") + 1]
                self.assertIn("hostfwd=tcp:127.0.0.1:", network)
                self.assertIn("restrict=on", network)
                self.assertEqual(self.tree_bytes(self.runtime), self.runtime_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
