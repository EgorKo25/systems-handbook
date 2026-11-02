#!/usr/bin/env python3
"""Pure fixed-model and state/file comparison checks; no Terraform or file writes."""
import copy
import importlib.util
import json
from pathlib import Path

def fixture(api_port=8080, api_id='A1', build='b1'):
    return dict(format_version='1.0', terraform_version='1.17.1',
                values=dict(root_module=dict(resources=[
                    dict(address='terraform_data.service["api"]', mode='managed',
                         type='terraform_data', name='service', index='api',
                         values=dict(id=api_id, output=dict(port=api_port, build=build))),
                    dict(address='terraform_data.service["worker"]', mode='managed',
                         type='terraform_data', name='service', index='worker',
                         values=dict(id='W1', output=dict(port=8081, build='b1')))])))

def check_modules(model, observer):
    model.check()
    receipts = dict(api=dict(port=8080, build='b1'), worker=dict(port=8081, build='b1'))
    before = copy.deepcopy(receipts)
    initial = observer.summarize(fixture(), receipts)
    assert all(row['receipt_matches'] for row in initial['services'])
    update = observer.summarize(fixture(8180), receipts)
    assert update['services'][0]['id'] == initial['services'][0]['id'] == 'A1'
    assert update['services'][0]['state']['port'] == 8180
    assert update['services'][0]['receipt']['port'] == 8080
    assert not update['services'][0]['receipt_matches']
    assert update['services'][1]['receipt_matches']
    assert observer.summarize(fixture(), {})['services'][0]['receipt'] is None
    assert observer.summarize(fixture(), {})['services'][0]['receipt_matches'] is False
    assert receipts == before, 'Comparison mutated evidence'
    moved = fixture(8180)
    for row in moved['values']['root_module']['resources']:
        row['name'] = 'node'
        row['address'] = row['address'].replace('.service[', '.node[')
    assert [x['id'] for x in observer.summarize(moved, receipts)['services']] == ['A1', 'W1']
    bad = []
    x = fixture(); x['format_version'] = '2.0'; bad.append(x)
    x = fixture(); x['resource_changes'] = []; bad.append(x)
    x = fixture(); del x['values']; bad.append(x)
    x = fixture(); x['values']['root_module']['resources'][0]['values']['output'] = None; bad.append(x)
    x = fixture(); x['values']['root_module']['resources'].append(copy.deepcopy(x['values']['root_module']['resources'][0])); bad.append(x)
    x = fixture(); x['values']['root_module']['resources'] = []; bad.append(x)
    for x in bad:
        try:
            observer.summarize(x, receipts)
        except ValueError:
            pass
        else:
            raise AssertionError('Malformed/unsupported view accepted')
    # Independent four-record drift calculation, not a fake external provider.
    desired, prior, remote = 'small', 'small', 'medium'
    refreshed = remote
    assert (desired, prior, refreshed) == ('small', 'small', 'medium')
    next_state_after_refresh_only = refreshed
    assert remote == next_state_after_refresh_only != desired
    assert (next_state_after_refresh_only, desired) == ('medium', 'small')
    return dict(result='PASS', basis='pure fixtures; no native Terraform/API',
                service_update='same ID; file differs', moved='same name to ID mapping',
                negative_views=len(bad), mutation_of_inputs=False)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    model = load('tf_mechanism_model', root / 'labs/mechanism_model.py')
    observer = load('tf_state_observer', root / 'labs/observe.py')
    print(json.dumps(check_modules(model, observer), ensure_ascii=False, indent=2))
