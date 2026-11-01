"""Verify the actual byte objects explained in Docker chapter 03."""
import gzip
import hashlib
import io
import json
import tarfile
import unittest
import image_objects as objects


class ImageObjectsTests(unittest.TestCase):
    def test_every_descriptor_checks_the_referenced_bytes(self):
        _, layers, _, config_data, manifest, manifest_data = objects.example()
        values = [(manifest['config'], config_data)]
        values += list(zip(manifest['layers'], [blob for _, blob in layers]))
        for descriptor, data in values:
            self.assertEqual(descriptor['size'], len(data))
            self.assertEqual(descriptor['digest'], 'sha256:' + hashlib.sha256(data).hexdigest())
        self.assertEqual(json.loads(manifest_data), manifest)

    def test_diff_ids_hash_the_uncompressed_tar(self):
        _, layers, config, *_ = objects.example()
        for (raw, blob), expected in zip(layers, config['rootfs']['diff_ids']):
            self.assertEqual(gzip.decompress(blob), raw)
            self.assertEqual(objects.digest(raw), expected)
            self.assertNotEqual(expected, objects.digest(blob))

    def test_different_compression_preserves_tar_and_diff_id(self):
        entries, *_ = objects.example()
        raw_a, blob_a = objects.layer(entries[0], compression=1)
        raw_b, blob_b = objects.layer(entries[0], compression=9)
        self.assertEqual(raw_a, raw_b)
        self.assertNotEqual(blob_a, blob_b)
        self.assertEqual(gzip.decompress(blob_a), gzip.decompress(blob_b))

    def test_whiteout_hides_lower_file_without_deleting_lower_bytes(self):
        entries, layers, *_ = objects.example()
        first, second = objects.apply_example(entries)
        self.assertEqual(first['app/old.txt'], b'B\n')
        self.assertNotIn('app/old.txt', second)
        self.assertEqual(second, {'app/config.txt': b'C\n', 'app/new.txt': b'D\n'})
        with tarfile.open(fileobj=io.BytesIO(layers[0][0])) as archive:
            self.assertEqual(archive.extractfile('app/old.txt').read(), b'B\n')

    def test_whiteout_precedes_same_layer_addition_regardless_of_order(self):
        entries = [[('app/old.txt', b'B')],
                   [('app/old.txt', b'new'), ('app/.wh.old.txt', b'')]]
        self.assertEqual(objects.apply_example(entries)[-1]['app/old.txt'], b'new')

    def test_config_changes_manifest_without_changing_layers(self):
        _, _, config, _, manifest, manifest_data = objects.example()
        config['config']['User'] = '65532:65532'
        changed = dict(manifest)
        changed['config'] = objects.descriptor(objects.json_bytes(config), manifest['config']['mediaType'])
        self.assertEqual(changed['layers'], manifest['layers'])
        self.assertNotEqual(objects.digest(objects.json_bytes(changed)), objects.digest(manifest_data))


if __name__ == '__main__':
    unittest.main()
