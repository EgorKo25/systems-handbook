#!/usr/bin/env python3
"""Read an existing show -json view and own receipt files; never run Terraform."""
import argparse
import json
import sys
from pathlib import Path

def summarize(view, receipts):
    """Pure comparison. This is not a provider Read or an HCL evaluator."""
    version = view.get('format_version', '')
    if not isinstance(version, str) or version.split('.')[0] != '1':
        raise ValueError('Unsupported show JSON major version')
    values = view.get('values')
    if not isinstance(values, dict) or not isinstance(values.get('root_module'), dict):
        raise ValueError('A complete state view is required, not a plan')
    if 'resource_changes' in view or 'planned_values' in view:
        raise ValueError('A plan is not an applied state view')
    resources = values['root_module'].get('resources', [])
    result = []
    seen = set()
    for resource in resources:
        if resource.get('mode') != 'managed' or resource.get('type') != 'terraform_data':
            continue
        if resource.get('name') not in ('service', 'node'):
            continue
        name = resource.get('index')
        if not isinstance(name, str) or name in seen:
            raise ValueError('Unsupported or duplicate service key')
        seen.add(name)
        current = resource.get('values', {})
        data = current.get('output')
        if not isinstance(data, dict) or set(data) != {'port', 'build'}:
            raise ValueError('Expected foundation output with port and build')
        if not isinstance(current.get('id'), str) or not current['id']:
            raise ValueError('Missing applied identity')
        receipt = receipts.get(name)
        result.append(dict(address=resource['address'], key=name, id=current['id'],
                           state=dict(data), receipt=receipt,
                           receipt_matches=(receipt == data)))
    if not result:
        raise ValueError('No root service/node instances found')
    return dict(basis='existing state view plus separately read files',
                managed_file_read=False, external_readiness_proved=False,
                services=sorted(result, key=lambda row: row['key']))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / '.terraform-handbook-lab').is_file():
        raise SystemExit('Refusing an unmarked lab')
    view = json.load(sys.stdin)
    receipts = {}
    # Names come from already applied state. Limit filesystem reads to lab keys.
    import re
    for resource in view.get('values', {}).get('root_module', {}).get('resources', []):
        if resource.get('name') in ('service', 'node') and resource.get('type') == 'terraform_data':
            name = resource.get('index')
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', name):
                raise SystemExit('Unsupported key')
            path = root / ('rendered-' + name + '.json')
            if path.is_symlink():
                raise SystemExit('Refusing a receipt symlink')
            if path.is_file():
                receipts[name] = json.loads(path.read_text())
    print(json.dumps(summarize(view, receipts), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
