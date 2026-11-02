#!/usr/bin/env python3
"""Real Go/HTTP/file tests on loopback in TemporaryDirectory; never starts Nexus."""
import argparse
import contextlib
import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import selectors
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.parse
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artifacts import MODULE, VERSION, escape_path, make_module, manifest, verify

HERE = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def server(directory=None, status=None):
    requests = []
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *unused):
            pass
        def do_GET(self):
            requests.append(self.path)
            if status is not None:
                self.send_error(status)
            else:
                super().do_GET()
    handler = functools.partial(Handler, directory=str(directory))
    instance = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{instance.server_port}', requests
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()


def run(go, arguments, cwd, env, okay=True):
    start = time.monotonic()
    result = subprocess.run([go, *arguments], cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if (result.returncode == 0) != okay:
        raise AssertionError(f'{arguments}: unexpected exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result, round((time.monotonic() - start) * 1000, 2)


def wait_listen(process, timeout=10):
    """Read one bounded startup line on Linux; no blocking readline on a partial line."""
    fd = process.stdout.fileno()
    os.set_blocking(fd, False)
    data = bytearray()
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as ready:
        ready.register(fd, selectors.EVENT_READ)
        while True:
            if b'\n' in data:
                line = bytes(data).split(b'\n', 1)[0].decode('ascii')
                if not line.startswith('LISTEN 127.0.0.1:'):
                    raise AssertionError('unexpected service startup line')
                port = line.removeprefix('LISTEN 127.0.0.1:')
                if not port.isdecimal() or not 1 <= int(port) <= 65535:
                    raise AssertionError('invalid startup port')
                return '127.0.0.1:' + port
            if process.poll() is not None:
                raise AssertionError('service exited before readiness')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('service readiness timed out')
            if not ready.select(min(remaining, 0.1)):
                continue
            try:
                chunk = os.read(fd, 4096 - len(data))
            except BlockingIOError:
                continue
            if not chunk:
                raise AssertionError('EOF before a complete readiness line')
            data.extend(chunk)
            if len(data) == 4096 and b'\n' not in data:
                raise AssertionError('startup line exceeds 4096 bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go', required=True, help='path to prepared Go executable')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    go = str(Path(args.go).resolve()) if '/' in args.go else shutil.which(args.go)
    if not go:
        raise SystemExit('Go executable not found')
    report = {'scope': 'real Go + loopback HTTP + files; NOT Nexus server', 'checks': []}
    def passed(name, **details):
        report['checks'].append({'name': name, 'passed': True, **details})
    with tempfile.TemporaryDirectory(prefix='nexus-client-') as temporary:
        root = Path(temporary)
        for name in ('home', 'cache', 'modcache', 'gopath'):
            (root / name).mkdir()
        # Do not read or rewrite the user's persistent Go configuration/credentials.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GO')}
        env.update(HOME=str(root / 'home'), GOENV='off', GOTOOLCHAIN='local', GOAUTH='off', GOWORK='off',
                   GOPATH=str(root / 'gopath'), GOCACHE=str(root / 'cache'),
                   GOMODCACHE=str(root / 'modcache'), GOPRIVATE='example.invalid',
                   GONOPROXY='none', GONOSUMDB='example.invalid', GOSUMDB='sum.golang.org',
                   CGO_ENABLED='0')
        result, _ = run(go, ['version'], root, env)
        report['go_version'] = result.stdout.strip()
        source = root / 'module'
        shutil.copytree(HERE / 'module' / 'ledger', source)
        env['GOPROXY'] = 'off'
        run(go, ['test', './...'], source, env)
        passed('own source module tests')
        proxy = root / 'proxy'
        archive = make_module(source, proxy)
        passed('uppercase module escape', escaped=escape_path(MODULE))
        service = root / 'service'
        shutil.copytree(HERE / 'service', service)
        with server(proxy) as (url, requests):
            env['GOPROXY'] = url
            result, elapsed = run(go, ['mod', 'tidy'], service, env)
            run(go, ['test', './...'], service, env)
            run(go, ['mod', 'verify'], service, env)
            saved_requests = list(requests)
            if not any('/!acme/ledger/@v/v1.0.0.zip' in urllib.parse.unquote(p) for p in requests):
                raise AssertionError('escaped .zip request missing')
            passed('clean HTTP client reads actual module proxy layout', requests=saved_requests, elapsed_ms=elapsed)
        # Upstream fixture has stopped. Warm client needs no new network for these inputs.
        env['GOPROXY'] = 'off'
        run(go, ['test', './...'], service, env)
        passed('warm client succeeds after HTTP upstream disappears')
        empty = root / 'empty-modcache'
        env['GOMODCACHE'] = str(empty)
        run(go, ['mod', 'download', MODULE + '@' + VERSION], service, env, okay=False)
        passed('clean client cannot resolve missing upstream with GOPROXY=off')
        # Comma and pipe are tested by the real Go command and independent caches.
        for code in (404, 410, 401, 403, 500):
            for separator in (',', '|'):
                with server(status=code) as (first, first_requests), server(proxy) as (second, second_requests):
                    env['GOMODCACHE'] = str(root / f'mods-{code}-{ord(separator)}')
                    env['GOPROXY'] = first + separator + second
                    expected = code in (404, 410) or separator == '|'
                    run(go, ['mod', 'download', '-json', MODULE + '@' + VERSION], service, env, okay=expected)
                    if bool(second_requests) != expected:
                        raise AssertionError(f'unexpected fallback: {code} {separator}')
                    passed(f'GOPROXY {code} {separator}', fallback=bool(second_requests))
        # Preserve go.sum, change valid source ZIP, and use another genuinely clean cache.
        with zipfile.ZipFile(archive) as original:
            payloads = [(i.filename, original.read(i.filename)) for i in original.infolist()]
        trusted_archive = archive.read_bytes()
        with zipfile.ZipFile(archive, 'w') as altered:
            for filename, data in payloads:
                altered.writestr(filename, data + (b'\n// altered\n' if filename.endswith('/ledger.go') else b''))
        env['GOMODCACHE'] = str(root / 'tampered-mods')
        with server(proxy) as (url, unused):
            env['GOPROXY'] = url
            result, _ = run(go, ['mod', 'download', MODULE + '@' + VERSION], service, env, okay=False)
            if 'checksum mismatch' not in result.stderr:
                raise AssertionError('failure did not prove checksum mismatch: ' + result.stderr)
        passed('existing go.sum rejects altered module source even with private sumdb exemption')
        archive.write_bytes(trusted_archive)
        # Build from restored, verified source; run a real loopback Go HTTP service.
        bundle = root / 'bundle'
        bundle.mkdir()
        binary = bundle / 'pulse-linux-amd64'
        with server(proxy) as (url, unused):
            env['GOPROXY'] = url
            env['GOMODCACHE'] = str(root / 'restore-mods')
            run(go, ['build', '-trimpath', '-buildvcs=false', '-ldflags=-X main.version=1.0.0',
                     '-o', str(binary), './cmd/pulse'], service, env)
        record = manifest(binary, '1.0.0', report['go_version'])
        manifest_path = bundle / 'manifest.json'
        manifest_path.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
        (bundle / 'SHA256SUMS').write_text(record['sha256'] + '  ' + binary.name + '\n')
        verify(manifest_path, bundle)
        process = subprocess.Popen([str(binary), '-listen', '127.0.0.1:0'], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=env)
        try:
            address = wait_listen(process)
            for endpoint, wanted in (('/healthz', 'ok'), ('/version', '1.0.0'), ('/hello', 'ledger:v1 hello reader')):
                with urllib.request.urlopen('http://' + address + endpoint, timeout=5) as response:
                    if response.read().decode().strip() != wanted:
                        raise AssertionError(endpoint)
        finally:
            try:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=10)
            finally:
                process.stdout.close()
                process.stderr.close()
        passed('built binary serves real HTTP health/version/hello', size_bytes=record['size_bytes'])
        symlink_bundle = root / 'symlink-bundle'
        symlink_bundle.mkdir()
        (symlink_bundle / binary.name).symlink_to(binary)
        try:
            verify(manifest_path, symlink_bundle)
        except ValueError as error:
            if 'regular file' not in str(error):
                raise
        else:
            raise AssertionError('symlink accepted')
        passed('manifest rejects symlink artifact')
        backup = root / 'backup'
        shutil.copytree(bundle, backup)
        data = bytearray(binary.read_bytes())
        data[len(data) // 2] ^= 1
        binary.write_bytes(data)
        try:
            verify(manifest_path, bundle)
        except ValueError as error:
            if str(error) != 'sha256 mismatch':
                raise
        else:
            raise AssertionError('corruption accepted')
        passed('same-size corruption rejected by manifest before execution')
        shutil.copy2(backup / binary.name, binary)
        verify(manifest_path, bundle)
        result = subprocess.run([str(binary), '-version'], check=True, text=True, capture_output=True)
        if result.stdout.strip() != '1.0.0':
            raise AssertionError('restored binary version')
        passed('local file backup restoration returns identical artifact')
    report['passed'] = len(report['checks'])
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(rendered)
    print(rendered)


if __name__ == '__main__':
    main()
