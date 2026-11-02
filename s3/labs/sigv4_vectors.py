#!/usr/bin/env python3
"""Public fictional S3 SigV4 vectors; stdlib, no network or file writes."""
import base64
import datetime as dt
import hashlib
import hmac
import json
import re

ACCESS = "AKIDEXAMPLE"
SECRET = b"s3-lab-only-not-a-real-secret"
DATE = "20261101T090000Z"
REGION = "us-east-1"
SERVICE = "s3"
KEY = "lessons/2026-11/hello +%.txt"
BODY = b"object-lab v1\n"
HOST = "127.0.0.1:19000"
ALGORITHM = "AWS4-HMAC-SHA256"
SAFE = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"

if not __debug__:
    raise SystemExit('SigV4 checks require assertions enabled')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def mac(key, message):
    return hmac.new(key, message, hashlib.sha256).digest()

def pct(text, slash=False):
    allowed = SAFE + (b"/" if slash else b"")
    return "".join(chr(b) if b in allowed else "%%%02X" % b
                   for b in text.encode("utf-8"))

def path(key):
    return "/study-s3/" + pct(key, slash=True)

def query(pairs):
    # Preserve every pair, including repeated names and empty values.
    encoded = sorted((pct(k), pct(v)) for k, v in pairs)
    return "&".join(k + "=" + v for k, v in encoded)

def header_block(headers):
    normalized = []
    for name, value in headers:
        if not re.fullmatch(r"[A-Za-z0-9-]+", name):
            raise ValueError("header name outside model")
        if any(ord(c) < 32 and c != "\t" or ord(c) > 126 for c in value):
            raise ValueError("non-ASCII or control character in header")
        value = value.strip(" \t")
        if "\t" in value:
            raise ValueError("interior HTAB outside model")
        normalized.append((name.lower(), re.sub(" +", " ", value)))
    normalized.sort()
    if len({k for k, _ in normalized}) != len(normalized):
        raise ValueError("repeated headers outside model")
    return ("".join(k + ":" + v + "\n" for k, v in normalized),
            ";".join(k for k, _ in normalized))

def canonical(method, key, pairs, headers, payload):
    block, names = header_block(headers)
    return "\n".join(
        (method, path(key), query(pairs), block, names, payload)
    ).encode("ascii")

def derive(short_date, region=REGION, service=SERVICE):
    keys = []
    key = b"AWS4" + SECRET
    for text in (short_date, region, service, "aws4_request"):
        key = mac(key, text.encode("ascii"))
        keys.append(key)
    return keys

def sign(raw, date=DATE, region=REGION, service=SERVICE, short_date=None):
    short_date = short_date or date[:8]
    scope = "/".join((short_date, region, service, "aws4_request"))
    keys = derive(short_date, region, service)
    string = "\n".join((ALGORITHM, date, scope, sha(raw))).encode("ascii")
    return {
        "canonical_bytes": len(raw), "canonical": raw.decode("ascii"),
        "canonical_sha256": sha(raw), "scope": scope,
        "string_to_sign": string.decode("ascii"),
        "string_to_sign_bytes": len(string),
        "keys_hex": [k.hex() for k in keys],
        "signature": mac(keys[-1], string).hex(),
    }

def put_headers(body=BODY, date=DATE, host=HOST, condition="*"):
    return [("Content-Type", "text/plain"), ("Host", host),
            ("If-None-Match", condition),
            ("X-Amz-Content-Sha256", sha(body)), ("X-Amz-Date", date)]

def put(body=BODY, date=DATE, host=HOST, condition="*", key=KEY, pairs=()):
    raw = canonical("PUT", key, pairs,
                    put_headers(body, date, host, condition), sha(body))
    return sign(raw, date=date)

def presign_pairs(expires="60", token=None):
    scope = DATE[:8] + "/" + REGION + "/" + SERVICE + "/aws4_request"
    pairs = [
        ("X-Amz-Algorithm", ALGORITHM),
        ("X-Amz-Credential", ACCESS + "/" + scope),
        ("X-Amz-Date", DATE), ("X-Amz-Expires", expires),
        ("X-Amz-SignedHeaders", "host"),
        ("response-content-disposition", 'attachment; filename="hello +%.txt"'),
        ("versionId", "v+/%"),
    ]
    if token is not None:
        pairs.append(("X-Amz-Security-Token", token))
    return pairs

