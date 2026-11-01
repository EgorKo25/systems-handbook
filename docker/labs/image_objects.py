#!/usr/bin/env python3
"""Build and inspect two original OCI layers entirely in memory; no Docker API."""
import gzip
import hashlib
import io
import json
import tarfile


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()


def layer(entries, compression=9):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for path, data in entries:
            info = tarfile.TarInfo(path)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid = info.gid = 0
            archive.addfile(info, io.BytesIO(data))
    raw = stream.getvalue()
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='',
                       compresslevel=compression, mtime=0) as target:
        target.write(raw)
    return raw, compressed.getvalue()


def descriptor(data, media_type):
    return {'mediaType': media_type, 'digest': digest(data), 'size': len(data)}


def example():
    entries = [
        [('app/config.txt', b'A\n'), ('app/old.txt', b'B\n')],
        [('app/config.txt', b'C\n'), ('app/new.txt', b'D\n'),
         ('app/.wh.old.txt', b'')],
    ]
    layers = [layer(items) for items in entries]
    config = {
        'architecture': 'amd64', 'os': 'linux', 'config': {},
        'rootfs': {'type': 'layers', 'diff_ids': [digest(raw) for raw, _ in layers]},
    }
    config_data = json_bytes(config)
    manifest = {
        'schemaVersion': 2,
        'mediaType': 'application/vnd.oci.image.manifest.v1+json',
        'config': descriptor(config_data, 'application/vnd.oci.image.config.v1+json'),
        'layers': [descriptor(blob, 'application/vnd.oci.image.layer.v1.tar+gzip')
                   for _, blob in layers],
    }
    return entries, layers, config, config_data, manifest, json_bytes(manifest)


def apply_example(entries):
    """Model only the regular-file/whiteout cases in our fixed example."""
    visible = {}
    snapshots = []
    for changes in entries:
        # OCI whiteouts remove entries from lower layers, before the additions
        # of this layer. Tar entry order must not remove a same-layer addition.
        for path, _ in changes:
            parent, _, name = path.rpartition('/')
            if name.startswith('.wh.'):
                lower = '/'.join(part for part in (parent, name[4:]) if part)
                visible.pop(lower, None)
        for path, data in changes:
            if not path.rpartition('/')[2].startswith('.wh.'):
                visible[path] = data
        snapshots.append(dict(visible))
    return snapshots


def report():
    entries, layers, config, config_data, manifest, manifest_data = example()
    return {
        'scope': 'Original in-memory OCI files; no executable, registry or container',
        'config_bytes': config_data.decode(),
        'config': config,
        'manifest_bytes': manifest_data.decode(),
        'manifest': manifest,
        'manifest_digest': digest(manifest_data),
        'manifest_size': len(manifest_data),
        'layers': [dict(tar_size=len(raw), gzip_size=len(blob),
                        diff_id=digest(raw), blob_digest=digest(blob),
                        entries=[dict(path=p, size=len(data), content=data.decode())
                                 for p, data in changes])
                   for changes, (raw, blob) in zip(entries, layers)],
        'visible_after_each_layer': [
            {path: data.decode() for path, data in view.items()}
            for view in apply_example(entries)],
    }


if __name__ == '__main__':
    print(json.dumps(report(), ensure_ascii=False, indent=2))
