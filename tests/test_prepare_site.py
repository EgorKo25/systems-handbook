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
        self.write("gitlab/index.html", "<h1>GitLab</h1>")
        self.write("gitlab/build.py", "GitLab builder")
        self.write("gitlab/sources/01.html", "GitLab authoring")
        self.write("gitlab/labs/service/.gitlab-ci.yml", "stages: [test]\n")
        self.write("networks/sources/01.html", "Network authoring")
        self.write("labs-personal/README.md", "Personal lab recipes")
        self.write("labs-personal/vm/world.py", "print('lab controller')")
        self.write("labs-personal/runtime/world.json", "personal progress")
        self.write("labs-personal/assets/base.qcow2", "large disk")
        self.write("labs-personal/private/ssh.key", "private credential")
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
        for name in ["git/index.html", "git/labs/trainer.py", "git/labs/template/.gitignore", "git/labs/template/tools/build.py", "go/labs/service/.gitignore", "go/labs/service/go.mod", "gitlab/index.html", "gitlab/labs/service/.gitlab-ci.yml", "labs-personal/README.md", "labs-personal/vm/world.py"]:
            self.assertTrue((output / name).is_file(), name)
        for name in ["git/build.py", "git/sources/01.html", "go/build.py", "go/sources/01.html", "jenkins/build.py", "jenkins/sources/01.html", "gitlab/build.py", "gitlab/sources/01.html", "networks/sources/01.html", "labs-personal/runtime/world.json", "labs-personal/assets/base.qcow2", "labs-personal/private/ssh.key"]:
            self.assertFalse((output / name).exists(), name)
        lines = (output / "SHA256SUMS").read_text().splitlines()
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_even_tracked_personal_world_state_and_runtime_bundles_stay_private(self):
        # Synthetic fixtures only: no personal keys or actual VM files are read.
        # Force tracking so the test exercises the export boundary, not merely
        # the independent protection against untracked files.
        private = [
            'labs-personal/runtime/world.json',
            'labs-personal/runtime/known_hosts',
            # A Windows-created directory can retain this spelling in Git even
            # though the launcher addresses the same directory as "runtime".
            'labs-personal/Runtime/world.json',
            'labs-personal/progress/history.json',
            'labs-personal/state/current.json',
            'labs-personal/private/assets.json',
            'labs-personal/cache/session.json',
            'labs-personal/snapshots/day-one/world.json',
            'labs-personal/assets/ubuntu.iso',
            'labs-personal/images/base.qcow2',
            'labs-personal/images/local-checksums.txt',
            'labs-personal/keys/id_ed25519',
            'labs-personal/KEYS/id_ed25519',
            'labs-personal/tools/linux/qemu-system-x86_64',
            'labs-personal/tools/windows/firmware/README.txt',
            'labs-personal/tools/python/python312.zip',
            'labs-personal/saves/monday/world.json',
            'labs-personal/saves/session-notes.html',
            'labs-personal/vm/guest/runtime/serial.log',
            'labs-personal/vm/progress/notes.md',
            'labs-personal/vm/keys/bootstrap-identity',
            'labs-personal/packet-tracer/saves/current.pkt',
            'labs-personal/vm/system.QCOW2',
            'labs-personal/vm/install.ISO',
            'labs-personal/vm/private.PEM',
            'labs-personal/vm/private.KEY',
        ]
        for name in private:
            self.write(name, 'synthetic private fixture; never a real key or disk\n')
        subprocess.run(['git', '-C', str(self.source), 'add', '-f', '--', *private], check=True)
        tracked = set(subprocess.check_output(['git', '-C', str(self.source), 'ls-files'], text=True).splitlines())
        self.assertTrue(set(private) <= tracked)
        output = self.root / 'privacy-site'
        MODULE.export_site(self.source, output, 'a' * 40)
        exported = {path.relative_to(output).as_posix() for path in output.rglob('*') if path.is_file()}
        for name in private:
            with self.subTest(private_path=name):
                self.assertFalse(name in exported, name)
                self.assertNotIn('  ' + name + '\n', (output / 'SHA256SUMS').read_text())

    def test_container_recipes_keep_authored_ignore_files_without_runtime_dotfiles(self):
        public = {
            'docker/labs/echo/.dockerignore': '.git\n.env\nsecrets\n',
            'sonarqube/labs/.gitignore': 'images.env\n.env\nreports/\n',
        }
        private = ['docker/labs/echo/.env', 'sonarqube/labs/.env']
        for name, data in public.items():
            self.write(name, data)
        for name in private:
            self.write(name, 'SYNTHETIC_TEST_VALUE=private\n')
        subprocess.run(['git', '-C', str(self.source), 'add', '-f', '--',
                        *public, *private], check=True)
        output = self.root / 'container-site'
        MODULE.export_site(self.source, output, 'a' * 40)
        for name, data in public.items():
            self.assertEqual((output / name).read_text(), data)
        for name in private:
            self.assertFalse((output / name).exists(), name)

    def test_authored_vm_recipes_and_practicum_helpers_keep_their_exact_bytes(self):
        public = {
            'labs-personal/index.html': '<h1>Personal lab instructions</h1>\n',
            'labs-personal/chapter-map.json': '{"schema": 1, "stages": []}\n',
            'labs-personal/assets.example.json': '{"schema": 1, "status": "template-missing-assets"}\n',
            'labs-personal/vm/world.example.json': '{"schema": 1, "network_default": "isolated"}\n',
            'labs-personal/vm/world.docker.example.json': '{"schema": 1, "docker": "planned"}\n',
            'labs-personal/vm/start.sh': '#!/bin/sh\npython3 world.py "$@"\n',
            'labs-personal/vm/Start-Lab.ps1': 'python world.py @args\n',
            'labs-personal/vm/guest/bootstrap.sh': '#!/bin/sh\n# Authored guest preparation\n',
            'labs-personal/vm/guest/netlab.sh': '#!/bin/sh\n# Authored namespace exercise\n',
            'labs-personal/packet-tracer/configs/R1-base.cfg': 'hostname STUDY-R1\n',
            'practicum/index.html': '<h1>Practice</h1>\n',
            'practicum/labs/observe.py': '# Authored HTTP measurement helper\n',
            'practicum/labs/verify_go_release.py': '# Authored release verifier\n',
        }
        authoring = {
            'practicum/build.py': '# Authoring-only builder\n',
            'practicum/sources/00-route.html': '<h1>Maintained source fragment</h1>\n',
            'practicum/labs/__pycache__/observe.cpython-312.pyc': 'synthetic compiled cache\n',
        }
        for name, data in {**public, **authoring}.items():
            self.write(name, data)
        subprocess.run(['git', '-C', str(self.source), 'add', '-f', '--', *public, *authoring], check=True)
        self.write('practicum/labs/untracked-personal-notes.txt', 'must remain local\n')
        output = self.root / 'practice-site'
        MODULE.export_site(self.source, output, 'a' * 40)
        for name, data in public.items():
            with self.subTest(public_path=name):
                self.assertTrue((output / name).is_file())
                self.assertEqual((output / name).read_bytes(), data.encode('utf-8'))
        for name in [*authoring, 'practicum/labs/untracked-personal-notes.txt']:
            self.assertFalse((output / name).exists(), name)

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
