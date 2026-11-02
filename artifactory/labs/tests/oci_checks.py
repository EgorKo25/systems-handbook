#!/usr/bin/env python3
"""Native ORAS local OCI layout. No registry, daemon, Artifactory or listeners."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,tempfile

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--oras',required=True);p.add_argument('--report',type=Path);a=p.parse_args()
    report={'date':'2026-11-01','scope':'native ORAS local OCI layout only; not Artifactory push/pull','checks':[]}
    with tempfile.TemporaryDirectory(prefix='artifactory-oras-')as td:
        r=Path(td);env=dict(os.environ,HOME=td)
        def run(args,ok=True):
            q=subprocess.run([str(Path(a.oras).resolve()),*args],cwd=r,env=env,capture_output=True,text=True,timeout=20)
            assert (q.returncode==0)==ok,q.stderr.replace(td,'<temporary>')
            return q
        def passed(name):report['checks'].append({'name':name,'passed':True})
        version=run(['version']).stdout;assert 'Version:        1.3.6' in version
        report['version']='1.3.6'
        payload=b'own receipt fixture\n';(r/'payload.txt').write_bytes(payload)
        (r/'metadata.json').write_text('{"version":"1.0.0"}\n')
        run(['push','--oci-layout','layout:1.0.0','payload.txt:text/plain','metadata.json:application/json',
             '--artifact-type','application/vnd.handbook.receipt.v1','--annotation','org.opencontainers.image.created=2026-11-01T00:00:00Z'])
        descriptor=json.loads(run(['manifest','fetch','--oci-layout','--descriptor','layout:1.0.0']).stdout)
        raw=run(['manifest','fetch','--oci-layout','layout:1.0.0']).stdout
        digest=descriptor['digest'];manifest_path=r/'layout/blobs/sha256'/digest.split(':')[1]
        content=manifest_path.read_bytes()
        assert hashlib.sha256(content).hexdigest()==digest.split(':')[1] and len(content)==descriptor['size']
        manifest=json.loads(content)
        assert manifest['artifactType']=='application/vnd.handbook.receipt.v1' and len(manifest['layers'])==2
        passed('native local push creates descriptor, manifest and two file layers')
        for layer in manifest['layers']:
            b=(r/'layout/blobs/sha256'/layer['digest'].split(':')[1]).read_bytes()
            assert len(b)==layer['size'] and hashlib.sha256(b).hexdigest()==layer['digest'].split(':')[1]
        passed('independent Python validates exact manifest/layer bytes, digests and lengths')
        run(['pull','--oci-layout','layout@'+digest,'--output','received'])
        assert (r/'received/payload.txt').read_bytes()==payload
        assert (r/'received/metadata.json').read_bytes()==(r/'metadata.json').read_bytes()
        passed('native pull by digest restores both exact file bytes')
        target=r/'layout/blobs/sha256'/manifest['layers'][0]['digest'].split(':')[1]
        original=target.read_bytes();target.chmod(0o600);target.write_bytes(b'corrupt bytes')
        run(['pull','--oci-layout','layout@'+digest,'--output','broken'],ok=False)
        passed('native pull rejects corrupted layer bytes')
        target.write_bytes(original);target.unlink()
        run(['pull','--oci-layout','layout@'+digest,'--output','missing'],ok=False)
        passed('native pull rejects missing referenced layer')
        report['manifest_digest']=digest;report['manifest_bytes']=len(content)
        report['payload_sha256']=hashlib.sha256(payload).hexdigest()
    if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
