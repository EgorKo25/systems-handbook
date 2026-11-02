#!/usr/bin/env python3
"""Real Bash guard tests with an authored curl stub. No downloads/sudo/extract.

Only failed HTTP and wrong-hash branches execute, in a new temporary folder.
The VM script must stop at its checksum before reaching any host mutation.
"""
from pathlib import Path
import argparse, json, os, subprocess, tempfile
HERE=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory(prefix='artifactory-guards-') as td:
        r=Path(td);stub=r/'curl-stub'
        stub.write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
if os.environ['AFT_STUB_MODE']=='http-failure':sys.exit(22)
target=sys.argv[sys.argv.index('--output')+1]
Path(target).write_text('#!/bin/sh\\ntouch "$AFT_EXECUTION_MARKER"\\n')
''');stub.chmod(0o700)
        env=dict(os.environ,AFT_CURL_BIN=str(stub),AFT_EXECUTION_MARKER=str(r/'executed'))
        for script in ['get-cli.sh','get-server.sh','get-oras.sh']:
            for mode in ['http-failure','bad-hash']:
                destination=r/(script+'-'+mode)
                p=subprocess.run(['bash',str(HERE/'recipes'/script),str(destination)],env=dict(env,AFT_STUB_MODE=mode),capture_output=True,text=True)
                assert p.returncode!=0 and not (r/'executed').exists()
                assert not list(destination.glob('jf')) and not list(destination.glob('oras')) and not list(destination.glob('*.tar.gz'))
                assert not list(destination.glob('.*download*'))
                checks.append({'script':script,'failure':mode,'passed':True,'exit':p.returncode})
        # Instrument downstream tools with stubs; bad archive must never reach them.
        tools=r/'tools';tools.mkdir()
        for name in ['sudo','tar']:
            p=tools/name;p.write_text('#!/bin/sh\ntouch "$AFT_EXECUTION_MARKER"\nexit 97\n');p.chmod(0o700)
        bad=r/'wrong-archive';bad.write_bytes(b'not the approved archive')
        p=subprocess.run(['bash',str(HERE/'recipes/extract-vm.sh'),str(bad)],env=dict(env,PATH=str(tools)+os.pathsep+os.environ['PATH']),capture_output=True,text=True)
        assert p.returncode!=0 and not (r/'executed').exists()
        checks.append({'script':'extract-vm.sh','failure':'bad-hash-before-sudo-or-tar','passed':True,'exit':p.returncode})
    result={'scope':'native Bash/sha256sum with own failed-download stubs; no real download/install','checks':checks}
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.report:args.report.write_text(encoded)
    print(encoded)

if __name__=='__main__':main()
