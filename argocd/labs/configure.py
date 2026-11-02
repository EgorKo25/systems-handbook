#!/usr/bin/env python3
"""Make reviewable bootstrap files only; never call Kubernetes or Argo CD."""
from pathlib import Path
import argparse,re,yaml
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--revision',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--fleet',action='store_true')
a=p.parse_args()
if '.invalid' in a.repo or not (a.repo.startswith('https://') or a.repo.startswith('ssh://')):
 p.error('Use your existing HTTPS or ssh:// repository, not the example placeholder')
if not re.fullmatch('[0-9a-f]{40}',a.revision):p.error('A full 40-character Git commit is required')
root=Path(__file__).resolve().parent
if a.output.exists() and any(a.output.iterdir()):p.error('Output must be absent or empty; do not silently overwrite persistent config')
a.output.mkdir(parents=True,exist_ok=True)
for name in (['project-fleet','applicationset'] if a.fleet else ['project','application']):
 obj=yaml.safe_load((root/'bootstrap'/f'{name}.template.yaml').read_text())
 if name.startswith('project'):obj['spec']['sourceRepos']=[a.repo]
 else:
  spec=obj['spec']['template']['spec'] if a.fleet else obj['spec']
  spec['source']['repoURL']=a.repo;spec['source']['targetRevision']=a.revision
 (a.output/f'{name}.yaml').write_text(yaml.safe_dump(obj,sort_keys=False))
print('Created reviewable bootstrap files; no cluster operation was executed.')
