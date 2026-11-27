#!/usr/bin/env python3
"""Evaluate a signed receipt for four independent reports against live PR metadata."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.github.com"
VERSION = "2026-03-10"
BEGIN = "<!-- tehatlas-pr-review:begin -->"
END = "<!-- tehatlas-pr-review:end -->"
ROLES = {
    "factcheck": "Фактчек",
    "frontend": "Фронтенд-тесты",
    "backend": "Бэкенд-тесты",
    "reader": "Редакторская вычитка книги",
}
SHA = r"[0-9a-f]{40}"
BINDING = re.compile(rf"Голова PR `({SHA})` · текущая целевая база `({SHA})`")
NAMESPACE = "tehatlas-pr-review-v1"
ID = re.compile(r"[A-Za-z0-9_./-]{1,100}")
CHECKOUT = Path(__file__).resolve().parents[1]
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
MAX_BODY = 8 * 1024 * 1024


class Blocked(ValueError):
    """A gate requirement has not been met."""


def require(condition, message):
    if not condition:
        raise Blocked(message)


def positive_int(value):
    return type(value) is int and value > 0


def unique_object(items):
    result = {}
    for field, value in items:
        require(field not in result, "duplicate JSON key")
        result[field] = value
    return result


def external_path(value):
    require(isinstance(value, str) and Path(value).is_absolute(), "external path must be absolute")
    resolved = Path(value).resolve()
    require(not resolved.is_relative_to(CHECKOUT), "trust data must be outside the code checkout")
    return resolved


def policy_from_text(raw):
    data = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(data, dict) and set(data) == {"repository", "base_ref", "authority", "reporters"},
            "invalid policy fields")
    require(isinstance(data["repository"], str) and REPO.fullmatch(data["repository"])
            and all(part not in {".", ".."} for part in data["repository"].split("/")),
            "invalid policy repository")
    require(data["base_ref"] == "main", "this gate expects the main branch")
    authority = data["authority"]
    require(isinstance(authority, dict)
            and set(authority) == {"principal", "github_user_id", "allowed_signers", "receipts_dir"}
            and isinstance(authority["principal"], str) and ID.fullmatch(authority["principal"])
            and (authority["github_user_id"] is None or positive_int(authority["github_user_id"])),
            "invalid authority identity or trust configuration")
    for key in ("allowed_signers", "receipts_dir"):
        authority[key] = external_path(authority[key])
    reporters = data["reporters"]
    require(isinstance(reporters, dict) and set(reporters) == set(ROLES)
            and all(isinstance(v, str) and ID.fullmatch(v) for v in reporters.values())
            and len(set(reporters.values())) == len(ROLES)
            and authority["principal"] not in reporters.values(), "four independent report sources required")
    return data


def review_block(body, head, base):
    require(isinstance(body, str) and body.count(BEGIN) == body.count(END) == 1,
            "PR body must contain exactly one review block")
    lines = body.splitlines()
    require(BEGIN in lines and END in lines and lines.index(BEGIN) < lines.index(END),
            "invalid review block boundaries")
    block = lines[lines.index(BEGIN) + 1:lines.index(END)]
    bindings = [BINDING.fullmatch(line.strip()) for line in block
                if line.strip().startswith("Голова PR")]
    require(len(bindings) == 1 and bindings[0] is not None
            and bindings[0].groups() == (head, base), "PR block head/base is missing or stale")
    for label in ROLES.values():
        row = re.compile(r"- \[[ xX]\] " + re.escape(label) + r"(?: · [^\n]+)?")
        require(sum(row.fullmatch(line.strip()) is not None for line in block) == 1,
                "expected one row for " + label)


def pull_snapshot(pull, ref, policy, number):
    repo = policy["repository"]
    head, base = pull["head"]["sha"], pull["base"]["sha"]
    author = pull["user"]["id"]
    require(pull["number"] == number and pull["state"] == "open" and pull["draft"] is False,
            "expected the open, non-draft requested PR")
    require(pull["base"]["repo"]["full_name"] == repo and pull["base"]["ref"] == "main"
            and ref["ref"] == "refs/heads/main" and ref["object"]["type"] == "commit"
            and re.fullmatch(SHA, head) and re.fullmatch(SHA, base)
            and ref["object"]["sha"] == base, "PR base does not match current main")
    require(positive_int(author) and author != policy["authority"]["github_user_id"],
            "PR author cannot sign the receipt")
    body = pull["body"]
    review_block(body, head, base)
    return (head, base, author, body)


def read_signed_manifest(authority, number):
    file = authority["receipts_dir"] / f"{number}.json"
    signature = external_path(str(file.with_suffix(".json.sig")))
    try:
        with external_path(str(file)).open("rb") as stream:
            raw = stream.read(65537)
        require(signature.is_file(), "signed manifest or signature is unavailable")
    except FileNotFoundError as error:
        raise Blocked("signed manifest or signature is unavailable") from error
    require(len(raw) <= 65536, "signed manifest exceeds the size limit")
    result = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(authority["allowed_signers"]),
         "-I", authority["principal"], "-n", NAMESPACE, "-s", str(signature)],
        input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
    )
    require(result.returncode == 0, "manifest signature is not trusted")
    return raw


def evaluate(pull, ref, raw, policy, number):
    head, base, _, _ = pull_snapshot(pull, ref, policy, number)
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    expected = {"schema": NAMESPACE, "repository": policy["repository"], "pr": number, "head": head,
                "base": base, "authority": policy["authority"]["principal"]}
    require(isinstance(manifest, dict) and set(manifest) == set(expected) | {"reports"}
            and type(manifest["pr"]) is int
            and all(manifest.get(key) == value for key, value in expected.items()),
            "signed manifest does not match the exact PR/head/base or authority")
    reports = manifest["reports"]
    require(isinstance(reports, list) and len(reports) == len(ROLES), "expected exactly four reports")
    accepted, digests = {}, set()
    for report in reports:
        require(isinstance(report, dict)
                and set(report) == {"role", "reporter", "sha256", "decision", "outcome", "evidence"},
                "invalid report fields")
        role, digest = report["role"], report["sha256"]
        require(isinstance(role, str) and role in ROLES and role not in accepted
                and report["reporter"] == policy["reporters"][role], "unexpected or duplicate report source")
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
                and digest not in digests, "missing or reused report digest")
        require(report["decision"] == "accepted" and report["outcome"] in ("passed", "not_applicable")
                and isinstance(report["evidence"], str) and bool(report["evidence"].strip()),
                "report has no accepted decision and evidence")
        accepted[role] = {"reporter": report["reporter"], "sha256": digest, "outcome": report["outcome"]}
        digests.add(digest)
    return expected | {"receipts": accepted, "manifest_sha256": hashlib.sha256(raw).hexdigest()}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, repository, token=None):
        self.prefix = f"{API}/repos/{repository}"
        self.opener = build_opener(NoRedirect())
        self.headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": VERSION,
                        "User-Agent": "tehatlas-review-gate", "Cache-Control": "no-cache"}
        if token:
            self.headers["Authorization"] = "Bearer " + token

    def get(self, path):
        request = Request(self.prefix + path, headers=self.headers)
        try:
            with self.opener.open(request, timeout=12) as response:
                body = response.read(MAX_BODY + 1)
                require(len(body) <= MAX_BODY, "GitHub response exceeded size limit")
        except HTTPError as error:
            error.close()
            raise Blocked(f"GitHub GET failed with HTTP {error.code}") from error
        except (URLError, OSError) as error:
            raise Blocked("GitHub GET network failure") from error
        return json.loads(body)


def evaluate_live(api, policy, number):
    path = f"/pulls/{number}"
    ref_path = "/git/ref/heads/main"
    pull, ref = api.get(path), api.get(ref_path)
    snapshot = pull_snapshot(pull, ref, policy, number)
    raw = read_signed_manifest(policy["authority"], number)
    result = evaluate(pull, ref, raw, policy, number)
    require(read_signed_manifest(policy["authority"], number) == raw,
            "signed manifest changed during the evaluation")
    require(pull_snapshot(api.get(path), api.get(ref_path), policy, number) == snapshot,
            "PR changed during the review evaluation")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path, help="operator-owned policy file outside the PR")
    parser.add_argument("--pr", required=True, type=int)
    args = parser.parse_args()
    require(positive_int(args.pr), "PR number must be positive")
    policy = policy_from_text(external_path(str(args.policy.absolute())).read_text())
    api = GitHub(policy["repository"], os.environ.get("TEHATLAS_REVIEW_GATE_TOKEN"))
    result = evaluate_live(api, policy, args.pr)
    print(json.dumps(result | {"state": "passed"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Blocked as error:
        sys.exit(f"review-gate: {error}")
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired):
        sys.exit("review-gate: malformed GitHub data or policy")
