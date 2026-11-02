#!/usr/bin/env python3
"""Real native-engine and loopback acceptance test, never a host service installer.

Mutable build data and generated binaries live in TemporaryDirectory. A prepared
module cache is copied into it; network module lookup is disabled. User-supplied
executables/cache are only read. Persistent reader exercises are separate.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def run(args, cwd=None, **kwargs):
    result = subprocess.run([str(a) for a in args], cwd=cwd, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise AssertionError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def request(url, method='GET'):
    # These requests target only this runner's own loopback processes.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, method=method), timeout=4) as r:
        return r.read().decode()


def wait_for(predicate, seconds=20):
    until = time.monotonic() + seconds
    last = None
    while time.monotonic() < until:
        try:
            result = predicate()
            if result: return result
        except (OSError, urllib.error.URLError, AssertionError, KeyError, IndexError) as exc:
            last = str(exc)
        time.sleep(.15)
    raise AssertionError(f'timeout: {last}')


def query(base, expression, timestamp=None):
    params = {'query': expression}
    if timestamp is not None: params['time'] = str(timestamp)
    result = json.loads(request(base + '/api/v1/query?' + urllib.parse.urlencode(params)))
    assert result['status'] == 'success', result
    assert not result.get('warnings'), result
    return result['data']['result']


def stop(process):
    if process and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try: process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)


def check_flags(prometheus, promtool):
    spec = importlib.util.spec_from_file_location('prom_reference_check', HERE.parent / 'sources/reference.py')
    ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
    for card in ref.COMMANDS:
        executable = prometheus if card['name'] == 'prometheus' else promtool
        args = card['name'].split()[1:]
        output = run([executable, *args, '--help'])
        normalized = output.replace('--[no-]', '--')
        for flag in card['flags']:
            assert flag['flag'] in normalized, (card['name'], flag['flag'])
    print('CLI HELP PASS: literal command names and card flags')


def live(prometheus, promtool, go, module_cache):
    processes = []
    with tempfile.TemporaryDirectory(prefix='prometheus-handbook-') as directory:
        work = Path(directory)
        binary = work / 'go-lab'
        cache = work / 'modules'
        shutil.copytree(module_cache, cache)
        service_source = work / 'go-service'
        shutil.copytree(HERE / 'go-service', service_source)
        env = dict(os.environ, GOTOOLCHAIN='local', GOENV='off', GOWORK='off',
                   GOTELEMETRY='off', GOPROXY='off', GOSUMDB='off', GOFLAGS='',
                   GOPATH=str(work / 'gopath'), GOCACHE=str(work / 'buildcache'),
                   GOMODCACHE=str(cache))
        run([go, 'test', '-mod=readonly', '-race', './...'], cwd=service_source, env=env)
        run([go, 'build', '-mod=readonly', '-o', binary, '.'], cwd=service_source, env=env)
        gp = free_port(); pp = free_port()
        assert gp != pp
        config = work / 'prometheus.yml'
        config.write_text(f'global:\n  scrape_interval: 1s\n  scrape_timeout: 900ms\nscrape_configs:\n  - job_name: go-lab\n    static_configs:\n      - targets: ["127.0.0.1:{gp}"]\n')
        empty = work / 'empty.yml'; empty.write_text('global:\n  scrape_interval: 1s\nscrape_configs: []\n')
        data = work / 'data'
        base = f'http://127.0.0.1:{pp}'
        log = (work / 'process.log').open('w+')

        def start(db=data, port=pp, admin=False, cfg=config):
            args = [str(prometheus), f'--config.file={cfg}', f'--storage.tsdb.path={db}', f'--web.listen-address=127.0.0.1:{port}', '--storage.tsdb.retention.time=1d']
            if admin: args.append('--web.enable-admin-api')
            p = subprocess.Popen(args, stdout=log, stderr=log)
            processes.append(p)
            wait_for(lambda: request(f'http://127.0.0.1:{port}/-/ready') == 'Prometheus Server is Ready.\n')
            assert p.poll() is None
            return p
        try:
            g = subprocess.Popen([str(binary), '-port', str(gp)], stdout=log, stderr=log); processes.append(g)
            wait_for(lambda: request(f'http://127.0.0.1:{gp}/ready') == 'ready\n')
            p = start()
            try:
                request(base + '/api/v1/admin/tsdb/snapshot', method='POST')
                raise AssertionError('admin API unexpectedly enabled')
            except urllib.error.HTTPError as exc:
                assert exc.code == 500 and 'admin APIs disabled' in exc.read().decode(), exc.code
            wait_for(lambda: query(base, 'up{job="go-lab"}') and float(query(base, 'up{job="go-lab"}')[0]['value'][1]) == 1)
            request(f'http://127.0.0.1:{gp}/work')
            try: request(f'http://127.0.0.1:{gp}/work?fail=1')
            except urllib.error.HTTPError as exc: assert exc.code == 500
            expression = 'lab_requests_total{code="500"}'
            samples = wait_for(lambda: (q if q and float(q[0]['value'][1]) == 1 else None) if (q := query(base, expression)) is not None else None)
            stamp = float(samples[0]['value'][0])
            metrics = request(f'http://127.0.0.1:{gp}/metrics')
            result = subprocess.run([str(promtool), 'check', 'metrics'], input=metrics, text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
            stop(p)
            assert (data / 'wal').is_dir()
            p = start(admin=True)
            old = query(base, expression, stamp)
            assert old and float(old[0]['value'][1]) == 1, old
            snapshot = json.loads(request(base + '/api/v1/admin/tsdb/snapshot', method='POST'))
            assert snapshot['status'] == 'success', snapshot
            snap = data / 'snapshots' / snapshot['data']['name']
            restored = work / 'restored'
            shutil.copytree(snap, restored)
            rp = free_port()
            r = start(db=restored, port=rp, cfg=empty)
            old = query(f'http://127.0.0.1:{rp}', expression, stamp)
            assert old and float(old[0]['value'][1]) == 1, old
            print('LIVE PASS: Go200/500 → exposition lint → scrape/up → sample → WAL restart → snapshot → independent restore query')
        finally:
            for proc in reversed(processes): stop(proc)
            log.flush()
            if sys.exc_info()[0]:
                log.seek(0); print(log.read()[-10000:], file=sys.stderr)
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prometheus', required=True, type=Path)
    parser.add_argument('--promtool', required=True, type=Path)
    parser.add_argument('--go', type=Path, help='also run real Go/race and temporary loopback acceptance')
    parser.add_argument('--module-cache', type=Path, help='prepared GOMODCACHE, read and copied; required with --go')
    args = parser.parse_args()
    prometheus = args.prometheus.resolve(); promtool = args.promtool.resolve()
    for binary in (prometheus, promtool):
        version = run([binary, '--version'])
        assert '3.13.5' in version, version
    print(run([sys.executable, HERE.parent / 'tests/check_sources.py']).strip())
    print(run([sys.executable, HERE.parent / 'tests/check_math_model.py']).strip())
    print(run([promtool, 'check', 'config', HERE / 'prometheus.yml']).strip())
    print(run([promtool, 'test', 'rules', HERE / 'fixtures/promql.yml']).strip())
    negative = subprocess.run([str(promtool), 'test', 'rules', str(HERE / 'fixtures/many-to-many-invalid.yml')], text=True, capture_output=True)
    assert negative.returncode != 0 and 'many-to-many matching not allowed' in negative.stdout + negative.stderr, negative.stdout + negative.stderr
    print('NEGATIVE PASS: duplicate unique side rejected by real engine')
    check_flags(prometheus, promtool)
    if args.go:
        assert args.module_cache and args.module_cache.is_dir(), '--go requires prepared --module-cache'
        live(prometheus, promtool, args.go.resolve(), args.module_cache.resolve())
    else: print('NOT RUN: Go/race, HTTP scrape, restart, snapshot/restore (pass --go to execute)')


if __name__ == '__main__': main()
