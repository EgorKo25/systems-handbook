#!/usr/bin/env python3
"""Offline transform of an exact official source. No kubectl, network or host edits."""
import argparse,hashlib
from pathlib import Path
import yaml
EXPECTED='2de8f47595fb9c41b3f47d7b767a1f8e72ecf84057af834738ff12689a234da5'
def transform(data):
 if hashlib.sha256(data).hexdigest()!=EXPECTED:raise ValueError('Expected exact official Calico v3.33.0 manifest; verify origin before adapting')
 docs=list(yaml.safe_load_all(data))
 found=0
 for d in docs:
  if d and d['kind']=='ConfigMap' and d['metadata']['name']=='calico-config':
   d['data']['calico_backend']='vxlan';d['data']['veth_mtu']='1450'
  if d and d['kind']=='DaemonSet' and d['metadata']['name']=='calico-node':
   c=next(c for c in d['spec']['template']['spec']['containers'] if c['name']=='calico-node')
   env={x['name']:x for x in c['env']}
   for k,v in {'CALICO_IPV4POOL_IPIP':'Never','CALICO_IPV4POOL_VXLAN':'Always','CALICO_IPV4POOL_CIDR':'10.244.0.0/16','CLUSTER_TYPE':'k8s','IP_AUTODETECTION_METHOD':'cidr=192.168.56.0/24','FELIX_BPFENABLED':'false'}.items():
    if k in env:env[k].clear();env[k].update(name=k,value=v)
    else:c['env'].append({'name':k,'value':v})
   for name in ['readinessProbe','livenessProbe']:
    c[name]['exec']['command']=[x for x in c[name]['exec']['command'] if x not in ['--bird-ready','--bird-live']]
   found+=1
 if found!=1:raise ValueError('Expected exactly one calico-node DaemonSet')
 return yaml.safe_dump_all(docs,sort_keys=False)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('source',type=Path);a.add_argument('output',type=Path);n=a.parse_args()
 if n.source.resolve()==n.output.resolve():a.error('output must be a new staged file')
 content=transform(n.source.read_bytes())
 with n.output.open('x',encoding='utf-8') as output:output.write(content)
