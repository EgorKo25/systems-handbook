#!/usr/bin/env python3
"""Prepare optional serving TLS hardening artifacts. Offline; no cluster mutation."""
import argparse,base64,copy,hashlib,json
from pathlib import Path
import yaml
EXPECTED='3c7f57cdbee0f57fb0259a150e8f6d6cb4f29d72d1aa5dce8803151dd6d4c2a1'
def prepare(source,ca):
 if hashlib.sha256(source).hexdigest()!=EXPECTED:raise ValueError('expected exact upstream metrics-server0.9.1 components.yaml')
 docs=[x for x in yaml.safe_load_all(source) if x]
 dep=copy.deepcopy(next(x for x in docs if x['kind']=='Deployment' and x['metadata']['name']=='metrics-server'))
 pod=dep['spec']['template']['spec'];c=next(x for x in pod['containers'] if x['name']=='metrics-server')
 c['args']+=[ '--tls-cert-file=/serving-tls/tls.crt','--tls-private-key-file=/serving-tls/tls.key' ]
 c.setdefault('volumeMounts',[]).append({'name':'serving-tls','mountPath':'/serving-tls','readOnly':True})
 pod.setdefault('volumes',[]).append({'name':'serving-tls','secret':{'secretName':'metrics-server-serving','defaultMode':0o440}})
 pod.setdefault('securityContext',{})['fsGroup']=2000
 if b'BEGIN CERTIFICATE' not in ca or b'PRIVATE KEY' in ca:raise ValueError('CA file must contain PEM certificate(s), not a private key')
 patch={'spec':{'insecureSkipTLSVerify':False,'caBundle':base64.b64encode(ca).decode()}}
 return dep,patch
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('source',type=Path);a.add_argument('ca',type=Path);a.add_argument('output',type=Path);n=a.parse_args();dep,patch=prepare(n.source.read_bytes(),n.ca.read_bytes());n.output.mkdir(parents=True,exist_ok=False)
 (n.output/'metrics-deployment-tls.yaml').write_text(yaml.safe_dump(dep,sort_keys=False))
 (n.output/'metrics-apiservice-ca.json').write_text(json.dumps(patch,indent=2)+'\n')
