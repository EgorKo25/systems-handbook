#!/usr/bin/env python3
"""Own manifest: matching SHA256 is integrity against a separately trusted manifest.
No origin/signature proof; no hostile concurrent writer/TOCTOU protection.
"""
from pathlib import Path
import argparse, hashlib, json, re

def describe(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular non-symlink file required')
    b = path.read_bytes()
    return {'name': path.name, 'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def verify(document, directory):
    if not isinstance(document, dict) or any(not isinstance(document.get(k), str) or not document[k].strip() for k in ('version','toolchain')):
        raise ValueError('version and toolchain must be nonempty strings')
    files = document.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('nonempty files list required')
    seen = set()
    directory = directory.resolve(strict=True)
    for item in files:
        if not isinstance(item, dict) or set(item) != {'name','size','sha256'}:
            raise ValueError('file requires name,size,sha256')
        name = item['name']
        if not isinstance(name, str) or name in seen:
            raise ValueError('unique string basename required')
        seen.add(name)
        if name != Path(name).name or name in ('', '.', '..') or '\\' in name:
            raise ValueError('basename required')
        if type(item['size']) is not int or item['size'] < 0 or not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):
            raise ValueError('nonnegative integer size and lowercase SHA256 required')
        path = directory / name
        if path.is_symlink() or path.resolve(strict=True).parent != directory:
            raise ValueError('file must stay in bundle')
        if describe(path) != item:
            raise ValueError('size or SHA256 mismatch')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    c = sub.add_parser('create')
    c.add_argument('--version', required=True)
    c.add_argument('--toolchain', required=True)
    c.add_argument('--file', action='append', required=True, type=Path)
    c.add_argument('--output', required=True, type=Path)
    v = sub.add_parser('verify')
    v.add_argument('--manifest', required=True, type=Path)
    v.add_argument('--directory', required=True, type=Path)
    a = p.parse_args()
    if a.action == 'create':
        names = [x.name for x in a.file]
        if len(names) != len(set(names)):
            raise ValueError('duplicate basename')
        a.output.write_text(json.dumps({'version': a.version, 'toolchain': a.toolchain, 'files': [describe(x) for x in a.file]}, indent=2) + '\n')
    else:
        verify(json.loads(a.manifest.read_text()), a.directory)
        print('PASS: named bytes match manifest; origin trust is separate')
