#!/usr/bin/env python3
"""Pure teaching models, Python 3.12+. No network or filesystem writes."""
import argparse
import base64
import copy
import hashlib
import json
import sys
from decimal import Decimal

if not __debug__:
    raise SystemExit("Storage model checks require assertions enabled")

BODY = b"object-lab v1\n"
SHA = "874160ebe2d9a6a82abdec1966f3be5be4e0db5d575d4d00953c66baf6e30897"
MODES = ("unversioned", "enabled", "suspended")


def digest(data):
    raw = hashlib.sha256(data).digest()
    return {"bytes": len(data), "sha256_hex": raw.hex(),
            "sha256_base64": base64.b64encode(raw).decode("ascii")}


def checksums():
    correct = digest(BODY)
    changed = digest(BODY[:-1] + b"\r\n")
    short = digest(BODY[:-1])
    assert correct["bytes"] == 14 and correct["sha256_hex"] == SHA
    assert correct["sha256_base64"] == "h0Fg6+LZpqgqvewZZvO+W+Tg211XXU0AlTxmuvbjCJc="
    assert base64.b64encode(correct["sha256_hex"].encode("ascii")).decode("ascii") != correct["sha256_base64"]
    assert changed["bytes"] == 15 and changed["sha256_hex"] != SHA
    assert short["bytes"] == 13 and short["sha256_hex"] != SHA
    return {"correct": correct, "body_lf_to_crlf": changed, "missing_lf": short}


def byte_range(data, start=None, end=None, suffix=None):
    # One interval of this complete, fixed representation; no HTTP parser.
    if suffix is not None:
        if type(suffix) is not int or suffix <= 0:
            raise ValueError("invalid suffix")
        if not data:
            return {"status": 416, "body_hex": ""}
        start, end = max(0, len(data) - suffix), len(data) - 1
    else:
        if type(start) is not int or start < 0:
            raise ValueError("invalid start")
        if end is not None and (type(end) is not int or end < start):
            raise ValueError("invalid end")
        if start >= len(data):
            return {"status": 416, "body_hex": ""}
        if end is None:
            end = len(data) - 1
        end = min(end, len(data) - 1)
    part = data[start:end + 1]
    return {"status": 206, "content_range": f"bytes {start}-{end}/{len(data)}",
            "content_length": len(part), "body_hex": part.hex()}


def ranges():
    a, b = byte_range(BODY, 0, 5), byte_range(BODY, 14)
    last, suffix = byte_range(BODY, 13), byte_range(BODY, suffix=1)
    assert a["content_length"] == 6 and a["body_hex"] == b"object".hex()
    assert a["content_range"] == "bytes 0-5/14"
    assert b["status"] == 416
    assert last == suffix and suffix["body_hex"] == "0a"
    assert byte_range(BODY, 0, 100)["content_length"] == 14
    v2 = b"OBJECT-LAB V2\n"
    mixed = BODY[:6] + v2[6:]
    assert len(mixed) == len(BODY) == len(v2) == 14
    assert digest(mixed)["sha256_hex"] not in (SHA, digest(v2)["sha256_hex"])
    return {"first_six": a, "past_end": b, "last_byte": last, "suffix_one": suffix,
            "mixed_same_length": {"bytes": len(mixed), "body_hex": mixed.hex(),
                                  "sha256_hex": digest(mixed)["sha256_hex"]}}


