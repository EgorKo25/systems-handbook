"""Publishing must not copy untracked local data or authoring metadata."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("prepare_site", Path(__file__).resolve().parents[1] / "scripts/prepare_site.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "repo"
        self.source.mkdir()
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        self.write("index.html", "<h1>Public book</h1>")
        self.write("cache/index.html", "<h1>Cache</h1>")
        self.write("cache/labs/example.py", "print('teaching example')")
        self.write("cache/sources/00.html", "authoring fragment")
        self.write("cache/sources/eviction.js", "module.exports = {}")
        self.write("git/index.html", "<h1>Git</h1>")
        self.write("git/build.py", "authoring builder")
        self.write("git/sources/01.html", "authoring fragment")
        self.write("go/sources/01.html", "Go authoring")
        self.write("jenkins/sources/01.html", "Jenkins authoring")
        self.write("go/build.py", "Go builder")
        self.write("jenkins/build.py", "Jenkins builder")
        self.write("git/labs/trainer.py", "print('trainer')")
        self.write("git/labs/template/.gitignore", "dist/\n")
        self.write("go/labs/service/.gitignore", "dist/\n")
        self.write("go/labs/service/go.mod", "module example.org/handbook-service\n")
        self.write("git/labs/template/tools/build.py", "print('build')")
        self.write("guide/textbook/index.html", "public supplement")
        self.write(".github/workflows/pages.yml", "authoring")
        self.write("guide/index.html", "private deployment instructions")
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        self.write("cache/labs/private-untracked.txt", "must remain local")

    def write(self, name, data):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def test_export_keeps_reading_and_labs_without_private_or_authoring_files(self):
        output = self.root / "site"
        MODULE.export_site(self.source, output, "a" * 40)
        self.assertTrue((output / "cache/labs/example.py").is_file())
        self.assertTrue((output / "cache/sources/eviction.js").is_file())
        self.assertTrue((output / "guide/textbook/index.html").is_file())
        for name in [".git", ".github", "guide/index.html", "cache/sources/00.html", "cache/labs/private-untracked.txt"]:
            self.assertFalse((output / name).exists(), name)
        for name in ["git/index.html", "git/labs/trainer.py", "git/labs/template/.gitignore", "git/labs/template/tools/build.py", "go/labs/service/.gitignore", "go/labs/service/go.mod"]:
            self.assertTrue((output / name).is_file(), name)
        for name in ["git/build.py", "git/sources/01.html", "go/build.py", "go/sources/01.html", "jenkins/build.py", "jenkins/sources/01.html"]:
            self.assertFalse((output / name).exists(), name)
        lines = (output / "SHA256SUMS").read_text().splitlines()
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_refuses_output_over_repository_or_unrelated_directory(self):
        with self.assertRaises(ValueError):
            MODULE.export_site(self.source, self.source, "a" * 40, replace=True)
        output = self.root / "important"
        output.mkdir()
        (output / "my-data.txt").write_text("keep")
        with self.assertRaises(ValueError):
            MODULE.export_site(self.source, output, "a" * 40, replace=True)
        self.assertEqual((output / "my-data.txt").read_text(), "keep")

    def test_refuses_tracked_symlink_to_external_data(self):
        outside = self.root / "outside.txt"
        outside.write_text("keep outside")
        (self.source / "cache/labs/link.txt").symlink_to(outside)
        subprocess.run(["git", "-C", str(self.source), "add", "cache/labs/link.txt"], check=True)
        with self.assertRaises(ValueError):
            MODULE.export_site(self.source, self.root / "site", "a" * 40)

    def test_replace_does_not_follow_output_or_parent_symlink(self):
        outside = self.root / "outside"
        MODULE.export_site(self.source, outside, "a" * 40)
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        for output in [alias, alias / "nested"]:
            with self.assertRaises(ValueError):
                MODULE.export_site(self.source, output, "b" * 40, replace=True)
        self.assertTrue((outside / "index.html").is_file())

    def test_replace_requires_valid_marker_and_unchanged_manifest(self):
        output = self.root / "site"
        output.mkdir()
        (output / "site-version.json").write_text("not even valid JSON")
        (output / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            MODULE.export_site(self.source, output, "b" * 40, replace=True)
        self.assertEqual((output / "keep.txt").read_text(), "keep")
        clean = self.root / "clean"
        MODULE.export_site(self.source, clean, "a" * 40)
        MODULE.export_site(self.source, clean, "b" * 40, replace=True)
        (clean / "my-notes.txt").write_text("preserve my notes")
        with self.assertRaises(ValueError):
            MODULE.export_site(self.source, clean, "c" * 40, replace=True)
        self.assertEqual((clean / "my-notes.txt").read_text(), "preserve my notes")


if __name__ == "__main__":
    unittest.main()
