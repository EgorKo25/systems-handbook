#!/usr/bin/env python3
"""Produce real native Go reports. Never starts or emulates SonarQube."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def prepare(project, go):
    project = Path(project).resolve()
    if not (project / 'go.mod').is_file():
        raise ValueError('project must contain go.mod')
    reports = project / 'reports'
    if reports.is_symlink():
        raise ValueError('reports must not be a symlink')
    reports.mkdir(exist_ok=True)
    names = ['coverage.out', 'test.jsonl', 'test-stderr.txt', 'vet.txt', 'reports-manifest.json']
    for name in names:
        target = reports / name
        if target.is_symlink():
            raise ValueError('report files must not be symlinks')
        if target.exists():
            target.unlink()
    env = {**os.environ, 'GOFLAGS': '', 'GOWORK': 'off', 'GOTOOLCHAIN': 'local', 'CGO_ENABLED': '0'}
    version = subprocess.check_output([go, 'version'], cwd=project, env=env, text=True).strip()
    flags = ['test', '-count=1', '-json', '-covermode=atomic', '-coverprofile=reports/coverage.out', './...']
    with (reports/'test.jsonl').open('wb') as output, (reports/'test-stderr.txt').open('wb') as errors:
        test = subprocess.run([go, *flags], cwd=project, env=env, stdout=output, stderr=errors)
    with (reports/'vet.txt').open('wb') as output:
        vet = subprocess.run([go, 'vet', './...'], cwd=project, env=env, stdout=output, stderr=subprocess.STDOUT)
    entries = {}
    for name in names[:-1]:
        target = reports / name
        if target.is_file():
            data = target.read_bytes()
            entries[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    manifest = dict(format=1, go=version, argv=flags, test_exit=test.returncode, vet_exit=vet.returncode,
                    files=entries, purpose='Local reports only; not a server gate or signed provenance.')
    (reports/'reports-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return 0 if test.returncode == 0 and vet.returncode == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--go', default=os.environ.get('HANDBOOK_GO', 'go'))
    args = parser.parse_args()
    go = shutil.which(args.go)
    if not go:
        parser.error('Go executable not found; pass --go /absolute/path/to/go')
    try:
        return prepare(args.project, go)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