def multipart():
    # Same deterministic fixture as chapter 10; update in 64 KiB blocks.
    sizes = [8 * 1024**2, 8 * 1024**2, 1024**2]
    whole = hashlib.sha256()
    results, offset = [], 0
    for number, size in enumerate(sizes, 1):
        h = hashlib.sha256()
        for local in range(0, size, 65536):
            block = bytes((offset + local + j) % 251
                          for j in range(min(65536, size - local)))
            h.update(block)
            whole.update(block)
        results.append({"part_number": number, "offset": offset, "bytes": size,
                        "sha256_base64": base64.b64encode(h.digest()).decode("ascii")})
        offset += size
    assert [p["bytes"] for p in results] == [8388608, 8388608, 1048576]
    assert [p["offset"] for p in results] == [0, 8388608, 16777216]
    assert [p["sha256_base64"] for p in results] == [
        "vfI4NxgfWAgzGADBritPfXqDlTaxDVhJFHHFDd4jgzo=",
        "tlPd1mVENNY1VABCXazfuR9Bu7hD50ywsx/7JLMNMww=",
        "cXjaGJ2oo7VPAVZmddRdm3mljr6yU4/gp3jdmferZ8E="]
    full = base64.b64encode(whole.digest()).decode("ascii")
    assert offset == 17825792 and full == "NpR3AcDrJK00v9qx/36Y9YTkgxjZrEORVODDeNlyYDM="
    # An upload is not an object until complete. Replacement is by part number.
    parts = {1: "etag-old", 2: "etag-two"}
    parts[1] = "etag-new"
    manifest = [(1, "etag-new"), (2, "etag-two")]
    assert len(parts) == 2 and all(parts[n] == e for n, e in manifest)
    assert parts[1] != "etag-old"
    return {"total_bytes": offset, "parts": results, "sha256_base64": full,
            "state": {"uploaded_part_numbers": sorted(parts), "object_before_complete": False,
                      "complete_manifest": manifest, "object_after_complete": True}}


def listing():
    keys = ["a/1", "a/2", "a/sub/3", "b"]
    matching = [k for k in keys if k.startswith("a/")]
    pages = [matching[i:i + 2] for i in range(0, len(matching), 2)]
    objects = [k for k in matching if "/" not in k[len("a/"):]]
    prefixes = sorted({"a/" + k[len("a/"):].split("/", 1)[0] + "/"
                       for k in matching if "/" in k[len("a/"):]})
    assert pages == [["a/1", "a/2"], ["a/sub/3"]]
    assert objects == ["a/1", "a/2"] and prefixes == ["a/sub/"]
    # This index pagination is deliberately NOT an implementation of S3 tokens.
    first = keys[:2]
    modified = ["a/0"] + keys
    second = modified[2:4]
    assert first + second == ["a/1", "a/2", "a/2", "a/sub/3"]
    return {"fixed_pages": pages, "delimiter_objects": objects,
            "common_prefixes": prefixes, "toy_index_mutation_duplicate": first + second,
            "s3_continuation_token_modelled": False}


def budget():
    original, retry = 17 * 1024**2, 25 * 1024**2
    rate = Decimal(100000000) / 8
    a, b = Decimal(original) / rate, Decimal(retry) / rate
    assert str(a) == "1.42606336" and str(b) == "2.097152"
    assert 3 * 14 * 7 == 294 and 14 * 7 == 98
    return {"upload_bytes_without_retry": original,
            "upload_bytes_with_one_retry": retry,
            "api_calls_without_retry_with_verify": 7,
            "api_calls_with_one_retry_with_verify": 8,
            "body_seconds_at_100_mbit_without_retry": str(a),
            "body_seconds_at_100_mbit_with_retry": str(b),
            "three_versions_byte_days": 294, "one_version_byte_days": 98,
            "four_8_mib_buffers_bytes": 4 * 8 * 1024**2,
            "measured_latency_or_invoice": False}


def initial(mode):
    if mode not in MODES:
        raise ValueError("unknown versioning mode")
    return {"mode": mode, "next_id": 1, "history": []}


