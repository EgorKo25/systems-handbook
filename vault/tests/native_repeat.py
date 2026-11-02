#!/usr/bin/env python3
"""Explicit independent repeat in a NEW owned persistent test root; never resets reader state."""
import argparse, importlib.util, json, os, pathlib, signal, socket, ssl, subprocess, sys, time, urllib.request
HERE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE/'labs'))
import lab, pg_lab

def freeport():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vault',type=pathlib.Path,required=True);p.add_argument('--work-root',type=pathlib.Path,required=True);p.add_argument('--pg-bin',type=pathlib.Path);a=p.parse_args()
root=a.work_root.expanduser().resolve()
if root.exists():raise SystemExit('work-root already exists; choose a NEW target, no deletion/reset is performed')
os.umask(0o077);root.mkdir(parents=True,mode=0o700)
source=root/'source';target=root/'restore';checks=[];started=[];pg_started=False
try:
    lab.prepare(source,a.vault.expanduser().resolve(),freeport(),freeport());lab.start(source);started.append(source)
    code,state=lab.request(source,'sys/health');assert code==501 and not state['initialized'];checks.append('new TLS server initialized=false')
    lab.initialize(source);lab.provision(source);lab.checks(source);checks.append('13 ACL/KV/TTL native assertions')
    lab.approle(source);lab.pki(source);lab.agent(source);checks.extend(['AppRole once-only wrapping/login','PKI intermediate/leaf/revoke','one-shot Agent native template0600'])
    # Native alias and position checks; the query parser is not substituted for CLI.
    lab.cli(source,['kv','get','--mount=secret','handbook/config']);checks.append('native --mount alternate accepted')
    denied=lab.cli(source,['kv','get','-mount=secret','handbook/config','-format=json'],want=1);checks.append('native flag after operand rejected')
    r=subprocess.run([str(a.vault.expanduser().resolve()),'-address=https://127.0.0.1:1','kv','get','-mount=secret','handbook/config'],capture_output=True,text=True)
    assert r.returncode!=0;checks.append('HTTP flag before subcommand rejected by actual CLI')
    for alias in ('-f','-force'):lab.cli(source,['write',alias,'-format=json','auth/approle/role/handbook/secret-id'],json_output=True)
    checks.append('native write -f and -force aliases')
    # Same starting states, same intervening write; only CAS protection differs.
    for key in ('compare-cas','compare-unconditional'):
        lab.cli(source,['kv','put','-mount=secret',key,'value=one'])
        lab.cli(source,['kv','put','-mount=secret',key,'value=two'])
    code,_=lab.request(source,'secret/data/compare-cas',{'options':{'cas':1},'data':{'value':'stale'}},lab.operator(source));assert code==400
    lab.cli(source,['kv','put','-mount=secret','compare-unconditional','value=stale'])
    v1=lab.cli(source,['kv','get','-mount=secret','-format=json','compare-cas'],json_output=True)
    v2=lab.cli(source,['kv','get','-mount=secret','-format=json','compare-unconditional'],json_output=True)
    assert v1['data']['data']['value']=='two' and v2['data']['data']['value']=='stale';checks.append('matched-state CAS rejects stale write while unconditional loses intervening value')
    # Deny + allow on exactly the same path, not just default-deny.
    code,_=lab.request(source,'sys/policies/acl/extra-allow',{'policy':'path "secret/data/handbook/forbidden" { capabilities=["read"] }'},lab.operator(source),method='PUT');assert code==204
    t=lab.cli(source,['token','create','-policy=handbook-reader','-policy=extra-allow','-ttl=1m','-format=json'],json_output=True)['auth']['client_token']
    code,_=lab.request(source,'secret/data/handbook/forbidden',token=t);assert code==403;checks.append('exact-path deny overrides second-policy allow')
    lab.snapshot(source,'accepted.snap')
    lab.cli(source,['kv','put','-mount=secret','-cas=3','handbook/config','message=after-snapshot'])
    lab.prepare(target,a.vault.expanduser().resolve(),freeport(),freeport());lab.start(target);started.append(target);lab.restore(target,source,'accepted.snap')
    assert json.loads((target/'restore-complete.json').read_text())['restored_version']==3
    assert lab.cli(source,['kv','get','-mount=secret','-format=json','handbook/config'],json_output=True)['data']['metadata']['version']==4
    checks.append('restore target3 / source4; later source write survives only on source')
    # Restart source retains version4 but requires Shamir unseal again.
    old=int((source/'server.pid').read_text());os.kill(lab.ensure_own_process(source),signal.SIGTERM)
    for _ in range(100):
        if pathlib.Path(f'/proc/{old}/stat').exists() and pathlib.Path(f'/proc/{old}/stat').read_text().split(') ',1)[1].startswith('Z'):break
        if not pathlib.Path(f'/proc/{old}').exists():break
        time.sleep(.1)
    (source/'server.pid').unlink();started.remove(source)
    lab.start(source);started.append(source);code,state=lab.request(source,'sys/health');assert code==503 and state['sealed'];lab.unseal(source)
    assert lab.cli(source,['kv','get','-mount=secret','-format=json','handbook/config'],json_output=True)['data']['metadata']['version']==4;checks.append('restart sealed→unseal→persistent version4')
    if a.pg_bin:
        pg=root/'postgresql';pg_lab.prepare(pg,a.pg_bin.expanduser().resolve(),freeport());pg_lab.start(pg);pg_started=True;pg_lab.bootstrap(pg);pg_lab.check(pg,source);checks.append('10 native PostgreSQL-plugin checkpoints')
    assert not any(root.rglob('.vault-token'));checks.append('no .vault-token generated in test tree')
    report=dict(kind='native isolated repeat, not publication/export/mobile acceptance',checks=checks,count=len(checks),work_root=str(root),pg_tested=bool(a.pg_bin))
    lab.save(root/'report.json',report);print(json.dumps(report,ensure_ascii=False))
finally:
    if a.pg_bin and (root/'postgresql/data').exists():
        subprocess.run([str(a.pg_bin.expanduser().resolve()/'pg_ctl'),'-D',str(root/'postgresql/data'),'-m','fast','-w','stop'],capture_output=True)
    for own in reversed(started):
        # Invoke published helper so its PID/cwd identity guard remains in use.
        subprocess.run([sys.executable,str(HERE/'labs/lab.py'),'--root',str(own),'stop'],capture_output=True)
