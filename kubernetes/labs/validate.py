#!/usr/bin/env python3
"""Offline shape + authored invariants. Never calls an API server."""
from pathlib import Path
import copy,json,sys
import yaml
from jsonschema import Draft4Validator,RefResolver
HERE=Path(__file__).resolve().parent
class UniqueLoader(yaml.SafeLoader):pass
def mapping(loader,node,deep=False):
 result={}
 for k,v in node.value:
  key=loader.construct_object(k,deep=deep)
  if key in result:raise ValueError('duplicate YAML key: '+str(key))
  result[key]=loader.construct_object(v,deep=deep)
 return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
def load(path):return [d for d in yaml.load_all(path.read_text(),Loader=UniqueLoader) if d]
def normalize(x):
 if isinstance(x,dict):
  if x.get('x-kubernetes-int-or-string') or x.get('format') == 'int-or-string':x.pop('type',None);x['anyOf']=[{'type':'integer'},{'type':'string'}]
  for v in list(x.values()):normalize(v)
 elif isinstance(x,list):
  for v in x:normalize(v)
def validator():
 root=json.loads((HERE/'schema/kubernetes-v1.36.6.json').read_text());normalize(root)
 kinds={}
 for name,v in root['definitions'].items():
  for gvk in v.get('x-kubernetes-group-version-kind',[]):
   api=(gvk['group']+'/' if gvk['group'] else '')+gvk['version'];kinds[(api,gvk['kind'])]=name
 def check(obj):
  key=(obj.get('apiVersion'),obj.get('kind'))
  if key not in kinds:raise ValueError('unsupported kind in schema subset: '+str(key))
  errors=list(Draft4Validator(root['definitions'][kinds[key]],resolver=RefResolver.from_schema(root)).iter_errors(obj))
  if errors:raise ValueError('; '.join('/'.join(map(str,e.path))+': '+e.message for e in errors))
 return check
if __name__=='__main__':
 check=validator();objects=[]
 for p in sorted((HERE/'manifests').glob('*.yaml')):
  for obj in load(p):check(obj);objects.append(obj)
 dep=next(x for x in objects if x['kind']=='Deployment');pod=dep['spec']['template']['spec'];c=pod['containers'][0]
 assert dep['spec']['selector']['matchLabels']==dep['spec']['template']['metadata']['labels']
 assert c['readinessProbe']['httpGet']['path']=='/readyz' and c['livenessProbe']['httpGet']['path']=='/livez'
 assert pod['automountServiceAccountToken'] is False and c['securityContext']['allowPrivilegeEscalation'] is False
 try:check(load(HERE/'fixtures/bad-port.yaml')[0])
 except ValueError:pass
 else:raise AssertionError('string Service port must fail static validation')
 broken=copy.deepcopy(dep);broken['spec']['replicas']='two'
 try:check(broken)
 except ValueError:pass
 else:raise AssertionError('replicas must be integer')
 gateway=json.loads((HERE/'schema/gateway-envoy-v1.9.3.json').read_text())
 schemas={(x['apiVersion'],x['kind']):x['schema'] for x in gateway['schemas']}
 for obj in load(HERE/'vm/gateway.yaml'):
  schema=schemas[(obj['apiVersion'],obj['kind'])]
  errors=list(Draft4Validator(schema).iter_errors(obj))
  if errors:raise ValueError('; '.join(e.message for e in errors))
 for obj in load(HERE/'vm/gateway-policy.yaml'):check(obj)
 for obj in load(HERE/'vm/diagnostic.yaml'):check(obj)
 for obj in load(HERE/'vm/workload-patterns.yaml'):check(obj)
 for name in ['scheduling-probe.yaml','ownership-a.yaml','ownership-b.yaml']:
  for obj in load(HERE/'vm'/name):check(obj)
 for path in sorted((HERE/'vm').glob('*.yaml')):load(path)
 print('PASS: 4 optional Gateway/Envoy resources match pinned CRD shape; 11 optional core resources validated; CEL/admission/controller behavior NOT tested')
 print(f'PASS: {len(objects)} authored Kubernetes objects match v1.36.6 OpenAPI subset; two negative cases rejected; API admission and cluster execution NOT tested')
