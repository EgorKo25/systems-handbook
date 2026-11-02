#!/usr/bin/env python3
"""Local Helm 4.3.1 tests without cluster actions.
The main chart uses local inputs; optional Go tests listen on their own loopback.
Requires PyYAML, explicit HELM_BIN. GO_BIN optionally runs Go contract tests.
All mutable Helm directories and dependency/chart copies live in TemporaryDirectory.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, json, os, shutil, statistics, subprocess, tempfile, time
import yaml

BASE=Path(__file__).resolve().parent
HELM=os.environ.get('HELM_BIN')
if not HELM or not Path(HELM).is_file():
    raise SystemExit('Set HELM_BIN to a verified Helm 4.3.1 executable')
results=[]
with tempfile.TemporaryDirectory(prefix='helm-ledger-check-') as td:
    root=Path(td)
    env=dict(os.environ, KUBECONFIG=str(root/'absent-kubeconfig'),
      HELM_CONFIG_HOME=str(root/'config'),HELM_CACHE_HOME=str(root/'cache'),
      HELM_DATA_HOME=str(root/'data'), HELM_CONTENT_CACHE=str(root/'content'),
      HELM_REGISTRY_CONFIG=str(root/'config/registry.json'),
      HELM_REPOSITORY_CONFIG=str(root/'config/repositories.yaml'),
      HELM_REPOSITORY_CACHE=str(root/'cache/repository'),
      HELM_PLUGINS=str(root/'plugins'), HELM_DRIVER='secret')
    def run(args, ok=True):
        p=subprocess.run([HELM,*map(str,args)],env=env,capture_output=True,text=True)
        if (p.returncode==0)!=ok:
            raise AssertionError(f'Unexpected exit for {args[:3]}: {p.stderr[:1200]}')
        return p
    version=run(['version','--short']).stdout.strip()
    assert version.startswith('v4.3.1+'),version
    chart=BASE/'chart'
    def render(*args, chart_path=chart, ok=True):
        return run(['template','ledger',chart_path,'--namespace','helm-lab','--kube-version','1.36.6',*args],ok)
    def parsed(output):
        return [d for d in yaml.safe_load_all(output) if d]
    def kind(docs,k): return next(d for d in docs if d['kind']==k)
    def pod(docs): return kind(docs,'Deployment')['spec']['template']
    def config(docs): return kind(docs,'ConfigMap')['data']
    def record(name): results.append({'test':name,'status':'PASS'})
    run(['lint',chart,'--strict','--kube-version','1.36.6']); record('lint-strict')
    raw=render().stdout; docs=parsed(raw)
    assert len(docs)==4 and {d['kind'] for d in docs}=={'Deployment','Service','ConfigMap','Pod'}
    assert kind(docs,'Deployment')['spec']['replicas']==2
    assert kind(docs,'Service')['spec']['selector']==kind(docs,'Deployment')['spec']['selector']['matchLabels']
    assert pod(docs)['spec']['containers'][0]['readinessProbe']['httpGet']['path']=='/readyz'
    record('baseline-four-objects-and-label-service-contract')
    assert raw==render().stdout; record('byte-reproducible-render')
    prod=parsed(render('-f',BASE/'fixtures/prod.yaml','-f',BASE/'fixtures/last.yaml').stdout)
    rev=parsed(render('-f',BASE/'fixtures/last.yaml','-f',BASE/'fixtures/prod.yaml').stdout)
    assert kind(prod,'Deployment')['spec']['replicas']==1 and kind(rev,'Deployment')['spec']['replicas']==3
    assert pod(prod)['spec']['containers'][0]['resources']['requests']=={'cpu':'100m','memory':'32Mi'}
    record('file-order-and-map-recursion')
    assert kind(parsed(render('-f',BASE/'fixtures/prod.yaml','--set','replicaCount=4').stdout),'Deployment')['spec']['replicas']==4
    record('set-overrides-files')
    for args in [('-f',BASE/'fixtures/wrong-replicas.yaml'),('-f',BASE/'fixtures/wrong-env.yaml'),('--set-string','replicaCount=3'),('--set','replicaCount=0'),('--set','service.targetPort=9090')]:
        p=render(*args,ok=False); assert 'schema' in p.stderr.lower()
    record('five-schema-negative-cases')
    p=render('--set','credentials.create=true',ok=False); assert 'credentials.token is required' in p.stderr
    p=render('--set','credentials.create=true','--set','credentials.existingSecret=external',ok=False); assert 'mutually exclusive' in p.stderr
    record('required-and-mutual-exclusion-negative-cases')
    token=parsed(render('--set','credentials.create=true','--set-file',f'credentials.token={BASE}/fixtures/token.txt').stdout)
    assert base64.b64decode(kind(token,'Secret')['data']['token'])==(BASE/'fixtures/token.txt').read_bytes()
    assert 'checksum/credentials' in pod(token)['metadata']['annotations']
    record('set-file-preserves-newline-base64-and-checksum')
    # Different flag families are processed in a fixed family order, not argv order.
    for flags in [('--set-string','config.message=text','--set-json','config.message="json"'),('--set-json','config.message="json"','--set-string','config.message=text')]:
        assert config(parsed(render(*flags).stdout))['MESSAGE']=='text'
    record('mixed-set-family-order')
    arr=parsed(render('--set-json','extraEnv=[{"name":"TRACE","value":"true"}]','--set-json','extraEnv=[{"name":"MODE","value":"lab"}]').stdout)
    assert pod(arr)['spec']['containers'][0]['env'][-1]=={'name':'MODE','value':'lab'}
    record('list-replaced-not-appended')
    labels=parsed(render('--set',r'extraLabels.handbook\.example/owner=reader').stdout)
    assert pod(labels)['metadata']['labels']['handbook.example/owner']=='reader'
    render('--set',r'extraLabels.app\.kubernetes\.io/name=other',ok=False)
    record('escaped-dot-and-protected-selector')
    notready=parsed(render('-f',BASE/'fixtures/not-ready.yaml').stdout)
    assert pod(notready)['spec']['containers'][0]['readinessProbe']['httpGet']['path']=='/missing-readyz'
    assert pod(notready)['metadata']['annotations']['checksum/config']==pod(docs)['metadata']['annotations']['checksum/config']
    changed=parsed(render('--set-string','config.message=changed').stdout)
    assert pod(changed)['metadata']['annotations']['checksum/config']!=pod(docs)['metadata']['annotations']['checksum/config']
    record('readiness-path-and-config-rollout-checksum')
    storage=parsed(render('-f',BASE/'fixtures/storage.yaml').stdout)
    assert kind(storage,'PersistentVolumeClaim')['metadata']['annotations']['helm.sh/resource-policy']=='keep'
    assert kind(storage,'Deployment')['spec']['strategy']=={'type':'Recreate'}
    assert kind(storage,'PersistentVolumeClaim')['spec']['storageClassName']=='helm-local'
    assert kind(storage,'PersistentVolumeClaim')['spec']['resources']['requests']['storage']=='128Mi'
    local_docs=parsed((BASE/'recipes/vm-local-storage.yaml').read_text())
    assert kind(local_docs,'StorageClass')['provisioner']=='kubernetes.io/no-provisioner'
    local_pv=kind(local_docs,'PersistentVolume')
    assert local_pv['spec']['claimRef']=={'namespace':'helm-lab','name':'ledger-ledger-api-data'}
    assert local_pv['spec']['capacity']['storage']=='256Mi'
    render('--set','persistence.enabled=true',ok=False)
    record('storage-one-replica-and-keep-policy')
    digest='sha256:'+'a'*64
    dig=parsed(render('--set-string','image.digest='+digest).stdout)
    assert pod(dig)['spec']['containers'][0]['image']=='ledger-api@'+digest
    record('image-digest-precedes-tag')
    # Source/template failure is distinguished from values schema failure.
    broken=root/'broken';shutil.copytree(chart,broken)
    (broken/'templates/broken.yaml').write_text('{{ if }}\n')
    p=render(chart_path=broken,ok=False); assert 'parse error' in p.stderr
    record('template-parse-negative-case')
    # Dependency update creates a lock in a disposable copy only.
    dep=root/'dependency';dep.mkdir()
    cp=dep/'chart';shutil.copytree(chart,cp)
    shutil.copytree(BASE/'dependency/lab-labels',dep/'lab-labels')
    (cp/'Chart.yaml').write_text((cp/'Chart.yaml').read_text()+'dependencies:\n  - name: lab-labels\n    version: 0.1.0\n    repository: file://../lab-labels\n')
    run(['dependency','update',cp]); lock=(cp/'Chart.lock').read_bytes()
    shutil.rmtree(cp/'charts');run(['dependency','build',cp])
    assert (cp/'Chart.lock').read_bytes()==lock
    assert parsed(render(chart_path=cp).stdout)==docs
    record('local-dependency-lock-build-without-network')
    packages=root/'packages';packages.mkdir()
    run(['package',chart,'--destination',packages])
    package=packages/'ledger-api-0.1.0.tgz'
    assert parsed(render(chart_path=package).stdout)==docs
    with __import__('tarfile').open(package) as archive:
        assert archive.extractfile('ledger-api/files/operator-note.txt').read()==(chart/'files/operator-note.txt').read_bytes()
    ignored=root/'ignored';shutil.copytree(chart,ignored)
    (ignored/'test-secret.private').write_text('dummy-excluded-content')
    (ignored/'.helmignore').write_text((ignored/'.helmignore').read_text()+'test-secret.private\n')
    run(['package',ignored,'--destination',packages])
    with __import__('tarfile').open(package) as archive:
        assert 'ledger-api/test-secret.private' not in archive.getnames()
    record('package-and-rendered-object-equivalence')
    # Tiny independent template exercise: types, scopes and include return string.
    types=root/'types';(types/'templates').mkdir(parents=True)
    (types/'Chart.yaml').write_text('apiVersion: v2\nname: types\nversion: 0.1.0\n')
    (types/'values.yaml').write_text('flag: false\ncount: 0\nitems: [a, b]\n')
    (types/'templates/types.yaml').write_text("""{{- define "types.part" -}}{{ .name }}{{- end -}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: types
data:
  flagKind: {{ kindOf .Values.flag | quote }}
  defaultFalse: {{ default true .Values.flag | toString | quote }}
  rootRelease: {{ with .Values.items }}{{ $.Release.Name | quote }}{{ end }}
  includeKind: {{ include "types.part" (dict "name" "hi") | kindOf | quote }}
  zeroEmpty: {{ empty .Values.count | toString | quote }}
  emptyDict: {{ empty (dict) | toString | quote }}
  nonemptyDict: {{ empty (dict "k" "v") | toString | quote }}
  emptyList: {{ empty (list) | toString | quote }}
  nonemptyList: {{ empty (list 1) | toString | quote }}
  invalidInt: {{ int "not-an-int" | toString | quote }}
  yamlError: {{ hasKey (fromYaml "x: [") "Error" | toString | quote }}
""")
    type_data=config(parsed(render(chart_path=types).stdout))
    assert type_data=={'flagKind':'bool','defaultFalse':'true','rootRelease':'ledger','includeKind':'string','zeroEmpty':'true','emptyDict':'true','nonemptyDict':'false','emptyList':'true','nonemptyList':'false','invalidInt':'0','yamlError':'true'}
    record('types-default-false-root-and-include')
    samples=[]
    for _ in range(10):
        start=time.perf_counter();render();samples.append((time.perf_counter()-start)*1000)
    metrics={'runs':len(samples),'objects_including_test_hook':len(docs),'rendered_bytes':len(raw.encode()),'median_wall_ms':round(statistics.median(samples),2),'min_wall_ms':round(min(samples),2),'max_wall_ms':round(max(samples),2),'scope':'CLI process + local render, no API/network; environment-specific'}
    go=os.environ.get('GO_BIN')
    if go:
        goenv=dict(env,GOCACHE=str(root/'gocache'),GOTOOLCHAIN='local',
          GOENV='off',GOWORK='off',GOFLAGS='',GOPATH=str(root/'gopath'),
          GOMODCACHE=str(root/'gomodcache'),GOPROXY='off',GOSUMDB='off')
        p=subprocess.run([go,'test','-mod=readonly','./...'],cwd=BASE/'service',env=goenv,capture_output=True,text=True)
        assert p.returncode==0,p.stderr
        record('go-http-contract-tests')
    report={'date':datetime.now(timezone.utc).date().isoformat(),'helm':version,'test_groups':len(results),'results':results,'metrics':metrics,'cluster_executed':False,'not_executed':['API admission','install','upgrade','hooks/test Pod execution','rollback','PVC binding','OCI remote push','binary GPG signature verification']}
    report_path = os.environ.get('HELM_CHECK_REPORT')
    if report_path:
        with Path(report_path).open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
