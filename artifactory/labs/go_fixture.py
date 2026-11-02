#!/usr/bin/env python3
"""Author's tiny Go proxy FILE fixture, not an Artifactory implementation."""
from pathlib import Path
import argparse, hashlib, json, zipfile

HERE = Path(__file__).resolve().parent
MODULE = 'example.invalid/BuildLab/checkdigit'
VERSION = 'v1.0.0'

def escape(value):
    return ''.join('!' + c.lower() if 'A' <= c <= 'Z' else c for c in value)

def create(output):
    target = output / escape(MODULE) / '@v'
    target.mkdir(parents=True, exist_ok=False)
    files = ('go.mod', 'checkdigit.go', 'checkdigit_test.go')
    with zipfile.ZipFile(target / (VERSION + '.zip'), 'w', compression=zipfile.ZIP_STORED) as z:
        for name in files:
            item = zipfile.ZipInfo(MODULE + '@' + VERSION + '/' + name, (2026, 11, 1, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            z.writestr(item, (HERE / 'module/checkdigit' / name).read_bytes())
    (target / (VERSION + '.mod')).write_bytes((HERE / 'module/checkdigit/go.mod').read_bytes())
    (target / (VERSION + '.info')).write_text(json.dumps({'Version': VERSION, 'Time': '2026-11-01T00:00:00Z'}) + '\n')
    (target / 'list').write_text(VERSION + '\n')
    return {p.name: {'size': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(target.iterdir())}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(create(args.output), indent=2))
