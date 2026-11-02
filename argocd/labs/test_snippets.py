#!/usr/bin/env python3
"""Syntax-check executable HTML Bash examples without executing a command."""
from pathlib import Path
import html,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
# The export intentionally omits author sources. A standalone invocation must
# reject that absence instead of reporting PASS for an empty glob.
EXPECTED=(
 '00-route','argocd-01-gitops','argocd-02-distribution','argocd-03-install',
 'argocd-04-architecture','argocd-05-application','argocd-06-render',
 'argocd-07-diff-health','argocd-08-sync','argocd-09-waves-hooks',
 'argocd-10-ownership','argocd-11-applicationset','argocd-12-repositories',
 'argocd-13-access','argocd-14-recovery','argocd-15-capacity',
 'argocd-16-offline','argocd-17-lab','argocd-18-diagnostics','argocd-19-sources')
paths=[ROOT/'sources'/f'{name}.html' for name in EXPECTED]
missing=[path.name for path in paths if not path.is_file()]
if missing:
 raise SystemExit('Source-only HTML syntax check requires all20 author sources; missing: '+', '.join(missing))
empty=[path.name for path in paths if not path.read_text().strip()]
if empty:raise SystemExit('Empty author HTML source: '+', '.join(empty))
count=0;data_examples=0
for path in paths:
 for block in re.findall(r'<pre><code>(.*?)</code></pre>',path.read_text(),re.S):
  code=html.unescape(block)
  if code.startswith(('metadata:','spec:','p, ')):
   data_examples+=1;continue
  q=subprocess.run(['bash','-n'],input=code,text=True,capture_output=True)
  assert q.returncode==0,(path.name,q.stderr)
  count+=1
if count==0:raise SystemExit('No executable HTML blocks found; no syntax-check evidence')
print(f'PASS:{count} executable HTML blocks parsed by Bash;{data_examples} YAML/CSV examples excluded. No block executed.')
