#!/usr/bin/env python3
"""Own byte-level experiment: canonical Go h1 versus a ZIP's SHA-256.

Creates only tiny known module fixtures under TemporaryDirectory. A real Go
client reads file:// proxy fixtures, without a Nexus server or network access.
The educational h1 calculation is not a general Go module ZIP validator.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

MODULE = 'example.invalid/bytes/lab'
VERSION = 'v1.0.0'
PREFIX = MODULE + '@' + VERSION + '/'
FILES = {
    'go.mod': b'module example.invalid/bytes/lab\n\ngo 1.26\n',
    'answer.go': b'package lab\n\nconst Answer = 42\n',
}


def canonical(files):
    """The hash input is explicit bytes; only controlled legal names are accepted."""
    lines = []
    for name in sorted(files):
        if '\n' in name:
            raise ValueError('newline in a hash input filename')
        file_hash = hashlib.sha256(files[name]).hexdigest()
        lines.append((file_hash + '  ' + name + '\n').encode('utf-8'))
    summary = b''.join(lines)
    return 'h1:' + base64.b64encode(hashlib.sha256(summary).digest()).decode('ascii'), summary


def make_proxy(directory, files, *, repack=False):
    target = directory / MODULE / '@v'
    target.mkdir(parents=True)
    archive = target / (VERSION + '.zip')
    names = sorted(files, reverse=repack)
    compression = zipfile.ZIP_DEFLATED if repack else zipfile.ZIP_STORED
    with zipfile.ZipFile(archive, 'w', compression=compression) as output:
        for name in names:
            item = zipfile.ZipInfo(PREFIX + name, date_time=(2026, 11, 1 if repack else 2, 0, 0, 0))
            item.external_attr = 0o100644 << 16
            output.writestr(item, files[name], compress_type=compression)
    (target / (VERSION + '.mod')).write_bytes(files['go.mod'])
    (target / (VERSION + '.info')).write_text(json.dumps({'Version': VERSION, 'Time': '2026-11-01T00:00:00Z'}) + '\n')
    (target / 'list').write_text(VERSION + '\n')
    return archive


def experiment(go):
    report = {'scope': 'actual Go client, private file:// fixtures; no Nexus, HTTP or public checksum lookup',
              'module': MODULE, 'version': VERSION, 'checks': []}
    with tempfile.TemporaryDirectory(prefix='nexus-h1-bytes-') as temporary:
        root = Path(temporary)
        (root / 'home').mkdir()
        base_env = dict(os.environ, GOENV='off', GOFLAGS='', GOWORK='off', GOTOOLCHAIN='local', GOAUTH='off',
                        GOPRIVATE='example.invalid', GONOPROXY='none', GONOSUMDB='example.invalid',
                        GOSUMDB='sum.golang.org', GO111MODULE='on',
                        GOCACHE=str(root / 'gocache'), GOPATH=str(root / 'gopath'), HOME=str(root / 'home'))
        tool = subprocess.run([go, 'version'], check=True, text=True, capture_output=True, env=base_env)
        report['go_version'] = tool.stdout.strip()

        def download(label, files, *, repack=False, known_sum=None, success=True):
            case = root / label
            case.mkdir()
            archive = make_proxy(case / 'proxy', files, repack=repack)
            project = case / 'consumer'
            project.mkdir()
            (project / 'go.mod').write_text('module example.invalid/consumer\n\ngo 1.26\n\nrequire ' + MODULE + ' ' + VERSION + '\n')
            if known_sum is not None:
                (project / 'go.sum').write_text(known_sum)
            env = dict(base_env, GOPROXY=(case / 'proxy').as_uri(), GOMODCACHE=str(case / 'gomodcache'))
            process = subprocess.run([go, 'mod', 'download', '-json', MODULE + '@' + VERSION], cwd=project,
                                     env=env, capture_output=True, text=True)
            if (process.returncode == 0) != success:
                raise AssertionError(label + ': unexpected exit: ' + process.stderr.replace(str(root), '<temporary>'))
            # Fatal integrity failures can exit before any JSON object is emitted.
            answer = json.loads(process.stdout) if process.stdout.strip() else {}
            return dict(answer=answer, stderr=process.stderr,
                        sumfile=(project / 'go.sum').read_text() if (project / 'go.sum').exists() else '',
                        zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), zip_bytes=archive.stat().st_size)

        h1, summary = canonical({PREFIX + name: data for name, data in FILES.items()})
        mod_h1, mod_summary = canonical({'go.mod': FILES['go.mod']})
        original = download('a-original', FILES)
        assert original['answer']['Sum'] == h1
        assert original['answer']['GoModSum'] == mod_h1
        report['checks'].append({'name': 'own canonical calculation matches real Go Sum and GoModSum', 'passed': True})

        repacked = download('b-repacked', FILES, repack=True, known_sum=original['sumfile'])
        assert repacked['zip_sha256'] != original['zip_sha256']
        assert repacked['answer']['Sum'] == h1
        report['checks'].append({'name': 'different ZIP bytes and order accepted with the same trusted go.sum', 'passed': True})

        changed = dict(FILES, **{'answer.go': b'package lab\n\nconst Answer = 43\n'})
        rejected = download('c-known-mismatch', changed, known_sum=original['sumfile'], success=False)
        error = rejected['answer'].get('Error', '') + rejected['stderr']
        assert 'checksum mismatch' in error and 'SECURITY ERROR' in error
        report['checks'].append({'name': 'known go.sum rejects changed content even with GONOSUMDB exemption', 'passed': True})

        first_use = download('d-no-known-sum', changed)
        changed_h1, _ = canonical({PREFIX + name: data for name, data in changed.items()})
        assert first_use['answer']['Sum'] == changed_h1 and changed_h1 != h1
        report['checks'].append({'name': 'no known sum and no external private checksum trust accepts first received content', 'passed': True})

        renamed = dict(FILES)
        renamed['renamed.go'] = renamed.pop('answer.go')
        moved = download('e-renamed-file', renamed)
        renamed_h1, _ = canonical({PREFIX + name: data for name, data in renamed.items()})
        assert moved['answer']['Sum'] == renamed_h1 and renamed_h1 != h1
        report['checks'].append({'name': 'filenames participate in the canonical hash', 'passed': True})

        report.update(module_h1=h1, go_mod_h1=mod_h1, changed_h1=changed_h1,
                      canonical_summary_utf8=summary.decode(), go_mod_summary_utf8=mod_summary.decode(),
                      archive_a=dict(sha256=original['zip_sha256'], bytes=original['zip_bytes']),
                      archive_b=dict(sha256=repacked['zip_sha256'], bytes=repacked['zip_bytes']),
                      passed=len(report['checks']),
                      limitations=['Not a module ZIP validator for arbitrary inputs',
                                   'Nexus and remote checksum database not executed',
                                   'Checksums establish consistency against trusted expectations, not source code safety'])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', default=os.environ.get('HANDBOOK_GO') or shutil.which('go'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.go:
        parser.error('provide --go or HANDBOOK_GO pointing to a prepared Go executable')
    report = experiment(args.go)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded)
    print(encoded)
