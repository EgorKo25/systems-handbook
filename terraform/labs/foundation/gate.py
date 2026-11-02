"""An explicit bounded failure/wait for the partial-apply and locking exercise."""
import os
import sys
import time
from pathlib import Path
root = Path(os.environ['TF_LAB_DIR']).resolve()
assert (root / '.terraform-handbook-lab').is_file(), 'Only inside the prepared lab'
time.sleep(min(20, max(0, float(os.environ['TF_LAB_HOLD']))))
if os.environ['TF_LAB_FAIL'] == 'true':
    print('LAB: deliberate gate refusal; earlier resource changes remain', file=sys.stderr)
    raise SystemExit(7)
print('LAB: gate accepted')
