#!/usr/bin/env python3
"""Own TEMP USTAR/file checks. Image payloads are models, never Docker/OCI tests."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('counter_backup_bundle', HERE / 'bundle.py')
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)


class BundleChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='counter-backup-own-')
        self.root = Path(self.temp.name) / 'gen.ABC123'
        self.root.mkdir(mode=0o700)
        values = {'app-image.tar': b'own fake image payload, NOT OCI',
                  'tools-image.tar': b'own fake tool payload, NOT OCI',
                  'image.id': ('sha256:' + 'a' * 64 + '\n').encode(),
                  'tools.id': ('sha256:' + 'b' * 64 + '\n').encode(),
                  'container.id': ('c' * 64 + '\n').encode(),
                  'platform.txt': b'linux/amd64\n', 'version.expected': b'lesson1\n',
                  'counter.expected': b'42\n', 'stopped.at': b'2026-11-02T12:00:00Z\n',
                  'runtime.txt': b'Own synthetic fixture, no Engine\n'}
        for name, value in values.items():
            (self.root / name).write_bytes(value)
        self.archive()

    def tearDown(self):
        self.temp.cleanup()  # Only the fixture created by this test.

    def member(self, name, content=b'', kind=tarfile.REGTYPE):
        item = tarfile.TarInfo(name)
        item.type = kind
        item.uid = item.gid = 10001
        item.mode = 0o700 if kind == tarfile.DIRTYPE else 0o600
        item.mtime = 1700000000
        item.size = len(content) if kind == tarfile.REGTYPE else 0
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            item.linkname = '/outside-must-not-be-created'
        return item, content

    def archive(self, extras=(), counter=b'42\n', mutate=None):
        entries = [self.member('.', kind=tarfile.DIRTYPE), self.member('./counter', counter), *extras]
        if mutate:
            mutate(entries)
        with tarfile.open(self.root / 'counter.tar', 'w', format=tarfile.USTAR_FORMAT) as archive:
            for item, content in entries:
                archive.addfile(item, io.BytesIO(content) if item.isfile() else None)

    def seal(self):
        result = B.seal(self.root)
        return result, B.digest(self.root / 'manifest.json')

    def test_valid_seal_verify_and_no_overwrite(self):
        result, expected = self.seal()
        self.assertEqual(result['counter'], '42')
        self.assertEqual(result['archive'], {'counter': '42', 'members': 2, 'expanded_bytes': 3})
        self.assertEqual((self.root / 'counter.tar').stat().st_size, 10240)
        self.assertEqual(B.verify(self.root, expected), result)
        old = (self.root / 'manifest.json').read_bytes()
        with self.assertRaises(ValueError):
            B.seal(self.root)
        self.assertEqual((self.root / 'manifest.json').read_bytes(), old)

    def test_seal_syncs_generation_and_its_new_parent_entry(self):
        import os
        synced_directories = []
        actual_sync = os.fsync
        def observe(descriptor):
            info = os.fstat(descriptor)
            import stat
            if stat.S_ISDIR(info.st_mode):
                synced_directories.append((info.st_dev, info.st_ino))
            return actual_sync(descriptor)
        with patch.object(B.os, 'fsync', side_effect=observe):
            self.seal()
        for directory in (self.root, self.root.parent):
            info = directory.stat()
            self.assertIn((info.st_dev, info.st_ino), synced_directories)

    def test_second_copy_different_folder_verifies_and_original_retained(self):
        result, expected = self.seal()
        copy = Path(self.temp.name) / 'renamed-copy'
        shutil.copytree(self.root, copy)
        self.assertEqual(B.verify(copy, expected), result)
        self.assertEqual((self.root / 'counter.expected').read_bytes(), b'42\n')

    def test_tampered_image_bytes_detected(self):
        _, expected = self.seal()
        (self.root / 'app-image.tar').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            B.verify(self.root, expected)

    def test_separate_manifest_hash_required(self):
        self.seal()
        with self.assertRaises(ValueError):
            B.verify(self.root, '0' * 64)

    def test_unchanged_header_does_not_protect_counter_payload(self):
        path = self.root / 'counter.tar'
        raw = path.read_bytes()
        damaged = bytearray(raw)
        damaged[1024] = ord('5')  # Directory+file headers still unchanged.
        path.write_bytes(damaged)
        self.assertEqual(path.read_bytes()[:1024], raw[:1024])
        with self.assertRaises(ValueError):
            B.check_archive(path, 42)

    def test_traversal_absolute_symlink_hardlink_device_and_duplicate_rejected(self):
        bad = [self.member('../outside', b'x'), self.member('/absolute', b'x'),
               self.member('link', kind=tarfile.SYMTYPE), self.member('link', kind=tarfile.LNKTYPE),
               self.member('device', kind=tarfile.CHRTYPE), self.member('./counter', b'43\n')]
        for member in bad:
            with self.subTest(member=member[0].name, type=member[0].type):
                self.archive([member])
                with self.assertRaises(ValueError):
                    B.check_archive(self.root / 'counter.tar', 42)
        self.assertFalse((Path(self.temp.name) / 'outside').exists())

    def test_owner_and_permissions_must_match(self):
        for field, value in [('uid', 0), ('gid', 0), ('mode', 0o644), ('mode', 0o4600)]:
            with self.subTest(field=field, value=value):
                self.archive(mutate=lambda entries: setattr(entries[1][0], field, value))
                with self.assertRaises(ValueError):
                    B.check_archive(self.root / 'counter.tar', 42)

    def test_partial_generation_never_sealed(self):
        (self.root / 'counter.tar.partial').write_bytes(b'own partial')
        with self.assertRaises(ValueError):
            self.seal()
        self.assertFalse((self.root / 'manifest.json').exists())

    def test_corrupt_future_and_boolean_manifest_retained(self):
        self.seal()
        path = self.root / 'manifest.json'
        original = json.loads(path.read_text())
        for raw in [b'{broken', json.dumps(dict(original, version=2)).encode(),
                    json.dumps(dict(original, version=True)).encode()]:
            with self.subTest(raw=raw[:30]):
                path.write_bytes(raw)
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    B.verify(self.root, B.digest(path))
                self.assertEqual(path.read_bytes(), raw)

    def test_duplicate_json_keys_rejected(self):
        self.seal()
        path = self.root / 'manifest.json'
        path.write_text('{"version":1,"version":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            B.verify(self.root, B.digest(path))

    def test_metadata_symlink_refused_without_following(self):
        original = self.root / 'image.id'
        outside = Path(self.temp.name) / 'outside-id'
        outside.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.seal()
        self.assertEqual(outside.read_bytes(), ('sha256:' + 'a' * 64 + '\n').encode())

    def test_uint64_limit_and_bad_formats(self):
        maximum = (1 << 64) - 1
        self.assertEqual(B.counter_value((str(maximum) + '\n').encode()), maximum)
        for value in [b'', b'42', b'042\n', b'-1\n', b'42\nunknown', (str(maximum + 1) + '\n').encode()]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                B.counter_value(value)

    def test_temporary_file_is_retained_but_not_committed_counter(self):
        self.archive([self.member('./.counter-123', b'43\n')])
        result = B.check_archive(self.root / 'counter.tar', 42)
        self.assertEqual(result, {'counter': '42', 'members': 3, 'expanded_bytes': 6})

    def test_sync_failure_does_not_publish_manifest(self):
        before = {name: (self.root / name).read_bytes() for name in B.FILES}
        with patch.object(B.os, 'fsync', side_effect=OSError('own sync refusal')):
            with self.assertRaises(OSError):
                self.seal()
        self.assertFalse((self.root / 'manifest.json').exists())
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in B.FILES})

    def test_member_and_size_budgets_rejected(self):
        self.archive([self.member('./.counter-' + str(i), b'x') for i in range(127)])
        with self.assertRaises(ValueError):
            B.check_archive(self.root / 'counter.tar', 42)
        self.archive([self.member('./.counter-1', b'x' * 4097)])
        with self.assertRaises(ValueError):
            B.check_archive(self.root / 'counter.tar', 42)


if __name__ == '__main__':
    unittest.main(verbosity=2)
