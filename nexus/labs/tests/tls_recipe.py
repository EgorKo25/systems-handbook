#!/usr/bin/env python3
"""Run only the book's local certificate generation in TemporaryDirectory.

Does not install CA trust, start services, modify DNS, or bind network ports.
"""
from html import unescape
import json
from pathlib import Path
import re
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[2] / 'sources' / '02-nexus-addresses.html').read_text()
match = re.search(r'<pre><code>(umask 077.*?)</code></pre>', source, re.S)
assert match
with tempfile.TemporaryDirectory(prefix='nexus-cert-recipe-') as temporary:
    recipe = subprocess.run(['bash', '-e', '-c', unescape(match[1])], cwd=temporary,
                            capture_output=True, text=True, timeout=30)
    if recipe.returncode:
        raise AssertionError('local certificate recipe failed; no services were started')
    version = subprocess.run(['openssl', 'version'], check=True, capture_output=True, text=True).stdout.strip()
    result = subprocess.run(['openssl','verify','-CAfile','lab-tls/ca.pem',
                             '-verify_hostname','nexus.lab.example','lab-tls/server.pem'],
                            cwd=temporary, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and ': OK' in result.stdout
    wrong = subprocess.run(['openssl','verify','-CAfile','lab-tls/ca.pem',
                            '-verify_hostname','other.lab.example','lab-tls/server.pem'],
                           cwd=temporary, capture_output=True, text=True, timeout=10)
    assert wrong.returncode != 0 and 'hostname mismatch' in wrong.stderr
report = dict(scope='real local certificate recipe only; no Nexus/NGINX/TLS server or trust installation',
              openssl=version, passed=3,
              checks=['book certificate commands execute', 'CA signature + SAN hostname accepted',
                      'different hostname rejected'])
output = Path(__file__).with_name('tls-results.json')
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(output.name + ': 3/3 local certificate checks passed')
