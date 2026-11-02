"""Deliberately one-shot provisioner effect, NOT a managed file provider."""
import json
import os
import re
from pathlib import Path
root = Path(os.environ['TF_LAB_DIR']).resolve()
assert (root / '.terraform-handbook-lab').is_file(), 'Only inside the prepared lab'
name = os.environ['TF_LAB_NAME']
assert re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', name), 'Unsupported lab key'
value = json.loads(os.environ['TF_LAB_JSON'])
(root / ('rendered-' + name + '.json')).write_text(json.dumps(value, sort_keys=True) + '\n')
