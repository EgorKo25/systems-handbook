#!/usr/bin/env python3
"""Исполняет точный безопасный TLS-блок главы03 в новой временной HOME.
Никаких служб, host trust, sudo или серверных настроек. Bash -n VM-рецептов
проверяет только синтаксис, не успешность установки/backup.
"""
import argparse, html, json, os, re, subprocess, tempfile
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path);a=ap.parse_args()
    volume=Path(__file__).resolve().parents[2]
    report={'date':'2026-11-01','scope':'native OpenSSL in temporary HOME; static bash -n only for VM scripts','checks':[]}
    def run(args,env=None,ok=True):
        p=subprocess.run(args,env=env,text=True,capture_output=True,timeout=40)
        assert (p.returncode==0)==ok,p.stderr[-500:]
        return p
    with tempfile.TemporaryDirectory(prefix='artifactory-blocks-') as td:
        env=dict(os.environ,HOME=td)
        body=(volume/'sources/artifactory-03-addresses.html').read_text()
        code=next(html.unescape(s) for s in re.findall(r'<pre><code>(.*?)</code></pre>',body,re.S) if 'openssl req' in s)
        run(['bash','-c',code],env)
        tls=Path(td)/'artifactory-handbook/work/private/tls'
        run(['openssl','verify','-CAfile',str(tls/'ca.crt'),'-verify_hostname','wrong.lab.example',str(tls/'server.crt')],ok=False)
        ca=run(['openssl','x509','-in',str(tls/'ca.crt'),'-noout','-text']).stdout
        assert 'CA:TRUE' in ca and 'Certificate Sign' in ca
        assert (tls/'server.key').stat().st_mode & 0o077 == 0
        report['openssl_version']=run(['openssl','version']).stdout.strip()
        report['checks'].append({'name':'exact chapter03 CA/sign/SAN block succeeds; wrong hostname fails; private key has no group/other access','passed':True})
        for path in sorted((volume/'labs/recipes').glob('*.sh')):
            run(['bash','-n',str(path)])
            report['checks'].append({'name':'static Bash syntax: '+path.name,'passed':True})
    report['checks_passed']=len(report['checks'])
    data=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.report:a.report.write_text(data)
    print(data)
if __name__=='__main__':main()
