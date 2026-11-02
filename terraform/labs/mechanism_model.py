#!/usr/bin/env python3
"""Fixed teaching examples, not Terraform, a provider, or an HCL interpreter.
Only pure calculations and stdout. No subprocess, filesystem, or infrastructure I/O.
"""
import copy
import json

def traces():
    # A/W/G labels are symbolic identities, never values for import.
    initial = dict(config=dict(port=8080, build='b1', gate_revision='g1', fail_gate=False),
                   api=dict(id='A1', port=8080, build='b1'),
                   worker=dict(id='W1', port=8081, build='b1'),
                   gate=dict(id='G1', status='ready'),
                   receipt=dict(port=8080, build='b1'),
                   actions=[], outcome='applied')
    rows = [copy.deepcopy(initial)]
    row = copy.deepcopy(initial)
    row['config']['port'] = 8180
    row['actions'] = ['update']
    row['outcome'] = 'planned; no apply'
    rows.append(copy.deepcopy(row))
    row['api']['port'] = 8180
    row['outcome'] = 'applied'
    rows.append(copy.deepcopy(row))
    row['config'].update(build='b2', gate_revision='fail-run', fail_gate=True)
    row['actions'] = ['delete', 'create']
    row['outcome'] = 'planned; no apply'
    rows.append(copy.deepcopy(row))
    # Selected legal schedule: both services finish before the dependent gate.
    # Child module records are not prerequisites of gate and are not asserted here.
    row['api'].update(id='A2', build='b2')
    row['worker'].update(id='W2', build='b2')
    row['receipt'].update(port=8180, build='b2')
    row['gate'] = dict(id='G2', status='tainted')
    row['outcome'] = 'Terraform rc=1; gate.py rc=7'
    rows.append(copy.deepcopy(row))
    row['config']['fail_gate'] = False
    row['actions'] = ['no-op']  # Service action; gate is replaced separately.
    row['gate'] = dict(id='G3', status='ready')
    row['outcome'] = 'repair applied; next plan empty'
    rows.append(copy.deepcopy(row))
    return rows

def render_receipt(row):
    return (json.dumps(row['receipt'], sort_keys=True) + '\n').encode('utf-8')

def validate_service(value):
    """Only the chosen lab requirements, not Terraform conversion rules."""
    if not isinstance(value, dict) or set(value) != {'port', 'build'}:
        return False
    port = value['port']
    return (isinstance(port, (int, float)) and not isinstance(port, bool)
            and 1024 <= port <= 65535 and int(port) == port
            and isinstance(value['build'], str) and bool(value['build'].strip()))

def earliest_finish(durations, dependencies):
    """Unlimited ready workers: lower bound only, not a parallel scheduler."""
    finish = {}
    pending = set(durations)
    while pending:
        ready = sorted(n for n in pending if set(dependencies.get(n, ())) <= finish.keys())
        if not ready:
            raise ValueError('Cycle or missing dependency')
        for name in ready:
            duration = durations[name]
            if duration < 0:
                raise ValueError('Negative duration')
            finish[name] = max((finish[d] for d in dependencies.get(name, ())), default=0) + duration
            pending.remove(name)
    return finish

def can_push(old_lineage, old_serial, current_lineage, current_serial):
    """Selected safety rule for the examples, not a full backend implementation."""
    return old_lineage == current_lineage and old_serial >= current_serial

def check():
    rows = traces()
    assert len(rows) == 6
    assert rows[0]['api']['id'] == rows[1]['api']['id'] == rows[2]['api']['id'] == 'A1'
    assert rows[1]['api']['port'] == 8080 and rows[1]['config']['port'] == 8180
    assert rows[2]['api']['port'] == 8180 and rows[2]['receipt']['port'] == 8080
    assert rows[3]['api']['build'] == 'b1' and rows[3]['config']['build'] == 'b2'
    # Gate creation runs because its own triggers_replace input changed.
    # depends_on and fail_gate alone do not rerun a creation provisioner.
    assert all(r['config']['gate_revision'] == 'g1' for r in rows[:3])
    assert all(r['config']['gate_revision'] == 'fail-run' for r in rows[3:])
    assert rows[2]['config']['gate_revision'] != rows[3]['config']['gate_revision']
    assert rows[4]['config']['fail_gate'] is True and rows[5]['config']['fail_gate'] is False
    assert rows[4]['api']['id'] == rows[5]['api']['id'] == 'A2'
    assert rows[4]['worker']['id'] == rows[5]['worker']['id'] == 'W2'
    assert rows[4]['gate']['status'] == 'tainted' and rows[5]['gate']['status'] == 'ready'
    assert rows[4]['api']['build'] == rows[5]['api']['build'] == 'b2'
    assert render_receipt(rows[2]) == b'{"build": "b1", "port": 8080}\n'
    assert render_receipt(rows[4]) == b'{"build": "b2", "port": 8180}\n'
    assert validate_service(dict(port=8080, build='b1'))
    assert all(not validate_service(v) for v in [
        None, dict(port=None, build='b1'), dict(port=8080, build=None),
        dict(port=80, build='b1'), dict(port=8080.5, build='b1'),
        dict(port=8080, build=' ')])
    # Count's identity is position; for_each's identity is key.
    before = ['api', 'worker', 'batch']; after = ['worker', 'batch']
    assert [(i, before[i], after[i]) for i in range(len(after))] == [
        (0, 'api', 'worker'), (1, 'worker', 'batch')]
    assert set(before) - set(after) == {'api'}
    assert earliest_finish(dict(A=2, B=3, C=1), dict(C=('A', 'B')))['C'] == 4
    assert sum([2, 3, 1]) == 6
    assert earliest_finish(dict(A=2, B=8, C=1), dict(C=('A', 'B')))['C'] == 9
    try:
        earliest_finish(dict(A=1, B=1), dict(A=('B',), B=('A',)))
    except ValueError:
        pass
    else:
        raise AssertionError('Cycle accepted')
    assert can_push('L', 43, 'L', 43)
    assert not can_push('L', 42, 'L', 43)
    assert not can_push('X', 43, 'L', 43)
    return dict(result='PASS', scope='fixed pure model; no native Terraform execution',
                snapshots=len(rows))

if __name__ == '__main__':
    print(json.dumps(dict(check=check(), trace=traces()), ensure_ascii=False, indent=2))
