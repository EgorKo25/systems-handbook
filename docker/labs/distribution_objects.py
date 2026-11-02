#!/usr/bin/env python3
"""Original in-memory OCI graph, extending chapter03's exact layer bytes.

No registry, socket, executable, Docker API, extraction or writes. --demo prints
our own JSON objects; --check exercises their descriptor/hash relationships.
This is a deliberately small format model, not a general OCI validator.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import re
import sys
import tarfile
import unittest
import zlib

SPEC = importlib.util.spec_from_file_location(
    'chapter03_image_objects', Path(__file__).with_name('image_objects.py'))
objects = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(objects)
INDEX = 'application/vnd.oci.image.index.v1+json'
MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
CONFIG = 'application/vnd.oci.image.config.v1+json'
LAYER = 'application/vnd.oci.image.layer.v1.tar+gzip'


def build_graph(config_label=None):
    entries, layers, config, _, _, _ = objects.example()
    blobs = {}
    def keep(data, media_type):
        desc = objects.descriptor(data, media_type)
        blobs[desc['digest']] = data
        return desc
    layer_desc = [keep(blob, LAYER) for _, blob in layers]
    variants = []
    configs = []
    manifests = []
    for arch in ('amd64', 'arm64'):
        conf = copy.deepcopy(config)
        conf['architecture'] = arch
        if config_label is not None:
            conf['config']['Labels'] = {'study.change': config_label}
        conf_data = objects.json_bytes(conf)
        conf_desc = keep(conf_data, CONFIG)
        manifest = {'schemaVersion': 2, 'mediaType': MANIFEST,
                    'config': conf_desc, 'layers': copy.deepcopy(layer_desc)}
        manifest_data = objects.json_bytes(manifest)
        desc = keep(manifest_data, MANIFEST)
        desc['platform'] = {'architecture': arch, 'os': 'linux'}
        variants.append(desc)
        configs.append(conf_data)
        manifests.append(manifest_data)
    index = {'schemaVersion': 2, 'mediaType': INDEX, 'manifests': variants}
    index_data = objects.json_bytes(index)
    root = keep(index_data, INDEX)
    return {'root': root, 'blobs': blobs, 'index': index_data,
            'configs': configs, 'manifests': manifests, 'layers': layers,
            'entries': entries}


def resolve(desc, blobs, media_type):
    """The three mandatory descriptor fields, then exact referenced bytes."""
    if desc.get('mediaType') != media_type:
        raise ValueError('unsupported mediaType for this model role')
    size = desc.get('size')
    if type(size) is not int or size < 0:
        raise ValueError('size must be a nonnegative integer')
    digest = desc.get('digest')
    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('only lowercase sha256 digest is supported by this model')
    if digest not in blobs:
        raise ValueError('referenced blob missing')
    raw = blobs[digest]
    if len(raw) != size:
        raise ValueError('descriptor size differs from referenced bytes')
    if objects.digest(raw) != digest:
        raise ValueError('descriptor digest differs from referenced bytes')
    return raw


def verify(graph):
    """Check this bounded two-platform/gzip example; no trust decision."""
    index = json.loads(resolve(graph['root'], graph['blobs'], INDEX))
    if index.get('schemaVersion') != 2 or index.get('mediaType') != INDEX:
        raise ValueError('invalid model index')
    seen = set()
    for desc in index['manifests']:
        manifest = json.loads(resolve(desc, graph['blobs'], MANIFEST))
        if manifest.get('schemaVersion') != 2 or manifest.get('mediaType') != MANIFEST:
            raise ValueError('invalid model manifest')
        conf = json.loads(resolve(manifest['config'], graph['blobs'], CONFIG))
        platform = desc['platform']
        if any(platform[k] != conf[k] for k in ('os', 'architecture')):
            raise ValueError('platform disagrees with referenced config')
        key = (platform['os'], platform['architecture'])
        if key in seen:
            raise ValueError('duplicate model platform')
        seen.add(key)
        layer_desc = manifest['layers']
        if len(layer_desc) != len(conf['rootfs']['diff_ids']):
            raise ValueError('layer/diffID count differs')
        for layer, diff_id in zip(layer_desc, conf['rootfs']['diff_ids']):
            compressed = resolve(layer, graph['blobs'], LAYER)
            uncompressed = gzip.decompress(compressed)
            if objects.digest(uncompressed) != diff_id:
                raise ValueError('uncompressed tar differs from diffID')
    return seen


def report():
    graph = build_graph()
    platforms = sorted('/'.join(k) for k in verify(graph))
    return {
        'scope': 'Original chapter03 non-executable files in RAM; no registry or Docker image.',
        'serializer': 'UTF-8, separators comma/colon, insertion order; not a universal canonical JSON rule.',
        'runtime': {'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION},
        'index_descriptor': graph['root'], 'index_bytes': graph['index'].decode(),
        'platforms': platforms,
        'variants': [{'config_bytes': c.decode(), 'config_digest': objects.digest(c),
                      'manifest_bytes': m.decode(), 'manifest_digest': objects.digest(m),
                      'manifest_size': len(m)}
                     for c, m in zip(graph['configs'], graph['manifests'])],
        'layers': [{'tar_size': len(raw), 'blob_size': len(blob),
                    'tar_diff_id': objects.digest(raw), 'compressed_blob_digest': objects.digest(blob),
                    'first_16_blob_bytes_hex': blob[:16].hex(' '),
                    'compressed_blob_hex': blob.hex(' ')}
                   for raw, blob in graph['layers']],
        'same_semantic_manifest_different_bytes': objects.digest(
            json.dumps(json.loads(graph['manifests'][0]), indent=2).encode()),
        'rewritten_graph_integrity_passes': sorted('/'.join(k) for k in verify(build_graph('changed by a different author'))),
    }


class GraphChecks(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph()

    def test_both_platforms_and_every_exact_descriptor(self):
        self.assertEqual(verify(self.graph), {('linux', 'amd64'), ('linux', 'arm64')})
        self.assertEqual(len(self.graph['blobs']), 7)

    def test_json_whitespace_changes_digest_but_not_parsed_object(self):
        raw = self.graph['manifests'][0]
        pretty = json.dumps(json.loads(raw), indent=2).encode()
        self.assertEqual(json.loads(raw), json.loads(pretty))
        self.assertNotEqual(objects.digest(raw), objects.digest(pretty))

    def test_tampered_bytes_are_rejected_even_at_same_length(self):
        key = self.graph['root']['digest']
        raw = bytearray(self.graph['blobs'][key]); raw[-2] ^= 1
        self.graph['blobs'][key] = bytes(raw)
        with self.assertRaisesRegex(ValueError, 'digest'):
            verify(self.graph)

    def test_wrong_size_type_or_missing_blob_are_rejected(self):
        for value in (True, -1, '1', self.graph['root']['size']+1):
            desc = dict(self.graph['root'], size=value)
            with self.assertRaisesRegex(ValueError, 'size'):
                resolve(desc, self.graph['blobs'], INDEX)
        with self.assertRaisesRegex(ValueError, 'missing'):
            resolve(self.graph['root'], {}, INDEX)

    def test_type_and_platform_are_checked_not_just_hash(self):
        with self.assertRaisesRegex(ValueError, 'mediaType'):
            resolve(self.graph['root'], self.graph['blobs'], MANIFEST)
        idx = json.loads(self.graph['index'])
        idx['manifests'][0]['platform']['architecture'] = 'arm64'
        raw = objects.json_bytes(idx)
        self.graph['root'] = objects.descriptor(raw, INDEX)
        self.graph['blobs'][objects.digest(raw)] = raw
        with self.assertRaisesRegex(ValueError, 'platform'):
            verify(self.graph)

    def test_compressed_blob_and_uncompressed_diff_id_differ(self):
        raw, blob = self.graph['layers'][0]
        self.assertEqual(gzip.decompress(blob), raw)
        self.assertNotEqual(objects.digest(raw), objects.digest(blob))
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            self.assertEqual(archive.extractfile('app/config.txt').read(), b'A\n')

    def test_whole_replacement_passes_integrity_but_has_new_root(self):
        changed = build_graph('different author')
        self.assertEqual(verify(self.graph), verify(changed))
        self.assertNotEqual(self.graph['root'], changed['root'])
        self.assertEqual(self.graph['layers'], changed['layers'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--demo', action='store_true', help='print exact objects and digests, writes nothing')
    group.add_argument('--check', action='store_true', help='run seven pure model groups, no Docker/network')
    args = parser.parse_args()
    if args.check:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(GraphChecks)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if args.demo:
        print(json.dumps(report(), ensure_ascii=False, indent=2)); return 0
    parser.print_help(); return 0


if __name__ == '__main__':
    raise SystemExit(main())