def validate_state(state):
    if not isinstance(state, dict) or set(state) != {"mode", "next_id", "history"}:
        raise ValueError("invalid state fields")
    if state["mode"] not in MODES or type(state["next_id"]) is not int or state["next_id"] < 1:
        raise ValueError("invalid state mode or counter")
    if not isinstance(state["history"], list) or len(state["history"]) > 100:
        raise ValueError("invalid history")
    ids = []
    for v in state["history"]:
        if not isinstance(v, dict) or set(v) != {"id", "kind", "body_base64", "operation_id", "etag"}:
            raise ValueError("invalid version")
        if not isinstance(v["id"], str) or not v["id"]:
            raise ValueError("invalid version id")
        if v["kind"] not in ("data", "marker"):
            raise ValueError("invalid kind")
        if not isinstance(v["body_base64"], str):
            raise ValueError("invalid body")
        body = base64.b64decode(v["body_base64"], validate=True)
        if len(body) > 1024 or not isinstance(v["operation_id"], str) or not isinstance(v["etag"], str):
            raise ValueError("invalid version fields")
        if v["kind"] == "marker" and (body or v["etag"] or v["operation_id"]):
            raise ValueError("marker has data")
        ids.append(v["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate version id")
    if state["mode"] == "unversioned" and (len(ids) > 1 or any(x != "null" for x in ids)):
        raise ValueError("invalid unversioned history")


def request(state, event):
    """One model request, not an SDK retry policy or a server implementation."""
    validate_state(state)
    if not isinstance(event, dict) or event.get("op") not in ("put", "get", "delete"):
        raise ValueError("invalid event")
    allowed = {"op", "body", "operation_id", "condition", "etag", "version_id", "lose_reply"}
    if set(event) - allowed:
        raise ValueError("unknown event field")
    op = event["op"]
    if type(event.get("lose_reply", False)) is not bool:
        raise ValueError("lose_reply must be boolean")
    if "version_id" in event and (not isinstance(event["version_id"], str) or not event["version_id"]):
        raise ValueError("version id must be a nonempty string")
    s = copy.deepcopy(state)
    h = s["history"]
    current = h[0] if h else None
    result = {"scope": "single_model_request", "outcome": "confirmed", "status": 200}
    if op == "put":
        if "version_id" in event:
            raise ValueError("put cannot select version")
        body, oid = event.get("body"), event.get("operation_id")
        if not isinstance(body, str) or len(body.encode("utf-8")) > 1024:
            raise ValueError("body must be a short string")
        if not isinstance(oid, str) or not oid or len(oid) > 128:
            raise ValueError("operation id required")
        condition = event.get("condition")
        if condition not in ("create", "match"):
            raise ValueError("put condition required")
        data_current = current is not None and current["kind"] == "data"
        accepted = not data_current if condition == "create" else (
            data_current and isinstance(event.get("etag"), str) and current["etag"] == event["etag"])
        if not accepted:
            result.update(outcome="rejected", status=404 if condition == "match" and not data_current else 412)
            return s, result
        if s["mode"] == "enabled":
            vid = f"v{s['next_id']:04d}"
            s["next_id"] += 1
        else:
            vid = "null"
            h[:] = [v for v in h if v["id"] != "null"] if s["mode"] == "suspended" else []
        raw = body.encode("utf-8")
        # Opaque toy label only. This is NOT a rule for S3 ETag generation.
        tag = '"toy-' + hashlib.sha256(raw).hexdigest()[:16] + '"'
        h.insert(0, {"id": vid, "kind": "data",
                     "body_base64": base64.b64encode(raw).decode("ascii"),
                     "operation_id": oid, "etag": tag})
        result.update(version_id=vid, etag=tag)
    elif op == "get":
        selected = next((v for v in h if v["id"] == event["version_id"]), None) if "version_id" in event else current
        if selected is None:
            result.update(outcome="rejected", status=404)
        elif selected["kind"] == "marker":
            result.update(outcome="rejected", status=405 if "version_id" in event else 404)
        else:
            raw = base64.b64decode(selected["body_base64"])
            result.update(version_id=selected["id"], operation_id=selected["operation_id"],
                          etag=selected["etag"], **digest(raw))
    elif "version_id" in event:
        h[:] = [v for v in h if v["id"] != event["version_id"]]
        result.update(status=204, removed_id=event["version_id"])
    elif s["mode"] == "unversioned":
        h[:] = []
        result.update(status=204)
    else:
        if s["mode"] == "enabled":
            vid = f"v{s['next_id']:04d}"
            s["next_id"] += 1
        else:
            vid = "null"
            h[:] = [v for v in h if v["id"] != "null"]
        h.insert(0, {"id": vid, "kind": "marker", "body_base64": "",
                     "operation_id": "", "etag": ""})
        result.update(status=204, version_id=vid)
    if event.get("lose_reply"):
        result = {"scope": "single_model_request", "outcome": "unknown", "status": None}
    validate_state(s)
    return s, result


def scenarios():
    event = {"op": "put", "body": BODY.decode("ascii"), "condition": "create",
             "operation_id": "op-a", "lose_reply": True}
    s, lost = request(initial("enabled"), event)
    assert lost["outcome"] == "unknown" and len(s["history"]) == 1
    retry_event = {**event, "lose_reply": False}
    s2, retry = request(s, retry_event)
    assert retry["status"] == 412 and s2 == s
    # Logical operation still unknown to the client, despite this request's 412.
    _, observed = request(s2, {"op": "get", "version_id": "v0001"})
    assert observed["operation_id"] == "op-a" and observed["sha256_hex"] == SHA
    s3, d1 = request(s2, {"op": "delete", "lose_reply": True})
    s4, d2 = request(s3, {"op": "delete"})
    assert len(s4["history"]) == 3 and d1["outcome"] == "unknown" and d2["status"] == 204
    s5, _ = request(s4, {"op": "delete", "version_id": "v0003"})
    _, still_hidden = request(s5, {"op": "get"})
    assert still_hidden["status"] == 404
    t, _ = request(initial("suspended"), retry_event)
    old = t["history"][0]["etag"]
    t2, _ = request(t, {"op": "put", "body": "changed", "operation_id": "op-b",
                      "condition": "match", "etag": old})
    assert len(t2["history"]) == 1 and t2["history"][0]["id"] == "null"
    assert t2["history"][0]["etag"] != old
    return {"lost_put_state": s, "lost_put_result": lost, "retry_request_result": retry,
            "logical_operation_after_retry": "unknown", "observed_version": observed,
            "after_two_delete_markers": s4, "after_removing_only_latest_marker": still_hidden,
            "null_id_reused": t2["history"][0]["id"],
            "null_version_before": t["history"][0], "null_version_after": t2["history"][0]}


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_document(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("checksums", "ranges", "multipart", "listing", "budget", "scenarios", "check"):
        sub.add_parser(name)
    init = sub.add_parser("state-init")
    init.add_argument("--mode", choices=MODES, required=True)
    step = sub.add_parser("state-step")
    step.add_argument("--event", required=True, help="synthetic request JSON, never credentials")
    args = parser.parse_args(argv)
    functions = {"checksums": checksums, "ranges": ranges, "multipart": multipart,
                 "listing": listing, "budget": budget, "scenarios": scenarios}
    if args.command == "check":
        output = {name: fn() for name, fn in functions.items()}
        output["checks"] = "PASS: pure teaching models"
    elif args.command in functions:
        output = functions[args.command]()
    elif args.command == "state-init":
        output = {"schema_version": 1, "state": initial(args.mode), "result": None}
    else:
        raw = sys.stdin.read(1048577)
        if len(raw) > 1048576:
            raise ValueError("state input too large")
        doc = parse_document(raw)
        if not isinstance(doc, dict) or set(doc) != {"schema_version", "state", "result"}:
            raise ValueError("invalid document")
        if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
            raise ValueError("invalid schema")
        state, result = request(doc["state"], parse_document(args.event))
        output = {"schema_version": 1, "state": state, "result": result}
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise SystemExit("invalid synthetic model input: " + str(exc))
