#!/usr/bin/env python3
"""Verify signed review receipts against live PR metadata."""

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
TEXT_REVIEW_ROLE = "text_review"
TEXT_REVIEW_LABEL = "Ревью нейротекста"
REPORT_FIELDS = {"role", "reporter", "sha256", "decision", "outcome", "evidence"}
TECHNICAL_NA_PATHS = {
    ".github/PULL_REQUEST_TEMPLATE.md",
    "scripts/ops/plan_reserve_cleanup.py",
    "scripts/ops/reserve-cleanup.md",
    "scripts/review_gate.py",
    "tests/test_plan_reserve_cleanup.py",
    "tests/test_review_gate.py",
}
TECHNICAL_FILE_STATUSES = {"added", "modified", "removed", "renamed"}
SHA = r"[0-9a-f]{40}"
BINDING = re.compile(rf"Голова PR `({SHA})` · текущая целевая база `({SHA})`")
NAMESPACE = "tehatlas-pr-review-v1"
ID = re.compile(r"[A-Za-z0-9_./-]{1,100}")
WORK_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
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


def validate_text_review_assignment(config, reporters, authority):
    require(isinstance(config, dict) and set(config) == {"pr", "head", "base", "assignments"}
            and positive_int(config["pr"])
            and all(isinstance(config[key], str) and re.fullmatch(SHA, config[key]) for key in ("head", "base")),
            "text review policy requires an exact PR/head/base")
    assignments = config["assignments"]
    require(isinstance(assignments, dict) and set(assignments) == {"authors", "reader", "text_reviewer"}
            and isinstance(assignments["authors"], list) and bool(assignments["authors"]),
            "text review policy requires author, reader and text reviewer assignments")
    reporter_paths, work_ids = set(), set()
    participants = [("author", author) for author in assignments["authors"]]
    participants += [("reader", assignments["reader"]), (TEXT_REVIEW_ROLE, assignments["text_reviewer"])]
    for role, participant in participants:
        require(isinstance(participant, dict) and set(participant) == {"role", "reporter", "thread_id", "turn_id"}
                and participant["role"] == role, "invalid text review role assignment")
        reporter = participant["reporter"]
        require(isinstance(reporter, str) and ID.fullmatch(reporter)
                and all(part not in {"", ".", ".."} for part in reporter.split("/"))
                and reporter not in reporter_paths, "text review assignment reporter paths must be distinct")
        reporter_paths.add(reporter)
        for field in ("thread_id", "turn_id"):
            identifier = participant[field]
            require(isinstance(identifier, str) and WORK_ID.fullmatch(identifier)
                    and identifier != "00000000-0000-0000-0000-000000000000"
                    and identifier not in work_ids, "text review assignments require distinct full thread and turn IDs")
            work_ids.add(identifier)
    require(assignments["reader"]["reporter"] == reporters["reader"],
            "text review reader assignment does not match the policy reader")
    reviewer = assignments["text_reviewer"]["reporter"]
    require(reviewer not in reporters.values() and reviewer != authority["principal"],
            "text review reporter must be distinct from existing reviewers and authority")


def policy_from_text(raw):
    data = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(data, dict)
            and set(data) == {"repository", "base_ref", "authority", "reporters", "text_review"},
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
    validate_text_review_assignment(data["text_review"], reporters, authority)
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
    for label in (*ROLES.values(), TEXT_REVIEW_LABEL):
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


def read_signed_manifest(authority, number, *, text_review=False):
    suffix = ".text-review.json" if text_review else ".json"
    file = authority["receipts_dir"] / f"{number}{suffix}"
    label = "text review manifest" if text_review else "manifest"
    signature = external_path(str(file.with_suffix(".json.sig")))
    try:
        with external_path(str(file)).open("rb") as stream:
            raw = stream.read(65537)
        require(signature.is_file(), f"signed {label} or signature is unavailable")
    except FileNotFoundError as error:
        raise Blocked(f"signed {label} or signature is unavailable") from error
    require(len(raw) <= 65536, f"signed {label} exceeds the size limit")
    result = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(authority["allowed_signers"]),
         "-I", authority["principal"], "-n", NAMESPACE, "-s", str(signature)],
        input=raw, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
    )
    require(result.returncode == 0, f"{label} signature is not trusted")
    return raw


def receipt_matches(manifest, expected, *fields):
    return (isinstance(manifest, dict) and set(manifest) == set(expected).union(fields)
            and type(manifest["pr"]) is int
            and all(manifest.get(key) == value for key, value in expected.items()))


def text_review_evidence(entries):
    require(isinstance(entries, list) and bool(entries), "text review requires final HTML and anchors")
    paths = set()
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {"path", "anchors"}, "invalid text review HTML entry")
        path, anchors = entry["path"], entry["anchors"]
        require(isinstance(path, str) and re.fullmatch(r"(?:[\w.-]+/)*[\w.-]+\.html", path)
                and not {".", ".."}.intersection(path.split("/")) and path not in paths,
                "invalid or duplicate text review HTML path")
        require(isinstance(anchors, list) and bool(anchors)
                and all(isinstance(anchor, str) and re.fullmatch(r"[\w.:-]+", anchor) for anchor in anchors)
                and len(set(anchors)) == len(anchors), "invalid or duplicate text review anchors")
        paths.add(path)


