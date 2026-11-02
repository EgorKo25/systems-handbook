#!/usr/bin/env python3
"""Real CLI tests. Uses a single continuing own temp lab, never a user's state."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from lab import prepare, snapshot, restore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terraform', default='terraform')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    binary = shutil.which(args.terraform)
    if not binary: raise SystemExit('Terraform CLI unavailable; not a simulated pass')
    binary = str(Path(binary).resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith('TF_')}
    env.update(CHECKPOINT_DISABLE='1', TF_IN_AUTOMATION='1', TF_INPUT='0')
    outcomes = []
    def record(name): outcomes.append(name); print('PASS', name, flush=True)
    with tempfile.TemporaryDirectory(prefix='terraform-handbook-check-') as tmp:
        base = Path(tmp)
        # A dedicated empty CLI config avoids inherited provider/backend settings.
        config = base / 'terraform.rc'; config.write_text('disable_checkpoint = true\n')
        env['TF_CLI_CONFIG_FILE'] = str(config)
        root = base / 'lab'; prepare(root)
        def tf(*cmd, expected=0, cwd=None):
            r = subprocess.run([binary, '-chdir=' + str(cwd or root), *cmd],
                               text=True, capture_output=True, env=env, timeout=50)
            if r.returncode != expected:
                raise AssertionError(f'{cmd}: expected {expected}, got {r.returncode}\n{r.stdout}\n{r.stderr}')
            return r
        def params(**kwargs):
            (root / 'case.auto.tfvars.json').write_text(json.dumps(kwargs) + '\n')
        def contract(): return json.loads(tf('output', '-json', 'contract').stdout)
        version = json.loads(subprocess.check_output([binary, 'version', '-json'],env=env,text=True))
        assert version['terraform_version'] == '1.17.1', version
        tf('fmt', '-check', '-recursive'); tf('init', '-input=false'); tf('validate')
        record('1.17.1 / fmt / init / validate without external provider')
        tf('plan', '-out=first.tfplan', '-detailed-exitcode', expected=2)
        tf('apply', '-input=false', 'first.tfplan')
        tf('plan', '-detailed-exitcode')
        first = contract(); assert set(first) == {'api','worker'}
        record('saved plan applied; next plan has exit 0')
        (root / 'rendered-api.json').write_text('{"tampered":true}\n')
        tf('plan', '-detailed-exitcode')
        record('unmanaged provisioner file drift is invisible to terraform_data Read')
        tf('plan', '-replace=terraform_data.service["api"]', '-out=repair.tfplan')
        tf('apply', 'repair.tfplan')
        assert json.loads((root / 'rendered-api.json').read_text())['port'] == 8080
        record('explicit replacement reruns one-shot receipt writer')
        services={'api': {'port':8180,'build':'b1'}, 'worker':{'port':8081,'build':'b1'}}
        before=contract(); params(services=services)
        tf('apply','-auto-approve')
        assert contract()['api']['id']==before['api']['id']
        assert json.loads((root / 'rendered-api.json').read_text())['port']==8080
        record('input update keeps identity; creation provisioner does not rerun')
        source=root/'main.tf'; original=source.read_text()
        source.write_text(original.replace('"service" {','"node" {').replace('terraform_data.service','terraform_data.node')+
                          '\nmoved {\n  from = terraform_data.service\n  to   = terraform_data.node\n}\n')
        ids=contract(); tf('plan','-out=move.tfplan'); tf('apply','move.tfplan')
        assert contract()==ids
        assert 'terraform_data.node["api"]' in tf('state','list').stdout
        tf('plan','-detailed-exitcode')
        record('moved block preserves IDs across block address rename')
        tf('plan','-var=gate_revision=stale','-out=stale.tfplan')
        tf('apply','-auto-approve','-var=gate_revision=intervening')
        stale=tf('apply','stale.tfplan',expected=1)
        assert 'stale' in (stale.stdout+stale.stderr).lower()
        record('saved plan refused after intervening state change')
        params(services=services,gate_revision='lock-test',hold_seconds=3)
        child=subprocess.Popen([binary,'-chdir='+str(root),'apply','-auto-approve'],env=env,
                               text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            for _ in range(200):
                if (root/'.terraform.tfstate.lock.info').exists(): break
                if child.poll() is not None: break
                time.sleep(.025)
            assert (root/'.terraform.tfstate.lock.info').exists(), 'Did not observe local backend lock'
            locked=tf('plan','-lock-timeout=200ms',expected=1)
            assert 'lock' in (locked.stdout+locked.stderr).lower()
        finally:
            out,err=child.communicate(timeout=25)
            assert child.returncode==0,(out,err)
        params(services=services,gate_revision='lock-test')
        tf('plan','-detailed-exitcode')
        record('concurrent plan refused while local apply owns state lock')
        snap=base/'snapshot'; snapshot(root,snap)
        for value in services.values(): value['build']='b2'
        params(services=services,gate_revision='fail-test',fail_gate=True)
        failed=tf('apply','-auto-approve',expected=1)
        assert 'deliberate gate refusal' in failed.stderr+failed.stdout
        raw=json.loads(tf('state','pull').stdout)
        nodes=next(r for r in raw['resources'] if r.get('name')=='node' and not r.get('module'))
        assert all(i['attributes']['input']['value']['build']=='b2' for i in nodes['instances'])
        gate=next(r for r in raw['resources'] if r.get('name')=='gate')
        assert any(i.get('status')=='tainted' for i in gate['instances'])
        record('partial apply preserves changed services and taints failed creation')
        params(services=services,gate_revision='fail-test',fail_gate=False)
        tf('apply','-auto-approve'); tf('plan','-detailed-exitcode')
        record('repair continues same state and converges without reset')
        refusal=tf('state','push',str(snap/'terraform.tfstate'),expected=1)
        assert 'serial' in refusal.stderr+refusal.stdout
        record('state push refuses lower serial; no force bypass')
        restore(root,snap); tf('init','-input=false'); tf('plan','-detailed-exitcode')
        assert contract()['api']['build']=='b1'
        record('explicit full stopped-lab snapshot restore; previous data preserved')
        tf('plan','-replace=terraform_data.node["api"]','-out=destroy-first.tfplan')
        plan=json.loads(tf('show','-json','destroy-first.tfplan').stdout)
        change=next(c for c in plan['resource_changes'] if c['address']=='terraform_data.node["api"]')
        assert change['change']['actions']==['delete','create']
        source.write_text(source.read_text().replace('  for_each         = var.services',
                          '  lifecycle { create_before_destroy = true }\n  for_each         = var.services'))
        tf('plan','-replace=terraform_data.node["api"]','-out=create-first.tfplan')
        plan=json.loads(tf('show','-json','create-first.tfplan').stdout)
        change=next(c for c in plan['resource_changes'] if c['address']=='terraform_data.node["api"]')
        assert change['change']['actions']==['create','delete']
        record('lifecycle changes replacement action order in real plan JSON')
        source.write_text(source.read_text().replace('create_before_destroy = true','prevent_destroy = true'))
        blocked=tf('plan','-replace=terraform_data.node["api"]',expected=1)
        assert 'prevent_destroy' in blocked.stdout+blocked.stderr
        record('prevent_destroy refuses replacement while declaration remains')
        source.write_text(source.read_text().replace('  lifecycle { prevent_destroy = true }\n',''))
        # terraform_data objects have no remote infrastructure; destroy only this owned temp root.
        tf('destroy','-auto-approve'); assert not tf('state','list').stdout.strip()
        record('destroy affects only the isolated continuing test state')
        report={'version':version['terraform_version'],'platform':version['platform'],
                'tests':outcomes,'count':len(outcomes),'external_providers':False,
                'cloud_or_vm_created':False,'network_required_after_cli_download':False}
        if args.report: args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(outcomes)} real CLI checks passed; own temporary test directory removed')

if __name__=='__main__': main()
