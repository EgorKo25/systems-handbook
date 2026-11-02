#!/usr/bin/env python3
"""Native local Argo RBAC + pinned renderers + upstream structural schemas.
No Argo API operation, real Kubernetes request, cluster changes or git commits.
Requires explicit ARGOCD_BIN, KUSTOMIZE_BIN, HELM_BIN; PyYAML and jsonschema.
GO_BIN optional. Downloaded runtimes must remain outside the public lab.
"""
from pathlib import Path
import copy,hashlib,json,os,shutil,socketserver,statistics,subprocess,sys,tempfile,threading,time
import yaml,jsonschema
BASE=Path(__file__).resolve().parent
bins={name:os.environ.get(name) for name in ['ARGOCD_BIN','KUSTOMIZE_BIN','HELM_BIN']}
if not all(p and Path(p).is_file() for p in bins.values()):raise SystemExit('Set ARGOCD_BIN,KUSTOMIZE_BIN,HELM_BIN to verified pinned executables')
results=[];skipped=[]
source_dir=BASE.parent/'sources'
if source_dir.exists() and not source_dir.is_dir():
    raise SystemExit('Expected author sources directory or its complete absence in a reading export')
mode='source-checkout' if source_dir.is_dir() else 'reading-export'
with tempfile.TemporaryDirectory(prefix='argocd-local-check-') as tmp:
    root=Path(tmp);(root/'home').mkdir();(root/'empty-kubeconfig').write_text('')
    env=dict(os.environ,HOME=str(root/'home'),KUBECONFIG=str(root/'empty-kubeconfig'),
        XDG_CONFIG_HOME=str(root/'config'),HELM_CONFIG_HOME=str(root/'helm-config'),
        HELM_CACHE_HOME=str(root/'helm-cache'),HELM_DATA_HOME=str(root/'helm-data'))
    env.pop('ARGOCD_AUTH_TOKEN',None);env.pop('ARGOCD_SERVER',None)
    def run(argv,code=0,cwd=None):
        p=subprocess.run(list(map(str,argv)),env=env,cwd=cwd,text=True,capture_output=True,timeout=30)
        assert p.returncode==code,(argv[:4],p.returncode,p.stderr[:1000],p.stdout[:1000]);return p
    def record(name):results.append({'test':name,'status':'PASS'})
    argo=bins['ARGOCD_BIN'];kustomize=bins['KUSTOMIZE_BIN'];helm=bins['HELM_BIN']
    argo_version=run([argo,'version','--client','--short']).stdout.strip()
    helm_version=run([helm,'version','--short']).stdout.strip()
    kustomize_version=run([kustomize,'version']).stdout.strip()
    assert argo_version=='argocd: v3.5.6+c2b1e30'
    assert helm_version.startswith('v4.2.1+') and kustomize_version=='v5.8.1'
    record('pinned-native-versions')
    no_client=[argo,'--config',str(root/'absent-client-config')]
    for value in ['180s','-1']:
        bad=run([*no_client,'app','sync','ledger-gitops','--timeout',value],code=1)
        assert 'invalid argument' in bad.stdout and 'ParseUint' in bad.stdout
    bad=run([*no_client,'--context','handbook-admin','app','get','ledger-gitops'],code=1)
    assert 'unknown flag: --context' in bad.stdout
    local_only=root/'local-diff-without-server';local_only.mkdir()
    bad=run([*no_client,'app','diff','ledger-gitops','--local',local_only],code=1)
    assert 'server address unspecified' in bad.stderr
    record('native-invalid-timeout-context-scope-and-local-diff-server-boundary')
    requests=[]
    class Trap(socketserver.BaseRequestHandler):
        def handle(self):
            requests.append(True)
            self.request.sendall(b'HTTP/1.1 500 Unexpected network request\r\nContent-Length: 0\r\n\r\n')
    with socketserver.TCPServer(('127.0.0.1',0),Trap) as trap:
        thread=threading.Thread(target=trap.serve_forever,daemon=True);thread.start()
        server='http://127.0.0.1:'+str(trap.server_address[1])
        common=['--kubeconfig',env['KUBECONFIG'],'--server',server,'--token','offline-dummy']
        prefix=[argo,'--config',str(root/'absent-argocd-config'),'admin','settings','rbac']
        run([*prefix,'validate','--policy-file',BASE/'rbac/policy.csv',*common])
        run([*prefix,'validate','--policy-file',BASE/'rbac/argocd-rbac-cm.yaml',*common])
        run([*prefix,'validate','--policy-file',BASE/'rbac/invalid.csv',*common],code=1)
        record('native-rbac-csv-configmap-positive-and-negative')
        cases=[('reader','get','applications','ledger/ledger-gitops',True),
          ('reader','sync','applications','ledger/ledger-gitops',False),
          ('releaser','sync','applications','ledger/ledger-gitops',True),
          ('releaser','delete','applications','ledger/ledger-gitops',False),
          ('releaser','sync','applications','other/ledger-gitops',False),
          ('releaser','sync','applications','ledger/another',False)]
        for subject,action,resource,obj,allowed in cases:
            p=run([*prefix,'can',subject,action,resource,obj,'--policy-file',BASE/'rbac/policy.csv','--use-builtin-policy=false',*common],code=0 if allowed else 1)
            assert p.stdout.strip()==('Yes' if allowed else 'No')
        record('native-rbac-read-sync-deny-project-boundaries')
        spaced=root/'policy with spaces.csv';shutil.copyfile(BASE/'rbac/policy.csv',spaced)
        run([*prefix,'can','reader','get','app','ledger/ledger-gitops','--policy-file',spaced,'--use-builtin-policy=false',*common])
        record('native-resource-alias-and-file-path-with-spaces')
        with spaced.open('a') as f:f.write('g, --reader, role:observer\n')
        run([*prefix,'can','--policy-file',spaced,'--use-builtin-policy=false',*common,'--','--reader','get','applications','ledger/ledger-gitops'])
        record('native-double-dash-preserves-subject-operand')
        # Cobra accepts the leaf-local Kubernetes --server even before admin.
        run([argo,'--config',str(root/'absent-client'),'--server',server,'admin','settings','rbac','can','reader','get','applications','ledger/ledger-gitops','--policy-file',BASE/'rbac/policy.csv','--kubeconfig',env['KUBECONFIG'],'--token','offline-dummy','--use-builtin-policy=false'])
        record('native-parent-position-leaf-server-shadow')
        trap.shutdown();thread.join(timeout=2)
        assert not requests,requests
    record('zero-kubernetes-or-argo-requests-trap')
    def parsed(text):return [x for x in yaml.safe_load_all(text) if x]
    def kind(docs,name):return next(x for x in docs if x['kind']==name)
    def render(path):return run([kustomize,'build',path]).stdout
    gitops=root/'gitops';shutil.copytree(BASE/'gitops',gitops)
    overlay=gitops/'apps/ledger/overlays/lab';base=gitops/'apps/ledger/base'
    raw=render(overlay);docs=parsed(raw)
    assert len(docs)==3
    deploy=kind(docs,'Deployment');service=kind(docs,'Service');config=kind(docs,'ConfigMap')
    assert all(x['metadata']['namespace']=='gitops-lab' for x in docs)
    assert deploy['metadata']['name']==service['metadata']['name']=='ledger-gitops'
    assert service['spec']['selector']==deploy['spec']['selector']['matchLabels']==deploy['spec']['template']['metadata']['labels']
    container=deploy['spec']['template']['spec']['containers'][0]
    assert container['envFrom'][0]['configMapRef']['name']==config['metadata']['name']
    assert config['data']['MESSAGE']=='Hello from GitOps lab'
    assert container['ports'][0]['containerPort']==8080
    record('native-kustomize-three-objects-and-service-config-contract')
    assert raw==render(overlay);record('native-render-byte-reproducibility')
    # Same continuing tree, no reset: message changes generated ConfigMap name and Pod reference.
    k=overlay/'kustomization.yaml';k.write_text(k.read_text().replace('Hello from GitOps lab','Next observed message'))
    changed=parsed(render(overlay));new_cfg=kind(changed,'ConfigMap');new_dep=kind(changed,'Deployment')
    assert new_cfg['metadata']['name']!=config['metadata']['name']
    assert new_dep['spec']['template']['spec']['containers'][0]['envFrom'][0]['configMapRef']['name']==new_cfg['metadata']['name']
    assert new_dep['spec']['selector']==deploy['spec']['selector']
    record('continuing-tree-config-hash-causes-new-pod-template')
    settings=yaml.safe_load(k.read_text());settings['patches']=[{'path':'not-ready.patch.yaml'}]
    shutil.copyfile(BASE/'fixtures/not-ready.patch.yaml',overlay/'not-ready.patch.yaml');k.write_text(yaml.safe_dump(settings,sort_keys=False))
    broken=parsed(render(overlay));broken_container=kind(broken,'Deployment')['spec']['template']['spec']['containers'][0]
    assert broken_container['readinessProbe']['httpGet']['path']=='/missing-readyz'
    assert kind(broken,'ConfigMap')['data']['MESSAGE']=='Next observed message'
    record('continuing-tree-readiness-fault-does-not-erase-config')
    # This is a text diff, explicitly not Argo normalization/diff/admission.
    before=root/'before.yaml';after=root/'after.yaml';before.write_text(raw);after.write_text(yaml.safe_dump_all(broken,sort_keys=False))
    run(['git','diff','--no-index','--',before,after],code=1);record('native-git-text-diff-without-commit-or-push')
    for name,path in [('Application','bootstrap/application.template.yaml'),('AppProject','bootstrap/project.template.yaml'),('ApplicationSet','bootstrap/applicationset.template.yaml')]:
        obj=yaml.safe_load((BASE/path).read_text());schema=json.loads((BASE/'schemas'/f'{name}.json').read_text())
        jsonschema.Draft7Validator(schema).validate(obj)
        bad=copy.deepcopy(obj)
        if name=='Application':bad['spec']['source']['targetRevision']=123
        elif name=='AppProject':bad['spec']['sourceRepos']=42
        else:bad['spec']['goTemplate']='true'
        assert list(jsonschema.Draft7Validator(schema).iter_errors(bad))
    record('official-crd-structural-positive-and-negative-subset')
    app=yaml.safe_load((BASE/'bootstrap/application.template.yaml').read_text());project=yaml.safe_load((BASE/'bootstrap/project.template.yaml').read_text())
    assert app['spec']['destination'] in project['spec']['destinations']
    assert project['spec']['clusterResourceWhitelist']==[]
    assert not app['metadata'].get('finalizers')
    assert app['spec']['syncPolicy']['automated']['enabled'] is False
    assert app['spec']['syncPolicy']['syncOptions']==['FailOnSharedResource=true']
    record('manual-project-destination-and-no-adoption-contract')
    fleet=yaml.safe_load((BASE/'bootstrap/applicationset.template.yaml').read_text())
    assert fleet['spec']['template']['spec']['source']['path']=='apps/ledger/base'
    assert all('namespace' not in d['metadata'] for d in parsed(render(base)))
    assert fleet['spec']['syncPolicy']['preserveResourcesOnDeletion'] is True
    record('fleet-source-has-no-hardcoded-destination-namespace')
    chart=BASE/'renderers/helm'
    run([helm,'lint',chart,'--strict'])
    h=parsed(run([helm,'template','ledger-gitops-render',chart,'--namespace','gitops-lab']).stdout)
    assert kind(h,'ConfigMap')['data']['MESSAGE']=='Hello from Helm renderer'
    run([helm,'template','ledger-gitops-render',chart,'--set','message=true'],code=1)
    record('native-bundled-helm-positive-and-schema-negative')
    destination=root/'bootstrap configured'
    run([sys.executable,BASE/'configure.py','--repo','https://git.example.org/reader/ledger-config.git','--revision','a'*40,'--output',destination])
    configured=yaml.safe_load((destination/'application.yaml').read_text())
    assert configured['spec']['source']['targetRevision']=='a'*40
    run([sys.executable,BASE/'configure.py','--repo','https://git.example.org/reader/ledger-config.git','--revision','b'*40,'--output',destination],code=2)
    record('configure-is-reviewable-and-refuses-silent-overwrite')
    fleet_out=root/'configured-fleet'
    run([sys.executable,BASE/'configure.py','--fleet','--repo','https://git.example.org/reader/ledger-config.git','--revision','b'*40,'--output',fleet_out])
    fleet_cfg=yaml.safe_load((fleet_out/'applicationset.yaml').read_text())
    assert fleet_cfg['spec']['template']['spec']['source']['targetRevision']=='b'*40
    assert fleet_cfg['spec']['template']['spec']['destination']['namespace']=='{{ .namespace }}'
    record('fleet-configure-preserves-generator-template-and-owned-source')
    samples=[]
    for _ in range(10):
        t=time.perf_counter();render(overlay);samples.append((time.perf_counter()-t)*1000)
    metrics={'runs':10,'objects':3,'rendered_bytes_initial':len(raw.encode()),'median_ms':round(statistics.median(samples),2),'min_ms':round(min(samples),2),'max_ms':round(max(samples),2),'scope':'process + native local Kustomize build, no repo-server/API/network'}
    run([sys.executable,BASE/'test_guards.py'])
    record('fake-kubectl-29-failure-paths-and-bash-syntax')
    if source_dir.is_dir():
        # A partial checkout is an error: test_snippets requires all expected HTML.
        run([sys.executable,BASE/'test_snippets.py'])
        record('html-executable-bash-syntax-without-execution')
    else:
        reason='Source-only HTML syntax check: author sources/ is omitted from the reading export or standalone labs copy; no HTML syntax evidence was collected'
        skipped.append({'test':'html-executable-bash-syntax-without-execution','status':'SKIPPED','reason':reason})
        print('SKIPPED: '+reason)

    if os.environ.get('BUNDLE_FIXTURE_DIR'):
        run([sys.executable,BASE/'test_bundle.py'])
        record('real-bundle-hashes-tamper-missing-and-tool-extraction')
    go=os.environ.get('GO_BIN')
    if go:
        p=subprocess.run([go,'test','-race','-count=1','./...'],cwd=BASE/'service',env=dict(env,GOTOOLCHAIN='local',GOCACHE=str(root/'go-cache')),text=True,capture_output=True,timeout=120)
        assert p.returncode==0,p.stderr
        record('go-service-contract-concurrency-graceful-race')
    report={'date':'2026-11-01','argocd':argo_version,'helm':helm_version,'kustomize':kustomize_version,'mode':mode,'groups':len(results),'results':results,'skipped':skipped,'metrics':metrics,'api_requests_observed':len(requests),'server_tests_executed':False,'limits':['jsonschema is structural subset, not Kubernetes admission','git --no-index is text diff, not Argo normalization','ApplicationSet templates were not generated by a running controller','Argo install/sync/health/rollback/export/restore not executed']}
    (BASE/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
