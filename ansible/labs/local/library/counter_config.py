#!/usr/bin/python
"""Original teaching module: exact JSON configuration in a pre-created directory."""
from __future__ import annotations
import json
import os
import stat
import tempfile
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
---
module: counter_config
short_description: Converge an exact JSON object in a private lab file
version_added: '1.0.0'
description:
  - Reads and validates an existing JSON object before deciding whether to replace it.
  - Rejects symlinks and malformed existing JSON. Does not create parent directories.
  - Teaching scope only; no concurrent writers or hostile parent directory.
options:
  path:
    description: Absolute file path in a pre-created private directory.
    type: path
    required: true
  config:
    description: Complete desired JSON object, without secrets.
    type: dict
    required: true
  mode:
    description: Octal permissions for the managed regular file.
    type: str
    default: '0640'
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
author: Original systems handbook example
'''
EXAMPLES = r'''
- name: Save a typed object
  counter_config:
    path: /tmp/ansible-reader-lab/counter_a/config.json
    config: {release: '0.1.0', listen: '127.0.0.1:8080'}
'''
RETURN = r'''
path:
  description: The managed path.
  type: str
  returned: success
changed:
  description: Whether UTF-8 file text after newline normalization or the permission mode differs from the desired state.
  type: bool
  returned: success
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(path=dict(type='path', required=True),
                           config=dict(type='dict', required=True),
                           mode=dict(type='str', default='0640')),
        supports_check_mode=True,
    )
    path = module.params['path']
    temporary = None
    try:
        if not os.path.isabs(path):
            module.fail_json(msg='path must be absolute')
        mode_text = module.params['mode']
        if len(mode_text) not in (3, 4) or any(c not in '01234567' for c in mode_text):
            module.fail_json(msg='mode must be an octal string')
        mode = int(mode_text, 8)
        if mode > 0o777:
            module.fail_json(msg='special permission bits are outside the lab contract')
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            module.fail_json(msg='parent directory must already exist')
        before = ''
        previous_mode = None
        if os.path.lexists(path):
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode):
                module.fail_json(msg='existing destination must be a regular file, not a symlink')
            previous_mode = stat.S_IMODE(info.st_mode)
            with open(path, encoding='utf-8') as source:
                before = source.read()
            old = json.loads(before)
            if not isinstance(old, dict):
                module.fail_json(msg='existing JSON must contain an object')
        after = json.dumps(module.params['config'], ensure_ascii=False,
                           sort_keys=True, indent=2, allow_nan=False) + '\n'
        changed = before != after or previous_mode != mode
        result = dict(changed=changed, path=path)
        if module._diff:
            result['diff'] = dict(before=before, after=after,
                                  before_header=path, after_header=path)
        if changed and not module.check_mode:
            descriptor, temporary = tempfile.mkstemp(prefix='.counter-', dir=parent)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                os.fchmod(output.fileno(), mode)
                output.write(after)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            temporary = None
        module.exit_json(**result)
    except (OSError, ValueError, TypeError) as error:
        module.fail_json(msg='configuration operation failed: ' + str(error))
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


if __name__ == '__main__':
    main()
