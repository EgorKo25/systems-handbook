#!/usr/bin/env python3
"""Export tracked public reading materials, without Git or authoring files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.publication import VOLUME_TITLES

ROOT_FILES = {
    ".nojekyll", "index.html", "library-stats.json", "published-volumes.json",
    "КАК-ЧИТАТЬ.txt", "ПЛАН-ПРАКТИЧЕСКОГО-СТЕНДА.txt",
    "ПРОВЕРКИ-БИБЛИОТЕКИ.txt", "ПЛАН-РАЗВИТИЯ.txt",
}
BOOKS = set(VOLUME_TITLES)
CACHE_LAB_MODELS = {"cache/sources/eviction.js", "cache/sources/resource-labs.js", "cache/sources/resp-lab.js"}
REVISION = re.compile(r"[0-9a-f]{40,64}")


def manifest(directory: Path) -> str:
    paths = sorted(directory.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("exported sites cannot contain symlinks")
    return "".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " +
                   path.relative_to(directory).as_posix() + "\n"
                   for path in paths if path.is_file() and path != directory / "SHA256SUMS")


def verify_previous_export(output: Path) -> None:
    try:
        marker = json.loads((output / "site-version.json").read_text(encoding="utf-8"))
        valid = (isinstance(marker, dict) and type(marker.get("format")) is int and
                 marker["format"] == 1 and isinstance(marker.get("revision"), str) and
                 REVISION.fullmatch(marker["revision"]))
        if not valid or (output / "SHA256SUMS").read_text(encoding="utf-8") != manifest(output):
            raise ValueError("marker or file manifest does not match")
    except (OSError, ValueError) as error:
        raise ValueError("output is not an intact previous export; preserve it and choose another directory") from error


def is_reading_file(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if name in ROOT_FILES:
        return True
    if name in CACHE_LAB_MODELS:
        return True  # Node laboratory checks require these same browser models.
    if path.parts[0] in BOOKS and name in {
            "git/labs/template/.gitignore", "go/labs/service/.gitignore",
            "gitlab/labs/service/.gitignore", "gitlab/labs/service/.gitlab-ci.yml",
            "docker/labs/echo/.dockerignore", "sonarqube/labs/.gitignore",
            "terraform/.gitignore", "terraform/labs/foundation/.gitignore",
            "terraform/labs/adapters/libvirt/.terraform.lock.hcl",
            "helm/labs/chart/.helmignore"}:
        return True
    if any(p.startswith(".") or p in {"__pycache__", "node_modules"} for p in path.parts):
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    if path.parts[:2] == ("guide", "textbook"):
        return True
    if path.parts[0] == "checks":
        return path.suffix in {".json", ".png", ".jpg", ".svg", ".txt"}
    if path.parts[0] == "labs-personal":
        private = {"runtime", "state", "assets", "private", "snapshots", "progress", "cache", "tools", "saves", "keys", "images", "exports"}
        binary = {".qcow2", ".img", ".iso", ".ova", ".vmdk", ".vdi", ".pkt", ".pka", ".zip", ".tar", ".gz", ".exe", ".dll", ".key", ".pem"}
        return not any(part.casefold() in private for part in path.parts[1:]) and path.suffix.lower() not in binary
    if path.parts[0] not in BOOKS:
        return False
    if path.parts[0] == "terraform" and re.search(r"\.(?:tfstate|tfplan)(?:\.|$)", path.name.casefold()):
        return False  # State, saved plans and their backups remain private even if tracked.
    if len(path.parts) > 1 and path.parts[1] == "sources":
        return False
    if len(path.parts) == 2 and path.suffix in {".py", ".cjs"}:
        return False
    return True


def export_site(source: Path, output: Path, revision: str, *, replace: bool = False) -> dict:
    output = output.absolute()
    if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
        raise ValueError("output and its parents cannot be symlinks")
    source, output = source.resolve(), output.resolve()
    if not REVISION.fullmatch(revision):
        raise ValueError("revision must be a full Git commit SHA")
    if output == source or source.is_relative_to(output):
        raise ValueError("output cannot replace the repository or one of its parents")
    if output.is_relative_to(source):
        first = output.relative_to(source).parts[0]
        if first in BOOKS | {"labs-personal", "guide", "checks", ".git", ".github", "scripts", "tests"}:
            raise ValueError("output overlaps source or authoring material")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        if not replace or not output.is_dir():
            raise ValueError("nonempty output is not a previous exported site; choose another directory")
        verify_previous_export(output)
    tracked = subprocess.run(
        ["git", "-C", str(source), "ls-files", "-z"],
        check=True, stdout=subprocess.PIPE,
    ).stdout.decode("utf-8").split("\0")
    names = sorted(name for name in tracked if name and is_reading_file(name))
    if "index.html" not in names:
        raise ValueError("no tracked public index.html in source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pages-export-", dir=output.parent) as temporary:
        stage = Path(temporary) / "site"
        stage.mkdir()
        for name in names:
            path = source / name
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != source.parent):
                raise ValueError(f"symlinks are not published: {name}")
            if not path.is_file() or not path.resolve().is_relative_to(source):
                raise ValueError(f"tracked reading file missing or outside source: {name}")
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        (stage / ".nojekyll").touch()
        (stage / "site-version.json").write_text(
            json.dumps({"revision": revision, "format": 1}, indent=2) + "\n", encoding="utf-8"
        )
        files = [path for path in stage.rglob("*") if path.is_file()]
        (stage / "SHA256SUMS").write_text(manifest(stage), encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        stage.replace(output)
    return {"revision": revision, "files": len(files) + 1, "output": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--replace", action="store_true", help="replace a previous export with site-version.json")
    args = parser.parse_args()
    try:
        report = export_site(Path(__file__).resolve().parents[1], args.output,
                             args.revision, replace=args.replace)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Cannot export Pages: {error}\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
