#!/usr/bin/env python3
"""Real Git and byte-level regression checks; all projects are temporary."""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import trainer as lab


class LaboratoryChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="handbook-git-check-")
        self.base = Path(self.temporary.name)
        self.workspace = lab.initialize(self.base / "workspace")
        self.repo = self.workspace / "repo"

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return lab.git(self.workspace, self.repo, *args)

    def reset(self, name):
        lab.reset_checkpoint(self.workspace, name)

    def build(self):
        lab.python(self.workspace, self.repo, "tools/build.py")
        return self.repo / "dist/handbook-demo.zip"

    def archive(self):
        return zipfile.ZipFile(self.repo / "dist/handbook-demo.zip")

    def link(self, target, link, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")

    def test_01_marker_and_children(self):
        _, data = lab.validate(self.workspace)
        self.assertEqual(set(data["children"]), set(lab.CHILDREN))
        self.assertEqual(len(data["id"]), 64)

    def test_02_local_identity(self):
        self.assertEqual(self.git("config", "--local", "user.email"), "student@example.invalid")

    def test_03_hooks_are_empty(self):
        self.assertEqual(list((self.workspace / ".trainer-hooks").iterdir()), [])
        self.assertEqual(self.git("config", "--local", "core.hooksPath"), "../.trainer-hooks")

    def test_04_bare_remote(self):
        self.assertEqual(lab.git(self.workspace, self.workspace / "remote.git", "rev-parse", "--is-bare-repository"), "true")

    def test_05_two_independent_worktrees(self):
        before = (self.workspace / "peer/app.py").read_bytes()
        (self.repo / "app.py").write_bytes(b"changed only here\n")
        self.assertEqual((self.workspace / "peer/app.py").read_bytes(), before)

    def test_06_nonempty_directory_rejected(self):
        path = self.base / "personal"
        path.mkdir()
        lab.write(path / "important.txt", "keep\n")
        with self.assertRaises(lab.LabError):
            lab.initialize(path)
        self.assertEqual((path / "important.txt").read_text(), "keep\n")

    def test_07_existing_stand_not_reinitialized(self):
        before = self.git("rev-parse", "HEAD")
        with self.assertRaises(lab.LabError):
            lab.initialize(self.workspace)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)

    def test_08_unknown_root_file_prevents_reset(self):
        lab.write(self.workspace / "personal.txt", "keep")
        before = (self.repo / "app.py").read_bytes()
        with self.assertRaises(lab.LabError):
            self.reset("start")
        self.assertEqual((self.repo / "app.py").read_bytes(), before)

    def test_09_missing_root_marker_prevents_reset(self):
        (self.workspace / lab.MARKER).unlink()
        with self.assertRaises(lab.LabError):
            self.reset("start")
        self.assertTrue((self.repo / "app.py").exists())

    def test_10_wrong_child_id_prevents_reset(self):
        lab.write(self.repo / lab.CHILD_MARKER, '{}')
        with self.assertRaises(lab.LabError):
            self.reset("start")
        self.assertTrue((self.workspace / "peer/app.py").exists())

    def test_11_root_symlink_rejected(self):
        link = self.base / "alias"
        self.link(self.workspace, link, True)
        with self.assertRaises(lab.LabError):
            lab.reset_checkpoint(link, "start")

    def test_12_ancestor_symlink_rejected(self):
        link = self.base / "alias"
        self.link(self.base, link, True)
        with self.assertRaises(lab.LabError):
            lab.initialize(link / "new-workspace")

    def test_13_nested_symlink_never_followed(self):
        outside = self.base / "outside"
        outside.mkdir()
        lab.write(outside / "keep.txt", "keep")
        self.link(outside, self.repo / "external", True)
        with self.assertRaises(lab.LabError):
            self.reset("start")
        self.assertEqual((outside / "keep.txt").read_text(), "keep")

    def test_14_marker_symlink_rejected(self):
        marker = self.workspace / lab.MARKER
        copy = self.base / "marker-copy.json"
        copy.write_bytes(marker.read_bytes())
        marker.unlink()
        self.link(copy, marker)
        with self.assertRaises(lab.LabError):
            self.reset("start")

    def test_15_hooks_file_prevents_reset(self):
        lab.write(self.workspace / ".trainer-hooks/pre-commit", "do not execute")
        with self.assertRaises(lab.LabError):
            self.reset("start")

    def test_16_reset_requires_explicit_yes(self):
        before = self.git("rev-parse", "HEAD")
        self.assertEqual(lab.main(["--workspace", str(self.workspace), "reset-checkpoint", "merge"]), 2)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)

    def test_17_inherited_git_directory_is_removed(self):
        outside = self.base / "not-a-repository"
        outside.mkdir()
        with patch.dict(os.environ, {"GIT_DIR": str(outside), "GIT_WORK_TREE": str(outside)}):
            self.assertEqual(self.git("branch", "--show-current"), "main")

    def test_18_personal_configuration_not_read_or_changed(self):
        config = self.base / "personal.gitconfig"
        body = b'[user]\n name = Wrong Identity\n email = wrong@example.invalid\n[core]\n autocrlf = true\n'
        config.write_bytes(body)
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}):
            path = lab.initialize(self.base / "another")
            self.assertEqual(lab.git(path, path / "repo", "config", "user.name"), "Handbook Student")
        self.assertEqual(config.read_bytes(), body)

    def test_19_index_three_different_versions(self):
        self.reset("index")
        self.assertTrue(lab.check(self.workspace, "index")["ok"])
        self.assertEqual(self.git("diff", "--name-only"), "notes.txt")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "notes.txt")

    def test_20_index_incorrect_result_rejected(self):
        with self.assertRaises(lab.LabError):
            lab.check(self.workspace, "index")

    def test_21_blob_hash_includes_type_length_and_zero(self):
        body = (self.repo / "notes.txt").read_bytes()
        expected = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        self.assertEqual(self.git("hash-object", "notes.txt"), expected)

    def test_22_adding_does_not_track_later_edits(self):
        lab.write(self.repo / "notes.txt", "prepared\n")
        self.git("add", "notes.txt")
        lab.write(self.repo / "notes.txt", "working\n")
        self.assertEqual(self.git("show", ":notes.txt"), "prepared")

    def test_23_restore_default_uses_index(self):
        self.reset("index")
        self.git("restore", "--worktree", "--", "notes.txt")
        self.assertEqual((self.repo / "notes.txt").read_text(), "prepared\n")

    def test_24_restore_staged_uses_head(self):
        self.reset("index")
        self.git("restore", "--staged", "--", "notes.txt")
        self.assertEqual(self.git("show", ":notes.txt"), "first")
        self.assertEqual((self.repo / "notes.txt").read_text(), "working\n")

    def test_25_branch_fast_forward(self):
        self.reset("branch")
        self.assertTrue(lab.check(self.workspace, "branch")["ok"])
        self.assertEqual(len(self.git("rev-list", "--parents", "-n", "1", "main").split()), 2)

    def test_26_conflict_has_three_index_stages(self):
        self.reset("merge")
        lab.git(self.workspace, self.repo, "merge", "feature-conflict", okay=(1,))
        stages = {line.split()[2] for line in self.git("ls-files", "--unmerged").splitlines()}
        self.assertEqual(stages, {"1", "2", "3"})
        self.assertIn("<<<<<<<", (self.repo / "message.txt").read_text())

    def test_27_resolved_merge_has_two_parents(self):
        self.reset("recovery")
        self.assertTrue(lab.check(self.workspace, "merge")["ok"])

    def test_28_reflog_preserves_detached_commit(self):
        self.git("switch", "--detach")
        lab.write(self.repo / "recovery.txt", "recovered\n")
        lab.commit(self.workspace, "Detached experiment")
        lost = self.git("rev-parse", "HEAD")
        self.git("switch", "main")
        self.assertIn(lost, self.git("reflog", "--format=%H"))
        self.git("branch", "rescued", lost)
        self.assertTrue(lab.check(self.workspace, "recovery")["ok"])

    def test_29_fetch_changes_ref_not_worktree(self):
        self.reset("remote")
        self.assertTrue(lab.check(self.workspace, "fetched")["ok"])

    def test_30_fast_forward_after_fetch(self):
        self.reset("remote")
        self.git("merge", "--ff-only", "origin/main")
        self.assertTrue(lab.check(self.workspace, "remote")["ok"])

    def test_31_service_tests_run_without_server(self):
        lab.python(self.workspace, self.repo, "-m", "unittest", "discover", "-s", "tests", "-v")
        self.assertEqual(lab.python(self.workspace, self.repo, "app.py").strip(), "Hello, reader!")

    def test_32_archive_contains_only_declared_inputs(self):
        self.build()
        with self.archive() as archive:
            self.assertEqual(archive.namelist(), ["README.txt", "app.py"])

    def test_33_archive_member_bytes(self):
        self.build()
        with self.archive() as archive:
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (self.repo / name).read_bytes())

    def test_34_archive_fixed_dates(self):
        self.build()
        with self.archive() as archive:
            self.assertEqual({i.date_time for i in archive.infolist()}, {(2000, 1, 1, 0, 0, 0)})

    def test_35_archive_modes_and_platform(self):
        self.build()
        with self.archive() as archive:
            for info in archive.infolist():
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.external_attr >> 16, stat.S_IFREG | 0o644)

    def test_36_archive_stored_compression(self):
        self.build()
        with self.archive() as archive:
            self.assertEqual({i.compress_type for i in archive.infolist()}, {zipfile.ZIP_STORED})

    def test_37_mtime_does_not_change_archive(self):
        archive = self.build()
        before = archive.read_bytes()
        os.utime(self.repo / "app.py", (1000000000, 1000000000))
        self.build()
        self.assertEqual(archive.read_bytes(), before)

    def test_38_content_change_changes_archive_and_dirty_flag(self):
        archive = self.build()
        before = archive.read_bytes()
        with (self.repo / "app.py").open("ab") as stream:
            stream.write(b"\n# A real input change.\n")
        self.build()
        self.assertNotEqual(archive.read_bytes(), before)
        self.assertTrue(lab.archive_check(self.repo)["provenance"]["tracked_and_untracked_dirty"])

    def test_39_empty_commit_changes_only_external_provenance(self):
        archive = self.build()
        before = archive.read_bytes()
        old_head = (self.repo / "dist/source-commit.txt").read_bytes()
        self.git("commit", "--allow-empty", "-m", "Metadata only")
        self.build()
        self.assertEqual(archive.read_bytes(), before)
        self.assertNotEqual((self.repo / "dist/source-commit.txt").read_bytes(), old_head)

    def test_40_manifest_hash_and_complete_build_check(self):
        self.build()
        self.assertTrue(lab.check(self.workspace, "build")["ok"])

    def test_41_stale_provenance_is_rejected(self):
        self.build()
        self.git("commit", "--allow-empty", "-m", "New HEAD")
        with self.assertRaises(lab.LabError):
            lab.check(self.workspace, "build")

    def test_42_two_clean_copies_reproduce_archive(self):
        self.assertTrue(lab.check(self.workspace, "reproducible")["ok"])

    def test_43_dirty_reproducibility_experiment_rejected(self):
        lab.write(self.repo / "notes.txt", "not committed\n")
        with self.assertRaises(lab.LabError):
            lab.check(self.workspace, "reproducible")

    def test_44_reset_removes_only_known_training_data(self):
        lab.write(self.repo / "disposable.txt", "training only")
        lab.write(self.base / "outside.txt", "keep")
        self.reset("start")
        self.assertFalse((self.repo / "disposable.txt").exists())
        self.assertEqual((self.base / "outside.txt").read_text(), "keep")

    def test_45_output_symlink_prevents_build(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.link(outside, self.repo / "dist", True)
        with self.assertRaises(lab.LabError):
            self.build()
        self.assertEqual(list(outside.iterdir()), [])

    def test_46_status_preserves_working_changes(self):
        lab.write(self.repo / "notes.txt", "keep my experiment\n")
        self.assertEqual(lab.main(["--workspace", str(self.workspace), "status"]), 0)
        self.assertEqual((self.repo / "notes.txt").read_text(), "keep my experiment\n")

    def test_47_unknown_checkpoint_cannot_delete(self):
        with self.assertRaises(lab.LabError):
            self.reset("not-a-checkpoint")
        self.assertTrue((self.repo / "app.py").exists())

    def test_48_entire_stateful_route_without_reset(self):
        original = self.git("rev-parse", "HEAD")
        lab.write(self.repo / "notes.txt", "prepared\n")
        self.git("add", "notes.txt")
        lab.write(self.repo / "notes.txt", "working\n")
        self.assertTrue(lab.check(self.workspace, "index")["ok"])
        self.git("restore", "--source=HEAD", "--staged", "--worktree", "--", "notes.txt")
        self.git("switch", "-c", "feature")
        lab.write(self.repo / "feature.txt", "feature ready\n")
        lab.commit(self.workspace, "Add a feature marker")
        self.git("switch", "main")
        self.git("merge", "--ff-only", "feature")
        self.assertTrue(lab.check(self.workspace, "branch")["ok"])
        self.git("switch", "-c", "feature-conflict")
        lab.write(self.repo / "message.txt", "Hello from feature\n")
        lab.commit(self.workspace, "Change feature")
        self.git("switch", "main")
        lab.write(self.repo / "message.txt", "Hello from main\n")
        lab.commit(self.workspace, "Change main")
        lab.git(self.workspace, self.repo, "merge", "feature-conflict", okay=(1,))
        lab.write(self.repo / "message.txt", "Hello from both branches\n")
        lab.commit(self.workspace, "Resolve conflict")
        self.assertTrue(lab.check(self.workspace, "merge")["ok"])
        self.git("switch", "--detach", "HEAD")
        lab.write(self.repo / "recovery.txt", "recovered\n")
        lab.commit(self.workspace, "Detached experiment")
        lost = self.git("rev-parse", "HEAD")
        self.git("switch", "main")
        self.git("branch", "rescued", lost)
        self.assertTrue(lab.check(self.workspace, "recovery")["ok"])
        self.git("push", "origin", "main")
        peer = self.workspace / "peer"
        lab.git(self.workspace, peer, "fetch", "origin")
        lab.git(self.workspace, peer, "merge", "--ff-only", "origin/main")
        lab.write(peer / "peer.txt", "from peer\n")
        lab.git(self.workspace, peer, "add", "peer.txt")
        lab.git(self.workspace, peer, "commit", "-m", "A peer contribution")
        lab.git(self.workspace, peer, "push", "origin", "main")
        self.git("fetch", "origin")
        self.assertTrue(lab.check(self.workspace, "fetched")["ok"])
        self.git("merge", "--ff-only", "origin/main")
        self.assertTrue(lab.check(self.workspace, "remote")["ok"])
        self.build()
        self.assertTrue(lab.check(self.workspace, "build")["ok"])
        self.assertTrue(lab.check(self.workspace, "reproducible")["ok"])
        self.assertNotEqual(self.git("rev-parse", "HEAD"), original)
        self.assertEqual(self.git("merge-base", "HEAD", original), original)

    def test_49_missing_template_cannot_destroy_existing_stand(self):
        before = (self.repo / "app.py").read_bytes()
        with patch.object(lab, "TEMPLATE", self.base / "missing-template"):
            with self.assertRaises(lab.LabError):
                self.reset("start")
        self.assertEqual((self.repo / "app.py").read_bytes(), before)

    def test_50_gitfile_redirect_prevents_reset(self):
        (self.repo / ".git").rename(self.repo / "saved-git")
        lab.write(self.repo / ".git", "gitdir: ../../outside\n")
        with self.assertRaises(lab.LabError):
            self.reset("start")
        self.assertTrue((self.repo / "saved-git/HEAD").exists())

    def test_51_external_object_store_prevents_reset(self):
        lab.write(self.repo / ".git/objects/info/alternates", str(self.base / "outside") + "\n")
        with self.assertRaises(lab.LabError):
            self.reset("start")

    def test_52_core_worktree_cannot_redirect_wrapper(self):
        outside = self.base / "outside"
        outside.mkdir()
        lab.write(outside / "notes.txt", "private contents\n")
        self.git("config", "--local", "core.worktree", str(outside))
        self.assertEqual(self.git("show", "HEAD:notes.txt"), "first")
        self.git("restore", "--worktree", "--", "notes.txt")
        self.assertEqual((outside / "notes.txt").read_text(), "private contents\n")


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LaboratoryChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"format": 1, "suite": "real-git-and-byte-laboratory",
              "git": lab.check_git(), "python": platform.python_version(),
              "platform": platform.system(), "windows_executed": platform.system() == "Windows",
              "tests": result.testsRun, "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              "failures": [test.id().split(".")[-1] for test, _ in result.failures],
              "errors": [test.id().split(".")[-1] for test, _ in result.errors],
              "skipped": [test.id().split(".")[-1] for test, _ in result.skipped],
              "ok": result.wasSuccessful()}
    lab.write(Path(__file__).with_name("lab-results.json"), json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
