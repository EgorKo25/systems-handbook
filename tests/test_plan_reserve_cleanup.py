import copy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.ops import plan_reserve_cleanup as cleanup


OLD = "a" * 40
MANIFEST = "b" * 64
HISTORICAL = "c" * 40


def tree(revision):
    return {
        "name": cleanup.reserve_name(revision),
        "revision": revision,
        "manifest": MANIFEST,
        "kind": "directory",
        "uid": 1000,
        "device": 10,
        "inode": 20,
        "ctime_ns": 30,
        "contains_mount": False,
        "verified": True,
        "reclaimable_bytes": 4096,
    }


def inventory():
    roles = {role: f"{i:040x}" for i, role in enumerate(
        ("active", "rollback", "blue", "green", "initial", "pinned"), 1
    )}
    return {
        "observed_at": 100,
        "owner_uid": 1000,
        "protected": roles,
        "generation": "d" * 64,
        "caddy": {"expected": "e" * 64, "observed": "e" * 64, "reserves": []},
        "loopback": {"revision": roles["active"], "manifest": MANIFEST},
        "active_manifest": MANIFEST,
        "receipts": {OLD: MANIFEST},
        "trees": [tree(OLD), tree(HISTORICAL)],
        "pending": False,
    }


class CleanupPlanTests(unittest.TestCase):
    def setUp(self):
        self.first = inventory()
        self.current = copy.deepcopy(self.first)
        self.current["observed_at"] += cleanup.MIN_AGE

    def test_retention_and_unowned_history(self):
        self.assertEqual(cleanup.plan(self.first)["candidates"], [])
        self.current["observed_at"] -= 1
        self.assertEqual(cleanup.plan(self.current, self.first)["candidates"], [])
        self.current["observed_at"] += 1
        report = cleanup.plan(self.current, self.first)
        self.assertEqual([item["revision"] for item in report["candidates"]], [OLD])
        self.assertEqual(report["candidates"][0]["reclaimable_bytes"], 4096)
        self.assertEqual(report["skipped"][cleanup.reserve_name(HISTORICAL)], "no exact ownership receipt")

    def test_all_protected_revisions_and_caddy_roots(self):
        for role in self.current["protected"]:
            with self.subTest(role=role):
                snapshot = copy.deepcopy(self.current)
                snapshot["protected"][role] = OLD
                if role == "active":
                    snapshot["loopback"]["revision"] = OLD
                self.assertEqual(cleanup.plan(snapshot, self.first)["skipped"][cleanup.reserve_name(OLD)],
                                 "protected")
        self.current["caddy"]["reserves"].append(cleanup.reserve_name(OLD))
        self.assertEqual(cleanup.plan(self.current, self.first)["skipped"][cleanup.reserve_name(OLD)],
                         "protected")

    def test_aborts_when_pending_caddy_or_loopback_disagrees(self):
        for field, value, expected in (
            ("pending", True, "pending cutover"),
            ("loopback", {"revision": OLD, "manifest": MANIFEST}, "loopback does not match active"),
            ("caddy", {"expected": "e" * 64, "observed": "f" * 64, "reserves": []}, "Caddy digest changed"),
        ):
            with self.subTest(field=field):
                snapshot = copy.deepcopy(self.current)
                snapshot[field] = value
                report = cleanup.plan(snapshot, self.first)
                self.assertEqual(report["blocked"], expected)
                self.assertEqual(report["candidates"], [])

    def test_changes_in_tree_identity_owner_or_mount(self):
        for changes in (
            {"inode": 200}, {"ctime_ns": 300}, {"device": 40}, {"uid": 1001},
            {"contains_mount": True}, {"kind": "symlink"}, {"verified": False},
            {"manifest": "f" * 64}, {"revision": HISTORICAL},
        ):
            with self.subTest(changes=changes):
                snapshot = copy.deepcopy(self.current)
                snapshot["trees"][0].update(changes)
                self.assertEqual(cleanup.plan(snapshot, self.first)["candidates"], [])

    def test_ambiguity_and_discontinuous_generation(self):
        self.current["receipts"]["a" * 39 + "f"] = MANIFEST
        self.assertEqual(cleanup.plan(self.current, self.first)["candidates"], [])
        del self.current["receipts"]["a" * 39 + "f"]
        self.current["trees"].append(tree(OLD))
        self.assertEqual(cleanup.plan(self.current, self.first)["candidates"], [])
        self.current["trees"].pop()
        self.current["generation"] = "a" * 64
        self.assertEqual(cleanup.plan(self.current, self.first)["candidates"], [])

    def test_fails_for_incomplete_or_reversed_inventory(self):
        self.current["observed_at"] = 99
        with self.assertRaisesRegex(ValueError, "out of order"):
            cleanup.plan(self.current, self.first)
        del self.current["protected"]["pinned"]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            cleanup.plan(self.current)

    def test_cli_does_not_change_its_inputs(self):
        with TemporaryDirectory() as work:
            old = Path(work) / "old.json"
            new = Path(work) / "new.json"
            old.write_text(json.dumps(self.first))
            new.write_text(json.dumps(self.current))
            command = [sys.executable, "-B", str(Path(cleanup.__file__)),
                       str(new), "--earlier", str(old)]
            result = subprocess.run(command, text=True, check=True, capture_output=True)
            self.assertEqual(json.loads(result.stdout)["candidates"][0]["revision"], OLD)
            self.assertEqual(json.loads(old.read_text()), self.first)
            self.assertEqual(json.loads(new.read_text()), self.current)
            new.write_text('{"protected": {}, "protected": {}}')
            result = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate JSON key", result.stderr)
