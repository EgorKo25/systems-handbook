#!/usr/bin/env python3
"""Read-only offline-file audit. Does not download, execute or install assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manifest", type=Path, default=ROOT / "private/assets.json")
args = parser.parse_args()
if not args.manifest.is_file():
    print("Комплект не подготовлен: создайте private/assets.json по assets.example.json.")
    raise SystemExit(2)
try:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise ValueError("ожидается schema=1")
    results = []
    failed = False
    for item in manifest["assets"]:
        path = (ROOT / item["path"]).resolve()
        if ROOT not in path.parents or path == ROOT:
            raise ValueError("asset path выходит из labs-personal")
        expected = item.get("sha256")
        if not path.is_file():
            status = "MISSING" if item.get("required", True) else "OPTIONAL-MISSING"
        elif not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            status = "UNPINNED"
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            status = "OK" if digest.hexdigest() == expected else "HASH-MISMATCH"
        failed |= status in ("MISSING", "UNPINNED", "HASH-MISMATCH")
        results.append({"id": item["id"], "status": status, "version": item.get("version")})
    print(json.dumps({"assets": results, "all_required_files_verified": not failed,
                      "guest_boot_or_windows_execution_tested": False}, ensure_ascii=False, indent=2))
    raise SystemExit(2 if failed else 0)
except (OSError, ValueError, KeyError, TypeError) as error:
    print("Ошибка manifest:", error, file=sys.stderr)
    raise SystemExit(2)
