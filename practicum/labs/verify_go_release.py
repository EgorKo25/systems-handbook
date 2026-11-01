#!/usr/bin/env python3
"""Verify an existing go/labs/service release; never rebuild or deploy it.

Copy this file to the personal service's tools/verify-release.py and commit it
before building. Uses the service's actual manifest schema, Git checkout and Go.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(project, expected_version, go=None):
    project = Path(project).resolve()
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,79}', expected_version), 'Invalid expected version')
    go = go or os.environ.get('HANDBOOK_GO') or shutil.which('go')
    require(go, 'Prepare Go in PATH or HANDBOOK_GO; no tools were installed')
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0', GOENV='off',
               GOTOOLCHAIN='local', GOWORK='off', GOTELEMETRY='off')

    def output(argv):
        return subprocess.check_output(argv, cwd=project, env=env, stderr=subprocess.STDOUT,
                                       text=True, timeout=15).strip()

    def git(*args):
        return output(['git','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null',*args])

    require(Path(git('rev-parse','--show-toplevel')).resolve() == project,
            'Service must be the root of its own Git checkout')
    head = git('rev-parse','--verify','HEAD')
    require(not git('status','--porcelain','--untracked-files=normal'), 'Checkout has uncommitted input changes')
    declared = os.environ.get('CI_COMMIT_SHA')
    require(not declared or declared == head, 'Declared CI revision differs from observed Git HEAD')
    manifest_path = project/'dist/manifest.json'
    require(not manifest_path.is_symlink(), 'Manifest must be an ordinary file')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest.get('format') == 1, 'Unsupported manifest format')
    require(manifest.get('source_revision') == head and manifest.get('source_dirty') is False,
            'Manifest provenance differs from the clean observed checkout')
    require(manifest.get('version') == expected_version, 'Unexpected release version')
    native = json.loads(output([go,'env','-json','GOHOSTOS','GOHOSTARCH']))
    expected_target = dict(GOOS=native['GOHOSTOS'], GOARCH=native['GOHOSTARCH'],
                           GOAMD64='v1', CGO_ENABLED='0', GOEXPERIMENT='')
    require(manifest.get('target') == expected_target,
            'Artifact target differs from the native lab target or expected build settings')
    name = 'handbook-service.exe' if native['GOHOSTOS'] == 'windows' else 'handbook-service'
    require(manifest.get('binary') == name, 'Unexpected binary filename')
    binary = project/'dist'/name
    require(not binary.is_symlink(), 'Binary must be an ordinary file')
    data = binary.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    require(manifest.get('bytes') == len(data), 'Binary size differs; not executed')
    require(manifest.get('sha256') == digest, 'Binary SHA-256 differs; not executed')
    require(manifest.get('flags') == ['-mod=readonly','-trimpath','-buildvcs=false',
                                    '-ldflags=-X main.Version='+expected_version],
            'Unexpected recorded build flags')
    require(manifest.get('toolchain') == output([go,'version']), 'Actual Go differs from recorded toolchain')
    build_script = project/'tools/build.py'
    require(manifest.get('build_script_sha256') == hashlib.sha256(build_script.read_bytes()).hexdigest(),
            'Actual build script differs from recorded script hash')
    require(output([str(binary),'-version']) == expected_version, 'Linked version differs from expected release')
    return dict(source_revision=head, version=expected_version, sha256=digest,
                bytes=len(data), target=expected_target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--expected-version', default='1.0.0')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.project, args.expected_version), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('Release rejected:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
