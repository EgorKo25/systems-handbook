#!/usr/bin/env python3
"""Own artifact formats, not a Nexus implementation. Standard-library only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

MODULE = 'example.invalid/Acme/ledger'
VERSION = 'v1.0.0'
STAMP = '2026-11-01T00:00:00Z'


def escape_path(value):
    return ''.join('!' + c.lower() if 'A' <= c <= 'Z' else c for c in value)


def module_version(value):
    # Deliberately narrow: numeric major-v1 releases of our one teaching module.
    if not isinstance(value, str) or not re.fullmatch(r'v1\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise ValueError('expected a numeric v1.MINOR.PATCH teaching release')
    return value


def make_module(source, destination, version=VERSION):
    """Publish one new local fixture version; never replace earlier version files.

    This is a three-file teaching ZIP, not a general x/mod/zip implementation.
    Individual writes are not a transaction. A failed output remains for inspection.
    """
    source, destination = Path(source), Path(destination)
    version = module_version(version)
    payloads = {}
    for filename in ('go.mod', 'ledger.go', 'ledger_test.go'):
        path = source / filename
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('module inputs must be regular files, not symlinks')
        payloads[filename] = path.read_bytes()
    if not re.search(r'^module[ \t]+' + re.escape(MODULE) + r'[ \t]*$', payloads['go.mod'].decode('utf-8'), re.M):
        raise ValueError('unexpected teaching module path')
    version_dir = destination / escape_path(MODULE) / '@v'
    archive = version_dir / (version + '.zip')
    targets = [archive, version_dir / (version + '.mod'), version_dir / (version + '.info')]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise FileExistsError('version output already exists; inspect it, do not overwrite')
    listing = version_dir / 'list'
    versions = set()
    if listing.exists() or listing.is_symlink():
        if not stat.S_ISREG(listing.lstat().st_mode):
            raise ValueError('version list must be a regular file')
        versions = {module_version(item) for item in listing.read_text(encoding='utf-8').splitlines()}
    if version in versions:
        raise ValueError('version already listed without a complete new output')
    version_dir.mkdir(parents=True, exist_ok=True)
    prefix = MODULE + '@' + version + '/'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for filename, data in payloads.items():
            item = zipfile.ZipInfo(prefix + filename, date_time=(2026, 11, 1, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            output.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)
    with targets[1].open('xb') as output:
        output.write(payloads['go.mod'])
    with targets[2].open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps({'Version': version, 'Time': STAMP}) + '\n')
    versions.add(version)
    order = sorted(versions, key=lambda value: tuple(map(int, value[1:].split('.'))))
    listing.write_text(''.join(value + '\n' for value in order), encoding='utf-8', newline='\n')
    return archive


def manifest(binary, version, toolchain, input_version=VERSION):
    """Describe our declared Linux/amd64 build; this does not inspect Go build info."""
    binary = Path(binary)
    if not stat.S_ISREG(binary.lstat().st_mode):
        raise ValueError('artifact must be a regular file, not a symlink')
    data = binary.read_bytes()
    return {'schema': 1, 'version': version, 'file': binary.name,
            'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'toolchain': toolchain, 'source_module': 'example.invalid/shop/pulse',
            'target': 'linux/amd64', 'inputs': {MODULE: module_version(input_version)}}


def verify(manifest_path, directory):
    record = json.loads(Path(manifest_path).read_text())
    # The manifest is data. Restrict basename instead of letting it escape the bundle.
    if not re.fullmatch(r'[A-Za-z0-9._-]+', record['file']) or record['file'] in ('.', '..'):
        raise ValueError('unsafe artifact name')
    binary = Path(directory) / record['file']
    if not stat.S_ISREG(binary.lstat().st_mode):
        raise ValueError('artifact must be a regular file, not a symlink')
    if binary.stat().st_size != record['size_bytes']:
        raise ValueError('size mismatch')
    if hashlib.sha256(binary.read_bytes()).hexdigest() != record['sha256']:
        raise ValueError('sha256 mismatch')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    pack = commands.add_parser('module')
    pack.add_argument('--output', type=Path, required=True)
    pack.add_argument('--source', type=Path, default=Path(__file__).parent / 'module' / 'ledger',
                      help='the controlled ledger source directory')
    pack.add_argument('--version', default=VERSION,
                      help='new numeric v1.MINOR.PATCH version; existing outputs are refused')
    create = commands.add_parser('manifest')
    create.add_argument('--binary', type=Path, required=True)
    create.add_argument('--version', required=True)
    create.add_argument('--toolchain', required=True)
    create.add_argument('--input-version', default=VERSION,
                        help='declared ledger version from the resolved build, not inferred')
    create.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--manifest', type=Path, required=True)
    check.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'module':
        print(make_module(args.source, args.output, args.version))
    elif args.action == 'manifest':
        if args.output.resolve() == args.binary.resolve():
            parser.error('manifest output must differ from the binary')
        record = manifest(args.binary, args.version, args.toolchain, args.input_version)
        with args.output.open('x', encoding='utf-8', newline='\n') as output:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        print(args.output)
    else:
        print(json.dumps(verify(args.manifest, args.directory), ensure_ascii=False, indent=2))