def presign(expires="60", token=None):
    pairs = presign_pairs(expires, token)
    raw = canonical("GET", KEY, pairs, [("Host", HOST)], "UNSIGNED-PAYLOAD")
    result = sign(raw)
    result["query"] = query(pairs)
    result["url"] = ("http://" + HOST + path(KEY) + "?" + query(pairs)
                     + "&X-Amz-Signature=" + result["signature"])
    return result

def first_difference(a, b):
    if a == b:
        return None
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                min(len(a), len(b)))

def mutation(name, raw, reference, **sign_args):
    result = sign(raw, **sign_args)
    return {"case": name, "first_canonical_difference": first_difference(reference, raw),
            "canonical_bytes": len(raw), "canonical_sha256": sha(raw),
            "signature": result["signature"]}

def utc(value):
    return dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)

def time_window(now, expires=60, credentials_end=None):
    # Arithmetic illustration, not the server's freshness/authorization validator.
    if not 1 <= expires <= 604800:
        return "invalid-expires"
    start = utc(DATE)
    end = start + dt.timedelta(seconds=expires)
    if credentials_end is not None:
        end = min(end, utc(credentials_end))
    now = utc(now)
    return "before-issue" if now < start else ("at-or-after-end" if now >= end else "within")

def main():
    assert mac(bytes([0x0b]) * 20, b"Hi There").hex() == (
        "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
    )
    base = put()
    raw = base["canonical"].encode("ascii")
    signed = header_block(put_headers())[1]
    authorization = (ALGORITHM + " Credential=" + ACCESS + "/" + base["scope"]
                     + ", SignedHeaders=" + signed
                     + ", Signature=" + base["signature"])
    lines = ["PUT " + path(KEY) + " HTTP/1.1",
             "Host: " + HOST, "Content-Type: text/plain", "Content-Length: 14",
             "If-None-Match: *", "X-Amz-Content-Sha256: " + sha(BODY),
             "X-Amz-Date: " + DATE, "Authorization: " + authorization, "", ""]
    wire = "\r\n".join(lines).encode("ascii") + BODY
    pre = presign()
    assert len(BODY) == 14 and BODY.hex() == "6f626a6563742d6c61622076310a"
    assert len(raw) == 354 and not raw.endswith(b"\n")
    assert base["canonical_sha256"] == "1916f06f0716be4ee42bfde94fb0ba08552e1b87f5a24193725c0097137c3ec6"
    assert base["signature"] == "a1dcb907b99c7d2f0848413d81c80960dd54f2e49d212c2ae01110fbb60afc31"
    assert pre["canonical_bytes"] == 369
    assert pre["canonical_sha256"] == "6e50095284b663b114d9a8eabfb4aa6d3ebc66a79cbb666c68ccfb35a746376a"
    assert pre["signature"] == "0f455b73dfd532fc6954d7bcdfce8b30bc806ba2ce1ca64fbed3681d47989221"
    assert path("sp ace") == "/study-s3/sp%20ace"
    assert path("sp%20ace") == "/study-s3/sp%2520ace"
    assert path("+") == "/study-s3/%2B" and path(" ") == "/study-s3/%20"
    assert path("a/b") == "/study-s3/a/b"
    assert path("a%2Fb") == "/study-s3/a%252Fb"
    assert path("a//b") == "/study-s3/a//b"
    assert path("a/../b") == "/study-s3/a/../b"
    assert path("урок/ёж.txt") == "/study-s3/%D1%83%D1%80%D0%BE%D0%BA/%D1%91%D0%B6.txt"
    assert path("é") != path("e\u0301")
    pairs = [("x", "2"), ("x", "1"), ("acl", "")]
    q = query(pairs)
    assert q == "acl=&x=1&x=2" and q == query(list(reversed(pairs)))
    assert q != query([("x", "1"), ("acl", "")])
    assert query([("x", "+ /%"), ("x", "")]) == "x=&x=%2B%20%2F%25"
    assert query([("a", "x"), ("é", "")]) == "%C3%A9=&a=x"
    reordered = [(k.upper(), " \t" + v + "\t ")
                 for k, v in reversed(put_headers())]
    assert canonical("PUT", KEY, [], reordered, sha(BODY)) == raw
    extra_a = put_headers() + [("X-Amz-Meta-Label", "alpha   beta")]
    extra_b = put_headers() + [("x-amz-meta-label", "alpha beta")]
    assert canonical("PUT", KEY, [], extra_a, sha(BODY)) == canonical("PUT", KEY, [], extra_b, sha(BODY))
    for bad in (put_headers() + [("host", HOST)],
                [("X-Label", "alpha\tbeta")], [("X-Label", "a\r\nb")]):
        try:
            header_block(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("header input should be rejected by model")
    cases = []
    def add(name, changed, **kwargs):
        cases.append(mutation(name, changed, raw, **kwargs))
    add("body-CRLF-rehashed", put(body=b"object-lab v1\r\n")["canonical"].encode("ascii"))
    add("canonical-CRLF", raw.replace(b"\n", b"\r\n"))
    add("extra-final-LF", raw + b"\n")
    add("path-space-as-plus", raw.replace(b"%20", b"+", 1))
    add("path-double-encoded-space", raw.replace(b"%20", b"%2520", 1))
    add("host-port-19001", put(host="127.0.0.1:19001")["canonical"].encode("ascii"))
    add("condition-changed", put(condition='"old"')["canonical"].encode("ascii"))
    unsorted = canonical("PUT", KEY, pairs, put_headers(), sha(BODY))
    sorted_hash = sha(unsorted)
    wrong_query = unsorted.replace(q.encode("ascii"), b"x=2&x=1&acl=")
    assert sha(wrong_query) != sorted_hash
    cases.append(mutation("query-order-not-canonical", wrong_query, unsorted))
    add("region-us-east-2", raw, region="us-east-2")
    add("scope-date-20261102-only", raw, short_date="20261102")
    changed_date = "20261101T090001Z"
    add("timestamp-plus-one-second",
        put(date=changed_date)["canonical"].encode("ascii"), date=changed_date)
    keys = derive(DATE[:8])
    to_sign = base["string_to_sign"].encode("ascii")
    bad_hex_key = mac(keys[-1].hex().encode("ascii"), to_sign).hex()
    assert bad_hex_key != base["signature"]
    assert put(key="a//b")["signature"] != put(key="a/b")["signature"]
    assert put(key="é")["signature"] != put(key="e\u0301")["signature"]
    assert put(key="a%2Fb")["signature"] != put(key="a/b")["signature"]
    assert presign(expires="61")["signature"] != pre["signature"]
    pre_raw = pre["canonical"].encode("ascii")
    bad_query_space = pre_raw.replace(b"attachment%3B%20", b"attachment%3B+", 1)
    cases.append(mutation("query-space-as-form-plus", bad_query_space, pre_raw))
    token_case = presign(token="session+/= token")
    assert "X-Amz-Security-Token=session%2B%2F%3D%20token" in token_case["query"]
    assert token_case["signature"] != pre["signature"]
    assert time_window("20261101T090030Z", credentials_end="20261101T090040Z") == "within"
    assert time_window("20261101T090040Z", credentials_end="20261101T090040Z") == "at-or-after-end"
    assert time_window("20261101T085959Z") == "before-issue"
    assert time_window("20261101T090000Z", expires=0) == "invalid-expires"
    assert time_window("20261101T090000Z", expires=604801) == "invalid-expires"
    print(json.dumps({
        "inputs": {"access_key": ACCESS, "secret_ascii": SECRET.decode("ascii"),
                   "date": DATE, "region": REGION, "service": SERVICE, "key": KEY,
                   "body_hex": BODY.hex(), "body_bytes": len(BODY),
                   "payload_sha256_hex": sha(BODY),
                   "payload_sha256_base64": base64.b64encode(hashlib.sha256(BODY).digest()).decode("ascii")},
        "put": base, "authorization": authorization,
        "authorization_value_bytes": len(authorization.encode("ascii")),
        "wire_bytes": len(wire), "wire_repr": repr(wire),
        "canonical_repr": repr(raw),
        "presign": pre, "session_presign": token_case,
        "mutations": cases, "bad_hex_key_signature": bad_hex_key,
        "crlf_payload_sha256": sha(b"object-lab v1\r\n"),
        "expires_61_signature": presign(expires="61")["signature"],
        "time_arithmetic": {
            "09:00:30_credentials_end_09:00:40": time_window("20261101T090030Z", credentials_end="20261101T090040Z"),
            "09:00:40_credentials_end_09:00:40": time_window("20261101T090040Z", credentials_end="20261101T090040Z"),
            "08:59:59": time_window("20261101T085959Z"),
            "expires_0": time_window("20261101T090000Z", expires=0),
            "expires_604801": time_window("20261101T090000Z", expires=604801),
        },
        "status": "PASS: local calculations; no server requests",
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
