#!/usr/bin/env python3
"""Validate the portable static handbook, without changing it or using the network.

Run from any directory: python3 scripts/check_site.py [SITE_ROOT] [--node-check].
Only explicit URL attributes and runtime resources are checked: example paths in
prose, shell commands and captured laboratory output are not deployment paths.
This is a structural CI check, not a JavaScript security audit or browser test.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import ipaddress
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

VOLUMES = {"networks", "linux", "bash", "postgres", "cache", "git"}
JSON_TYPES = {"application/json", "application/ld+json"}
JS_TYPES = {"", "text/javascript", "application/javascript", "module"}
URL_ATTRIBUTES = {"href", "xlink:href", "src", "poster", "action", "formaction", "data", "cite"}
ACTIVE_HREF_TAGS = {"link", "use", "image", "feimage"}
NETWORK_CALL = re.compile(r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|importScripts|sendBeacon)\s*\(")
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
CSS_IMPORT = re.compile(r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1", re.I)
JS_IMPORT = re.compile(r"\bimport\s*(?:\(\s*|[^;\n]*?\bfrom\s*)?['\"]([^'\"]+)['\"]")


def reject_non_json_number(value):
    raise ValueError(f"{value} is not a valid JSON number")


def parse_json(text):
    # Python's default accepts NaN and Infinity, unlike JSON.parse in the reader.
    return json.loads(text, parse_constant=reject_non_json_number)


@dataclass
class Script:
    attrs: dict
    line: int
    text: str = ""


@dataclass
class Page(HTMLParser):
    path: Path
    ids: list[str] = field(default_factory=list)
    urls: list[tuple[str, int, bool]] = field(default_factory=list)
    scripts: list[Script] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self._script = None
        self._style = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and a["id"]:
            self.ids.append(a["id"])
        if tag == "a" and a.get("name"):
            # Old-style named anchors still work in a browser.
            if a["name"] != a.get("id"):
                self.ids.append(a["name"])
        if tag == "base":
            self.parse_errors.append("<base> changes relative URL resolution; use portable relative links")
        for name in URL_ATTRIBUTES:
            value = a.get(name)
            if value and (name != "data" or tag == "object"):
                active = name in {"src", "poster", "data"} or (name in {"href", "xlink:href"} and tag in ACTIVE_HREF_TAGS)
                self.urls.append((value, self.getpos()[0], active))
        if a.get("srcset"):
            # Embedded data URIs can contain commas; a single one has no path to resolve.
            if a["srcset"].lstrip().startswith("data:"):
                self.parse_errors.append("data: srcset is unsupported by the checker; use src for embedded data")
            else:
                for item in a["srcset"].split(","):
                    if item.strip():
                        self.urls.append((item.strip().split()[0], self.getpos()[0], True))
        if a.get("style"):
            self.styles.append(a["style"])
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"\burl\s*=\s*(.*)", a.get("content", ""), re.I)
            if match:
                self.urls.append((match.group(1).strip(" '\""), self.getpos()[0], True))
        if tag == "script":
            self._script = Script(a, self.getpos()[0])
            self.scripts.append(self._script)
        if tag == "style":
            self._style = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            self._script = None
        if tag == "style" and self._style is not None:
            self.styles.append("".join(self._style))
            self._style = None

    def handle_data(self, text):
        if self._script is not None:
            self._script.text += text
        if self._style is not None:
            self._style.append(text)


class SiteChecker:
    def __init__(self, root: Path, node_check=False):
        self.root = Path(root).resolve()
        self.node_check = node_check
        self.errors: list[str] = []
        self.pages: dict[Path, Page] = {}
        self.json_data: dict[Path, dict] = {}
        self.checked_urls = 0
        self.checked_js = 0
        self.json_blocks = 0
        self.json_files = 0
        self.reference_counts = {}
        self._resource_seen = set()
        self._js_sources = []

    def label(self, path):
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def error(self, path, message):
        self.errors.append(f"{self.label(path)}: {message}")

    def url(self, source: Path, value: str, *, active=False, location="URL"):
        """Resolve like a browser, with a directory index and URL-decoded anchor."""
        self.checked_urls += 1
        value = value.strip()
        if re.match(r"^[A-Za-z]:[\\/]", value):
            self.error(source, f"{location}: machine-specific Windows path {value!r}")
            return
        try:
            parsed = urlsplit(value)
            host = (parsed.hostname or "").lower()
        except ValueError as exc:
            self.error(source, f"{location}: malformed URL {value!r}: {exc}")
            return
        scheme = parsed.scheme.lower()
        try:
            address = ipaddress.ip_address(host)
            local_host = address.is_loopback or address.is_unspecified
        except ValueError:
            local_host = host == "localhost" or host.endswith(".localhost")
        if scheme == "file" or local_host:
            self.error(source, f"{location}: machine-specific URL {value!r}")
            return
        if scheme or parsed.netloc:
            if scheme == "javascript":
                self.error(source, f"{location}: javascript: URL is not portable content")
            elif active and scheme != "data":
                self.error(source, f"{location}: external active resource {value!r}")
            return  # Source citations and mailto: links do not require the network in CI.
        decoded = unquote(parsed.path)
        if decoded.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", decoded):
            self.error(source, f"{location}: absolute path {value!r} breaks offline/project Pages navigation")
            return
        target = (source.parent / decoded).resolve() if decoded else source.resolve()
        if not target.is_relative_to(self.root):
            self.error(source, f"{location}: URL escapes the published site: {value!r}")
            return
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            self.error(source, f"{location}: missing local file {value!r}")
            return
        fragment = unquote(parsed.fragment)
        if fragment and target.suffix.lower() in {".html", ".htm"}:
            # Text fragments are a browser feature, rather than an element ID.
            fragment = fragment.split(":~:text=", 1)[0]
            if fragment and (target not in self.pages or fragment not in self.pages[target].ids):
                self.error(source, f"{location}: missing anchor {fragment!r} in {self.label(target)} ({value!r})")
        if active and target.suffix.lower() in {".css", ".js", ".mjs"}:
            self.resource(target)

    def css(self, path, text):
        for match in CSS_URL.finditer(text):
            # A fragment in inline CSS/SVG refers to this document's definitions.
            if match.group(2).strip().startswith("#"):
                continue
            self.url(path, match.group(2), active=True, location="CSS url()")
        for match in CSS_IMPORT.finditer(text):
            self.url(path, match.group(2), active=True, location="CSS @import")

    def javascript(self, path, text, label):
        if NETWORK_CALL.search(text):
            self.error(path, f"{label}: runtime network API detected; the offline reader must be self-contained")
        for match in JS_IMPORT.finditer(text):
            self.url(path, match.group(1), active=True, location=f"{label} import")
        # Legacy supplemental search index creates links at runtime.
        for match in re.finditer(r"\b(?:window\.)?BOOK_SEARCH\s*=\s*", text):
            try:
                rows, _ = json.JSONDecoder(parse_constant=reject_non_json_number).raw_decode(text[match.end():])
            except ValueError as exc:
                self.error(path, f"{label}: invalid BOOK_SEARCH JSON: {exc}")
                continue
            if not isinstance(rows, list):
                self.error(path, f"{label}: BOOK_SEARCH must be a list")
                continue
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("url"), str):
                    self.error(path, f"{label}: malformed BOOK_SEARCH row")
                else:
                    self.url(path, row["url"], location="BOOK_SEARCH")
        self._js_sources.append((path, label, text))

    def resource(self, path):
        if path in self._resource_seen:
            return
        self._resource_seen.add(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".css":
            self.css(path, text)
        else:
            self.javascript(path, text, "external JavaScript")

    def embedded_references(self, path, data):
        page = self.pages[path]
        book = data.get("book-data")
        if book is not None:
            if not isinstance(book, list) or not book:
                self.error(path, "book-data must be a nonempty list")
            else:
                chapter_ids = []
                for chapter in book:
                    if not isinstance(chapter, dict) or not isinstance(chapter.get("id"), str):
                        self.error(path, "book-data contains a malformed chapter")
                        continue
                    chapter_ids.append(chapter["id"])
                    if chapter["id"] not in page.ids:
                        self.error(path, f"book-data chapter has no HTML anchor: {chapter['id']!r}")
                if len(chapter_ids) != len(set(chapter_ids)):
                    self.error(path, "book-data has duplicate chapter IDs")
        glossary = data.get("glossary-data")
        if glossary is not None:
            if not isinstance(glossary, list):
                self.error(path, "glossary-data must be a list")
            else:
                for index, term in enumerate(glossary):
                    if not isinstance(term, list) or len(term) != 2 or not all(isinstance(x, str) and x for x in term):
                        self.error(path, f"glossary-data[{index}] must contain a term and definition")
                    self.url(path, f"#glossary-term-{index}", location="glossary-data")
        commands = data.get("command-reference-data")
        terms = data.get("library-glossary-data")
        if commands is not None:
            if not isinstance(commands, list):
                self.error(path, "command-reference-data must be a list")
                commands = []
            names = []
            for command in commands:
                if not isinstance(command, dict) or not all(isinstance(command.get(k), str) and command[k] for k in ("name", "purpose", "syntax", "chapter")):
                    self.error(path, "command-reference-data contains a malformed command")
                    continue
                names.append(command["name"])
                volume = command.get("volume", "bash")
                self.reference_target(path, volume, command["chapter"], f"command {command['name']!r}")
                flags = command.get("flags")
                if not isinstance(flags, list):
                    self.error(path, f"command {command['name']!r}: flags must be a list")
                    continue
                for flag in flags:
                    if not isinstance(flag, dict) or not all(isinstance(flag.get(k), str) and flag[k] for k in ("flag", "action", "when", "example", "result")):
                        self.error(path, f"command {command['name']!r}: malformed flag explanation")
            if len(names) != len(set(names)):
                self.error(path, "command-reference-data contains duplicate command names")
        if terms is not None:
            if not isinstance(terms, list):
                self.error(path, "library-glossary-data must be a list")
                terms = []
            for term in terms:
                if not isinstance(term, dict) or not all(isinstance(term.get(k), str) and term[k] for k in ("term", "definition", "volume", "anchor")):
                    self.error(path, "library-glossary-data contains a malformed definition")
                    continue
                self.reference_target(path, term["volume"], term["anchor"], f"glossary {term['term']!r}")
        comparisons = data.get("flag-comparison-data")
        if comparisons is not None:
            if not isinstance(comparisons, list):
                self.error(path, "flag-comparison-data must be a list")
            else:
                known = {c.get("name") for c in (commands or []) if isinstance(c, dict)}
                for pair in comparisons:
                    if not isinstance(pair, dict) or not all(isinstance(pair.get(k), str) and pair[k] for k in ("command", "key", "base", "variant", "why")):
                        self.error(path, "flag-comparison-data contains a malformed comparison")
                    elif pair["command"] not in known:
                        self.error(path, f"flag comparison references unknown command {pair['command']!r}")
        if commands is not None or terms is not None:
            self.reference_counts[self.label(path)] = {"commands": len(commands or []), "definitions": len(terms or [])}

    def reference_target(self, path, volume, anchor, label):
        if not isinstance(volume, str) or volume not in VOLUMES:
            self.error(path, f"{label}: unknown volume {volume!r}")
            return
        if not isinstance(anchor, str) or not anchor:
            self.error(path, f"{label}: target anchor must be a nonempty string")
            return
        target = self.root / volume / "index.html"
        if target not in self.pages or anchor not in self.pages[target].ids:
            self.error(path, f"{label}: missing target {volume}/index.html#{anchor}")

    def check(self):
        if not (self.root / "index.html").is_file():
            self.error(self.root / "index.html", "site entry point is missing")
        files = sorted(p for p in self.root.rglob("*") if p.is_file() and not any(x.startswith(".") for x in p.relative_to(self.root).parts) and p.relative_to(self.root).parts[:2] not in {("cache", "sources"), ("git", "sources")})
        for path in files:
            if path.suffix.lower() in {".html", ".htm"}:
                page = Page(path)
                try:
                    page.feed(path.read_text(encoding="utf-8"))
                    page.close()
                except (UnicodeError, ValueError) as exc:
                    self.error(path, f"cannot parse HTML: {exc}")
                self.pages[path] = page
            elif path.suffix.lower() == ".json":
                self.json_files += 1
                try:
                    parse_json(path.read_text(encoding="utf-8"))
                except (UnicodeError, ValueError) as exc:
                    self.error(path, f"invalid JSON file: {exc}")
        for path, page in self.pages.items():
            for ident, count in Counter(page.ids).items():
                if count > 1:
                    self.error(path, f"duplicate HTML ID/anchor {ident!r} ({count} occurrences)")
            for error in page.parse_errors:
                self.error(path, error)
            for value, line, active in page.urls:
                self.url(path, value, active=active, location=f"line {line}")
            for style in page.styles:
                self.css(path, style)
            data = {}
            for script in page.scripts:
                typ = script.attrs.get("type", "").lower()
                if typ in JSON_TYPES:
                    self.json_blocks += 1
                    try:
                        value = parse_json(script.text)
                    except ValueError as exc:
                        self.error(path, f"line {script.line}: invalid embedded JSON: {exc}")
                        continue
                    if script.attrs.get("id"):
                        data[script.attrs["id"]] = value
                elif typ in JS_TYPES and not script.attrs.get("src"):
                    self.javascript(path, script.text, f"inline {'module ' if typ == 'module' else ''}script line {script.line}")
            self.json_data[path] = data
            if path.parent.name in VOLUMES and path.name == "index.html":
                for required in ("book-data", "glossary-data", "command-reference-data", "library-glossary-data", "flag-comparison-data"):
                    if required not in data:
                        self.error(path, f"missing required embedded JSON {required!r}")
            self.embedded_references(path, data)
        main_data = [self.json_data[self.root / v / "index.html"] for v in sorted(VOLUMES) if self.root / v / "index.html" in self.json_data]
        if len(main_data) > 1:
            # Command catalogs and experiments may be extended by a particular
            # volume. The cross-volume glossary is deliberately the same in all.
            for key in ("library-glossary-data",):
                if any(data.get(key) != main_data[0].get(key) for data in main_data[1:]):
                    self.error(self.root / "index.html", f"shared {key} differs between volumes")
        if self.node_check:
            self.check_javascript_syntax()
        return not self.errors

    def check_javascript_syntax(self):
        node = shutil.which("node")
        if not node:
            self.error(self.root, "--node-check requested but node is not installed")
            return
        # Check every shipped JS file, including downloadable laboratory tools.
        known = {p for p, _, _ in self._js_sources}
        for path in sorted(p for p in self.root.rglob("*") if p.suffix in {".js", ".mjs"}):
            if ".git" not in path.parts and path.relative_to(self.root).parts[:2] not in {("cache", "sources"), ("git", "sources")} and path not in known:
                self._js_sources.append((path, "JavaScript file", path.read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory(prefix="handbook-js-check-") as directory:
            for index, (path, label, text) in enumerate(self._js_sources):
                extension = ".mjs" if path.suffix == ".mjs" or label.startswith("inline module ") else ".js"
                temp = Path(directory) / f"script-{index}{extension}"
                temp.write_text(text, encoding="utf-8")
                result = subprocess.run([node, "--check", str(temp)], text=True, capture_output=True)
                self.checked_js += 1
                if result.returncode:
                    # The temporary host path is irrelevant to the author.
                    detail = result.stderr.replace(str(temp), self.label(path)).strip()
                    self.error(path, f"{label}: JavaScript syntax error\n{detail}")

    def report(self):
        return {"ok": not self.errors, "html_pages": len(self.pages), "checked_urls": self.checked_urls, "json_blocks": self.json_blocks, "json_files": self.json_files, "javascript_syntax_checks": self.checked_js, "references": self.reference_counts, "errors": self.errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--node-check", action="store_true", help="also run node --check on shipped and embedded JavaScript")
    parser.add_argument("--json", action="store_true", help="print machine-readable results to stdout")
    args = parser.parse_args(argv)
    checker = SiteChecker(args.root, node_check=args.node_check)
    checker.check()
    if args.json:
        print(json.dumps(checker.report(), ensure_ascii=False, indent=2))
    else:
        for error in checker.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        r = checker.report()
        print(f"{'PASS' if r['ok'] else 'FAIL'}: {r['html_pages']} HTML pages, {r['checked_urls']} URL/anchor targets, {r['json_blocks']} embedded JSON blocks, {r['json_files']} JSON files, {r['javascript_syntax_checks']} JavaScript syntax checks")
    return 0 if not checker.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
