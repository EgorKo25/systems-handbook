#!/usr/bin/env python3
"""Real local Go steps. No GitLab emulator, dependencies or network installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run(argv, *, check=True, env=None):
    return subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, check=check)


def go_command():
    binary = os.environ.get('HANDBOOK_GO') or shutil.which('go')
    if not binary:
        raise RuntimeError('Go is required; set HANDBOOK_GO or prepare PATH. Nothing was installed.')
    return binary


def junit_from_go(output, returncode):
    """Convert the demonstrated go test event stream, including incomplete runs."""
    cases = {}
    package_state = {}
    packages_seen = set()
    package_output = {}
    saw_event = False
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            package_output.setdefault('(tool)', []).append(line)
            continue
        if not isinstance(event, dict) or 'Action' not in event:
            package_output.setdefault('(tool)', []).append(line)
            continue
        saw_event = True
        package = str(event.get('Package', '(tool)'))
        if 'Package' in event:
            packages_seen.add(package)
        test = event.get('Test')
        action = event['Action']
        if test:
            item = cases.setdefault((package, str(test)), dict(action='incomplete', output=[], elapsed=0.0))
            if action == 'output':
                item['output'].append(str(event.get('Output', '')))
            elif action in ('pass', 'fail', 'skip'):
                item['action'] = action
                item['elapsed'] = event.get('Elapsed', 0)
        else:
            if action in ('pass', 'fail', 'skip'):
                package_state[package] = action
            if action == 'output':
                package_output.setdefault(package, []).append(str(event.get('Output', '')))
    suites = ET.Element('testsuites')
    suite = ET.SubElement(suites, 'testsuite', name='Go tests')
    for (package, test), item in sorted(cases.items()):
        try:
            elapsed = max(0.0, float(item['elapsed']))
        except (TypeError, ValueError):
            elapsed = 0.0
        case = ET.SubElement(suite, 'testcase', classname=package, name=test, time=str(elapsed))
        if item['action'] == 'fail':
            ET.SubElement(case, 'failure', message='Go test failed').text = ''.join(item['output'])
        elif item['action'] == 'skip':
            ET.SubElement(case, 'skipped', message='Go test skipped')
        elif item['action'] == 'incomplete':
            ET.SubElement(case, 'error', message='No final test event').text = ''.join(item['output'])
    for package, state in sorted(package_state.items()):
        has_test_failure = any(p == package and item['action'] == 'fail' for (p, _), item in cases.items())
        if state == 'fail' and not has_test_failure:
            case = ET.SubElement(suite, 'testcase', classname=package, name='(package failure)', time='0')
            ET.SubElement(case, 'error', message='Package failed outside a completed test').text = ''.join(package_output.get(package, []))
    for package in sorted(packages_seen - package_state.keys()):
        case = ET.SubElement(suite, 'testcase', classname=package, name='(incomplete package)', time='0')
        ET.SubElement(case, 'error', message='No final package event').text = ''.join(package_output.get(package, []))
    errors = list(suite.iter('error'))
    failures = list(suite.iter('failure'))
    if returncode and not errors and not failures:
        case = ET.SubElement(suite, 'testcase', classname='(tool)', name='(go test exit)', time='0')
        ET.SubElement(case, 'error', message=f'go test exited {returncode}').text = output
    if not saw_event:
        case = ET.SubElement(suite, 'testcase', classname='(tool)', name='(missing events)', time='0')
        ET.SubElement(case, 'error', message='No go test JSON events were received').text = output
    suite.set('tests', str(len(suite.findall('testcase'))))
    suite.set('failures', str(len(list(suite.iter('failure')))))
    suite.set('errors', str(len(list(suite.iter('error')))))
    suite.set('skipped', str(len(list(suite.iter('skipped')))))
    return ET.tostring(suites, encoding='unicode') + '\n'


def test():
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    result = run([go_command(), 'test', '-json', '-count=1', './...'], check=False)
    (reports / 'tests.jsonl').write_text(result.stdout, encoding='utf-8')
    report = junit_from_go(result.stdout, result.returncode)
    (reports / 'junit.xml').write_text(report, encoding='utf-8')
    print(result.stdout, end='')
    # Malformed/incomplete output must never be silently reported as success.
    invalid_report = ET.fromstring(report).find('.//error') is not None
    return result.returncode or (1 if invalid_report else 0)


def source_revision():
    value = os.environ.get('CI_COMMIT_SHA')
    if value:
        return value
    try:
        result = run(['git', '-c', 'core.hooksPath=/dev/null', 'rev-parse', 'HEAD'], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return 'local-unversioned'


def build(version):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,79}', version):
        raise ValueError('Version must contain 1..80 simple version characters.')
    binary = ROOT / 'dist' / ('echo.exe' if os.name == 'nt' else 'echo')
    binary.parent.mkdir(exist_ok=True)
    env = dict(os.environ, CGO_ENABLED='0')
    tool = go_command()
    target = json.loads(run([tool, 'env', '-json', 'GOOS', 'GOARCH'], env=env).stdout)
    expected_name = 'echo.exe' if target['GOOS'] == 'windows' else 'echo'
    binary = binary.with_name(expected_name)
    run([tool, 'build', '-trimpath', '-buildvcs=false', '-ldflags=-X main.Version=' + version,
         '-o', str(binary), './cmd/echo'], env=env)
    raw = binary.read_bytes()
    manifest = dict(file=binary.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                    source_revision=source_revision(), version=version,
                    toolchain=run([tool, 'version']).stdout.strip(), **target)
    (binary.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def verify():
    directory = ROOT / 'dist'
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    name = manifest.get('file')
    if name not in ('echo', 'echo.exe'):
        raise ValueError('Unexpected artifact filename')
    binary = directory / name
    raw = binary.read_bytes()
    if len(raw) != manifest['bytes'] or hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('Artifact size or SHA-256 mismatch; binary was not executed.')
    # This exercise deliberately verifies a native artifact. Cross builds need a target runner.
    native = json.loads(run([go_command(), 'env', '-json', 'GOHOSTOS', 'GOHOSTARCH']).stdout)
    if manifest['GOOS'] != native['GOHOSTOS'] or manifest['GOARCH'] != native['GOHOSTARCH']:
        raise ValueError('Artifact target differs from this host; use the corresponding native runner.')
    value = run([str(binary), '-version']).stdout.strip()
    if value != manifest['version']:
        raise ValueError('Linked version differs from manifest')
    print('Verified native artifact:', manifest['sha256'], 'version', value)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['test', 'build', 'verify'])
    parser.add_argument('--version', default=os.environ.get('LAB_VERSION', '0.1.0'))
    args = parser.parse_args()
    try:
        return test() if args.action == 'test' else build(args.version) if args.action == 'build' else verify()
    except (RuntimeError, ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('CI step failed:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
