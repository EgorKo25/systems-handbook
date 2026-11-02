#!/usr/bin/env python3
"""Seal/check the book's tiny counter backup. No Docker, network or extraction.

This is deliberately not a verifier for arbitrary application archives. It
accepts only the regular counter/temporary files and metadata explained in14.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

FILES = ('counter.tar', 'app-image.tar', 'tools-image.tar', 'image.id',
         'tools.id', 'platform.txt', 'version.expected', 'counter.expected',
         'stopped.at', 'runtime.txt', 'container.id')
MAX_UINT64 = (1 << 64) - 1
MAX_ARCHIVE_BYTES = 16 << 20
MAX_EXPANDED_BYTES = 1 << 20
MAX_MEMBERS = 128
HEX = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'Not a regular file: ' + path.name)


def digest(path):
    regular(path)
    result = hashlib.sha256()
    with path.open('rb') as source:
        while data := source.read(1 << 20):
            result.update(data)
    return result.hexdigest()


def text(root, name, limit=4096):
    path = root / name
    regular(path)
    require(path.stat().st_size <= limit, 'Metadata too large: ' + name)
    return path.read_text(encoding='utf-8')


def counter_value(data):
    require(re.fullmatch(rb'(?:0|[1-9][0-9]{0,19})\n', data) is not None,
            'Counter must be canonical unsigned decimal plus newline')
    value = int(data)
    require(value <= MAX_UINT64, 'Counter exceeds uint64')
    return value


def check_archive(path, expected):
    regular(path)
    require(path.stat().st_size <= MAX_ARCHIVE_BYTES,
            'Archive exceeds the counter-lab16MiB limit')
    seen = set()
    expanded = 0
    actual = None
    with tarfile.open(path, mode='r:') as archive:
        for member in archive:
            require(len(seen) < MAX_MEMBERS, 'Too many counter-lab archive members')
            raw = member.name
            name = str(PurePosixPath(raw))
            require(not raw.startswith('/') and '..' not in PurePosixPath(raw).parts,
                    'Unsafe archive name: ' + raw)
            require(raw in ('.', './') or raw in (name, './' + name),
                    'Noncanonical archive path: ' + raw)
            require(name not in seen, 'Duplicate archive name: ' + name)
            seen.add(name)
            require(not member.pax_headers, 'PAX extensions are outside this USTAR example')
            require(member.uid == 10001 and member.gid == 10001,
                    'Unexpected archive UID/GID: ' + raw)
            require(member.mode & 0o7000 == 0, 'Special mode bits: ' + raw)
            if name == '.':
                require(member.isdir() and member.mode == 0o700,
                        'Root directory must be UID10001 mode0700')
                continue
            require(member.isfile(), 'Only regular counter files are accepted: ' + raw)
            require(name == 'counter' or re.fullmatch(r'\.counter-[0-9]+', name),
                    'Unexpected counter-lab archive path: ' + raw)
            require(member.mode == 0o600, 'Counter file mode must be0600: ' + raw)
            require(0 <= member.size <= 4096, 'Oversized counter-lab file: ' + raw)
            expanded += member.size
            require(expanded <= MAX_EXPANDED_BYTES, 'Expanded counter-lab limit exceeded')
            if name == 'counter':
                file = archive.extractfile(member)  # Read bytes; NEVER extract to a path.
                require(file is not None, 'Cannot read counter member')
                with file:
                    actual = counter_value(file.read(64))
        require('.' in seen and actual is not None, 'Missing root directory/counter member')
    require(actual == expected, 'Archive counter differs from stopped checkpoint')
    return {'counter': str(actual), 'members': len(seen), 'expanded_bytes': expanded}


def describe(root, generation):
    require(re.fullmatch(r'gen\.[A-Za-z0-9]{6}', generation) is not None,
            'Generation must have the mktemp gen.XXXXXX form')
    require(not any(p.name.endswith('.partial') for p in root.iterdir()),
            'Incomplete .partial file retained; generation cannot be sealed/verified')
    expected = counter_value(text(root, 'counter.expected').encode('ascii'))
    image = text(root, 'image.id').rstrip('\n')
    tools = text(root, 'tools.id').rstrip('\n')
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', image) is not None, 'Invalid image ID')
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', tools) is not None, 'Invalid tools ID')
    platform = text(root, 'platform.txt').rstrip('\n')
    require(re.fullmatch(r'linux/[a-z0-9_]+(?:/[a-zA-Z0-9]+)?', platform) is not None,
            'Invalid Linux platform')
    version = text(root, 'version.expected', 1024)
    require(version.endswith('\n') and '\x00' not in version and len(version.splitlines()) == 1,
            'Expected one nonempty version line')
    require(bool(version.strip()), 'Empty application version')
    stopped = text(root, 'stopped.at').strip()
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', stopped) is not None,
            'Invalid stopped UTC timestamp')
    datetime.datetime.fromisoformat(stopped.replace('Z', '+00:00'))
    require(bool(text(root, 'runtime.txt', 16384).strip()), 'Empty runtime description')
    container = text(root, 'container.id').rstrip('\n')
    require(HEX.fullmatch(container), 'Invalid source container ID')
    archive = check_archive(root / 'counter.tar', expected)
    files = {}
    for name in FILES:
        path = root / name
        regular(path)
        files[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return {'version': 1, 'generation': generation, 'stopped_at_utc': stopped,
            'source_volume': 'study-data', 'source_container_id': container, 'counter': str(expected),
            'image_id': image, 'tools_id': tools, 'platform': platform,
            'archive': archive, 'files': files}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_manifest(root):
    raw = text(root, 'manifest.json', 65536)
    value = json.loads(raw, object_pairs_hook=no_duplicates,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))
    require(type(value) is dict and type(value.get('version')) is int and value['version'] == 1,
            'Unknown manifest version')
    require(type(value.get('files')) is dict and set(value['files']) == set(FILES),
            'Unexpected manifest file list')
    for entry in value['files'].values():
        require(type(entry) is dict and set(entry) == {'bytes', 'sha256'}, 'Invalid file record')
        require(type(entry['bytes']) is int and entry['bytes'] >= 0, 'Invalid byte count')
        require(type(entry['sha256']) is str and HEX.fullmatch(entry['sha256']), 'Invalid SHA256')
    require(type(value.get('generation')) is str, 'Missing generation ID')
    return value


def verify(root, expected_manifest):
    require(type(expected_manifest) is str and HEX.fullmatch(expected_manifest),
            'Supply the separately recorded64lowercase hex manifest hash')
    require(digest(root / 'manifest.json') == expected_manifest, 'Manifest SHA256 mismatch')
    value = read_manifest(root)
    require(value == describe(root, value['generation']), 'Bundle metadata/hash/size mismatch')
    return value


def seal(root):
    require(not (root / 'manifest.json').exists() and not (root / 'manifest.json').is_symlink(),
            'manifest.json already exists: never overwrite a generation')
    value = describe(root, root.name)
    # These are only this generation's exported files, not the running data volume.
    for name in FILES:
        with (root / name).open('rb') as file:
            os.fsync(file.fileno())
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    descriptor = os.open(root / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    # Files/manifest live in root; root itself is a new directory entry in its
    # already prepared backup parent. Both directories need a sync request.
    for directory in (root, root.parent):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('seal', help='check own generation and create a new manifest once')
    create.add_argument('directory', type=Path)
    check = sub.add_parser('verify', help='read/check files; no extraction or Docker calls')
    check.add_argument('directory', type=Path)
    check.add_argument('--expected-manifest', required=True)
    args = parser.parse_args(argv)
    try:
        value = seal(args.directory) if args.action == 'seal' else verify(args.directory, args.expected_manifest)
    except (OSError, ValueError, tarfile.TarError, UnicodeError) as error:
        print('FAIL:', error, file=sys.stderr)
        return 1
    total = sum(item['bytes'] for item in value['files'].values())
    print(f"OK {args.action}: {value['generation']} counter={value['counter']} bytes={total}")
    print('manifest_sha256=' + digest(args.directory / 'manifest.json'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