def technical_scope(files, *, github=False):
    require(isinstance(files, list), "text review N/A requires a technical file list")
    scope = {}
    for file in files:
        require(isinstance(file, dict) and isinstance(file.get("status"), str)
                and file["status"] in TECHNICAL_FILE_STATUSES, "unrecognized text review N/A file status")
        fields = {"filename", "status"}
        if file["status"] == "renamed":
            fields.add("previous_filename")
        require(fields <= file.keys() and (github or file.keys() == fields)
                and ("previous_filename" not in file or "previous_filename" in fields),
                "incomplete text review N/A file entry")
        paths = fields - {"status"}
        require(all(isinstance(file[field], str) and file[field] in TECHNICAL_NA_PATHS for field in paths),
                "text review N/A requires explicitly allowlisted technical paths")
        require(file["filename"] not in scope and file.get("previous_filename") != file["filename"],
                "duplicate or invalid text review N/A file entry")
        entry = {field: file[field] for field in fields}
        scope[file["filename"]] = entry
    return [scope[name] for name in sorted(scope)]


def github_technical_scope(api, path, pull):
    count = pull.get("changed_files")
    # An eligible diff has at most one record per allowlisted destination.
    # The entire eligible list fits in one 100-item GitHub API page.
    require(type(count) is int and 0 <= count <= len(TECHNICAL_NA_PATHS),
            "text review N/A requires a complete technical changed_files count")
    files = api.get(path + "/files?per_page=100&page=1", single_page=True)
    require(isinstance(files, list) and len(files) == count, "incomplete GitHub file list for text review N/A")
    return technical_scope(files, github=True)


def evaluate_text_review(raw, expected, assignment, reader_digest, digests, read_scope):
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    require(receipt_matches(manifest, expected, "report", "assignments", "reader_report_sha256"),
            "signed text review manifest does not match the exact PR/head/base or authority")
    require(all(assignment[key] == expected[key] for key in ("pr", "head", "base")),
            "trusted text review assignment does not match the exact PR/head/base")
    assignments = assignment["assignments"]
    require(manifest["assignments"] == assignments, "signed text review assignments do not match trusted assignments")
    require(manifest["reader_report_sha256"] == reader_digest,
            "signed text review manifest does not match the accepted reader report")
    report = manifest["report"]
    require(isinstance(report, dict), "invalid text review report fields")
    fields = REPORT_FIELDS | {"open_findings", "reader_text", "html", "scope"}
    if report.get("outcome") == "not_applicable":
        fields.add("technical_files")
    require(set(report) == fields, "invalid text review report fields")
    require(report["role"] == TEXT_REVIEW_ROLE and report["reporter"] == assignments["text_reviewer"]["reporter"],
            "text review reporter does not match trusted identity")
    digest = report["sha256"]
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) and digest not in digests,
            "missing or reused text review digest")
    require(report["decision"] == "accepted"
            and all(isinstance(report[key], str) and report[key].strip() for key in ("evidence", "scope")),
            "text review requires an accepted decision, evidence and scope")
    require(type(report["open_findings"]) is int and report["open_findings"] == 0,
            "text review requires zero open findings")
    if report["outcome"] == "passed":
        require(report["reader_text"] is True, "a passed text review requires reader text")
        text_review_evidence(report["html"])
    else:
        require(report["outcome"] == "not_applicable" and report["reader_text"] is False
                and report["html"] == [], "text review N/A requires signed evidence of no reader-text changes")
        require(technical_scope(report["technical_files"]) == read_scope(),
                "signed text review N/A scope does not match the GitHub file list")
    return report


def evaluate(pull, ref, raw, text_raw, policy, number, read_scope):
    head, base, _, _ = pull_snapshot(pull, ref, policy, number)
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    expected = {"schema": NAMESPACE, "repository": policy["repository"], "pr": number, "head": head,
                "base": base, "authority": policy["authority"]["principal"]}
    require(receipt_matches(manifest, expected, "reports"),
            "signed manifest does not match the exact PR/head/base or authority")
    reports = manifest["reports"]
    require(isinstance(reports, list) and len(reports) == len(ROLES), "expected exactly four reports")
    accepted, digests = {}, set()
    for report in reports:
        require(isinstance(report, dict) and set(report) == REPORT_FIELDS,
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
    accepted[TEXT_REVIEW_ROLE] = evaluate_text_review(
        text_raw, expected, policy["text_review"], accepted["reader"]["sha256"], digests, read_scope,
    )
    return expected | {
        "receipts": accepted, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "text_review_manifest_sha256": hashlib.sha256(text_raw).hexdigest(),
    }


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

    def get(self, path, *, single_page=False):
        request = Request(self.prefix + path, headers=self.headers)
        try:
            with self.opener.open(request, timeout=12) as response:
                if single_page:
                    require(not response.headers.get("Link"), "unexpected pagination for text review N/A")
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
    text_raw = read_signed_manifest(policy["authority"], number, text_review=True)
    result = evaluate(pull, ref, raw, text_raw, policy, number, lambda: github_technical_scope(api, path, pull))
    require(read_signed_manifest(policy["authority"], number) == raw,
            "signed manifest changed during the evaluation")
    require(read_signed_manifest(policy["authority"], number, text_review=True) == text_raw,
            "signed text review manifest changed during the evaluation")
    current_pull, current_ref = api.get(path), api.get(ref_path)
    require(pull_snapshot(current_pull, current_ref, policy, number) == snapshot,
            "PR changed during the review evaluation")
    text_report = result["receipts"][TEXT_REVIEW_ROLE]
    if text_report["outcome"] == "not_applicable":
        require(github_technical_scope(api, path, current_pull) == technical_scope(text_report["technical_files"]),
                "GitHub file list changed during text review N/A evaluation")
        final_pull, final_ref = api.get(path), api.get(ref_path)
        require(pull_snapshot(final_pull, final_ref, policy, number) == snapshot
                and type(final_pull.get("changed_files")) is int
                and final_pull["changed_files"] == current_pull["changed_files"],
                "PR or changed_files changed during text review N/A evaluation")
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
