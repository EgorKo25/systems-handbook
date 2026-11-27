"""Plan expired release reserves from two trusted inventories. No filesystem changes."""

from collections import Counter
import argparse
import json
from pathlib import Path
import re


REVISION = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
RESERVE = re.compile(r"book-fallback-[0-9a-f]{7}")
MIN_AGE = 72 * 60 * 60
NANOSECONDS_PER_SECOND = 1_000_000_000
STAT_BLOCK_BYTES = 512


def require(condition, message):
    if not condition:
        raise ValueError(message)


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def reserve_name(revision):
    return f"book-fallback-{revision[:7]}"


def check_inventory(snapshot):
    require(isinstance(snapshot, dict), "invalid inventory object")
    require(integer(snapshot["observed_at"]), "invalid inventory time")
    require(integer(snapshot["owner_uid"]), "invalid reserve owner")
    roles = snapshot["protected"]
    expected_roles = {"active", "rollback", "blue", "green", "initial", "pinned"}
    require(isinstance(roles, dict) and set(roles) == expected_roles
            and all(matches(REVISION, value) for value in roles.values()),
            "incomplete protected revisions")
    require(matches(DIGEST, snapshot["generation"]), "missing protection generation")
    caddy = snapshot["caddy"]
    require(isinstance(caddy, dict) and matches(DIGEST, caddy["expected"])
            and matches(DIGEST, caddy["observed"]),
            "invalid Caddy digests")
    require(isinstance(caddy["reserves"], list) and all(
        matches(RESERVE, name) for name in caddy["reserves"]
    ), "invalid Caddy reserve list")
    loopback = snapshot["loopback"]
    require(isinstance(loopback, dict) and matches(REVISION, loopback["revision"])
            and matches(DIGEST, loopback["manifest"])
            and matches(DIGEST, snapshot["active_manifest"]), "invalid loopback receipt")
    receipts = snapshot["receipts"]
    require(isinstance(receipts, dict) and all(
        matches(REVISION, revision) and matches(DIGEST, manifest)
        for revision, manifest in receipts.items()
    ), "invalid reserve ownership receipts")
    trees = snapshot["trees"]
    require(isinstance(trees, list) and all(
        isinstance(row, dict) and matches(RESERVE, row.get("name")) for row in trees
    ),
            "invalid reserve observations")
    require(type(snapshot["pending"]) is bool, "invalid pending flag")
    if snapshot["pending"]:
        return "pending cutover"
    if caddy["expected"] != caddy["observed"]:
        return "Caddy digest changed"
    if (loopback["revision"], loopback["manifest"]) != (roles["active"], snapshot["active_manifest"]):
        return "loopback does not match active"
    return None


def inspect(snapshot):
    blocked = check_inventory(snapshot)
    receipts = snapshot["receipts"]
    prefixes = Counter(reserve_name(revision) for revision in receipts)
    names = Counter(row["name"] for row in snapshot["trees"])
    inodes = Counter(
        (row["device"], row["inode"]) for row in snapshot["trees"]
        if integer(row.get("device")) and integer(row.get("inode"), 1)
    )
    protected = {reserve_name(revision) for revision in snapshot["protected"].values()}
    protected.update(snapshot["caddy"]["reserves"])
    accepted = {}
    skipped = {}
    for row in sorted(snapshot["trees"], key=lambda tree: tree["name"]):
        name = row["name"]
        revision = row.get("revision")
        if name in protected:
            skipped[name] = "protected"
        elif blocked:
            skipped[name] = blocked
        elif names[name] != 1 or prefixes[name] > 1:
            skipped[name] = "ambiguous reserve identity"
        elif not matches(REVISION, revision) or name != reserve_name(revision) or revision not in receipts:
            skipped[name] = "no exact ownership receipt"
        elif row.get("manifest") != receipts[revision] or row.get("verified") is not True:
            skipped[name] = "manifest or contents unverified"
        elif (row.get("kind") != "directory" or row.get("contains_mount") is not False
              or row.get("uid") != snapshot["owner_uid"] or not integer(row.get("uid"))
              or not integer(row.get("device")) or not integer(row.get("inode"), 1)
              or not integer(row.get("ctime_ns"), 1) or not integer(row.get("reclaimable_bytes"))):
            skipped[name] = "unsafe or incomplete filesystem evidence"
        elif inodes[row["device"], row["inode"]] != 1:
            skipped[name] = "ambiguous directory inode"
        elif row["ctime_ns"] // NANOSECONDS_PER_SECOND > snapshot["observed_at"]:
            skipped[name] = "directory ctime is after observation"
        elif row["reclaimable_bytes"] % STAT_BLOCK_BYTES:
            skipped[name] = "reclaimable bytes must be a multiple of 512"
        else:
            accepted[name] = row
    return blocked, accepted, skipped


def identity(row):
    return tuple(row[field] for field in ("revision", "manifest", "uid", "device", "inode", "ctime_ns"))


def plan(current, earlier=None):
    blocked, accepted, skipped = inspect(current)
    continuity = False
    prior = {}
    if earlier is not None:
        earlier_blocked, prior, _ = inspect(earlier)
        require(earlier["observed_at"] <= current["observed_at"], "inventories are out of order")
        continuity = (not earlier_blocked and current["generation"] == earlier["generation"]
                      and current["protected"] == earlier["protected"] and current["caddy"] == earlier["caddy"]
                      and current["loopback"] == earlier["loopback"])
    candidates = []
    for name, row in accepted.items():
        if not continuity or name not in prior or identity(row) != identity(prior[name]):
            skipped[name] = "matching earlier observation required"
            continue
        age = current["observed_at"] - earlier["observed_at"]
        if age < MIN_AGE:
            skipped[name] = "retention period not elapsed"
            continue
        candidates.append({field: row[field] for field in (
            "name", "revision", "manifest", "uid", "device", "inode", "ctime_ns", "reclaimable_bytes"
        )} | {"observed_for_seconds": age})
    return {"mode": "report", "blocked": blocked, "candidates": candidates, "skipped": skipped}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_inventory(path):
    snapshot = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    require(isinstance(snapshot, dict), "invalid inventory object")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path)
    parser.add_argument("--earlier", type=Path)
    args = parser.parse_args()
    try:
        current = read_inventory(args.current)
        earlier = read_inventory(args.earlier) if args.earlier else None
        report = plan(current, earlier)
    except (OSError, TypeError, KeyError, ValueError) as error:
        parser.exit(2, f"invalid inventory: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
