#!/usr/bin/env python3
"""Independent offline checks; never starts Docker or imports lesson modules.

This checks publication links and the command-help contract against the actual
reader's flag parser. It is not evidence of a successful container build/run.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
VOLUME = ROOT / 'docker'
errors: list[str] = []
checks = 0


def require(condition: bool, description: str) -> None:
    global checks
    checks += 1
    if not condition:
        errors.append(description)


def assignment(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node.value
    raise ValueError(f'No assignment for {name}')


def accumulated_lists(tree: ast.Module, name: str) -> list[ast.expr]:
    """Read declaration + later += additions without executing Python code."""
    result: list[ast.expr] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            if not isinstance(node.value, (ast.List, ast.Tuple)):
                raise ValueError(f'{name} must be a literal list/tuple')
            result = list(node.value.elts)
        elif (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name)
              and node.target.id == name):
            if (result is None or not isinstance(node.op, ast.Add)
                    or not isinstance(node.value, (ast.List, ast.Tuple))):
                raise ValueError(f'Unsupported accumulated declaration of {name}')
            result.extend(node.value.elts)
    if result is None:
        raise ValueError(f'No declaration for {name}')
    return result


class Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.assets: list[str] = []
        self.scripts: list[tuple[dict[str, str], str]] = []
        self._script: tuple[dict[str, str], list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if tag == 'a' and values.get('href'):
            self.links.append(values['href'])
        if tag in ('img', 'script') and values.get('src'):
            self.assets.append(values['src'])
        if tag == 'link' and values.get('href'):
            self.assets.append(values['href'])
        if tag == 'script':
            self._script = (values, [])

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script' and self._script is not None:
            self.scripts.append((self._script[0], ''.join(self._script[1])))
            self._script = None


def parse(path: Path) -> Document:
    result = Document()
    result.feed(path.read_text(encoding='utf-8'))
    return result


def local_links(document: Document, source: Path, same_page_ids: set[str]) -> None:
    for href in document.links + document.assets:
        url = urlsplit(href)
        if url.scheme in ('https', 'http', 'data', 'mailto') or url.netloc:
            continue
        require(not url.scheme, f'{source.name}: unsupported link scheme {href!r}')
        target = (source.parent / unquote(url.path)).resolve() if url.path else source
        if not url.path or target == source.resolve():
            if url.fragment:
                require(unquote(url.fragment) in same_page_ids,
                        f'{source.name}: missing same-volume anchor {href!r}')
            continue
        require(target.is_file(), f'{source.name}: missing local target {href!r}')
        if url.fragment and target.is_file() and target.suffix == '.html':
            require(unquote(url.fragment) in set(parse(target).ids),
                    f'{source.name}: missing target anchor {href!r}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-only', action='store_true',
                        help='Check sources before docker/index.html is built.')
    parser.add_argument('--reader', type=Path,
                        help='Inspect a temporary built reader without replacing the published file.')
    args = parser.parse_args()

    # Read literal declarations, not executable Python lesson code.
    config_tree = ast.parse((VOLUME / 'volume_config.py').read_text())
    config_node = assignment(config_tree, 'CONFIG')
    if not isinstance(config_node, ast.Call):
        raise ValueError('Expected a literal dict(...) volume configuration')
    config = {item.arg: ast.literal_eval(item.value) for item in config_node.keywords}
    chapters = [item for _, group in config['sections'] for item in group]
    require(len(chapters) == len(set(chapters)), 'Duplicate declared chapter ID')
    chapter_ids = set(chapters)
    source_documents: list[tuple[Path, Document]] = []
    for chapter in chapters:
        if chapter == '99-glossary':
            continue
        path = VOLUME / 'sources' / f'{chapter}.html'
        require(path.is_file(), f'Missing chapter source {chapter}')
        if path.is_file():
            doc = parse(path)
            chapter_ids.update(doc.ids)
            source_documents.append((path, doc))
    for path, doc in source_documents:
        # Links in fragments are resolved from the published reader location.
        local_links(doc, VOLUME / 'index.html', chapter_ids)

    reference_tree = ast.parse((VOLUME / 'sources' / 'reference.py').read_text())
    glossary = [ast.literal_eval(item)
                for item in accumulated_lists(reference_tree, 'GLOSSARY')]
    terms = [term.casefold() for term, _ in glossary]
    require(len(terms) == len(set(terms)), 'Duplicate case-insensitive glossary term')
    command_list = accumulated_lists(reference_tree, 'COMMANDS')
    commands: dict[str, list[str]] = {}
    for call in command_list:
        if not isinstance(call, ast.Call) or len(call.args) < 5:
            raise ValueError('Expected command(...) declaration')
        name = ast.literal_eval(call.args[0])
        require(name not in commands, f'Duplicate command-help entry {name}')
        chapter = ast.literal_eval(call.args[3])
        require(chapter in chapter_ids, f'{name}: unknown destination chapter {chapter}')
        flags = call.args[5] if len(call.args) > 5 else ast.List(elts=[], ctx=ast.Load())
        if not isinstance(flags, (ast.List, ast.Tuple)):
            raise ValueError(f'{name}: flags must be literal declarations')
        commands[name] = [ast.literal_eval(flag.args[0]) for flag in flags.elts]

    # Catch conspicuous concatenation, not ordinary Russian word length.
    for node in ast.walk(reference_tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for word in re.findall(r'[А-Яа-яЁё]{46,}', node.value):
                require(False, f'reference.py:{node.lineno}: unreadable concatenation {word!r}')

    reader = args.reader.resolve() if args.reader else VOLUME / 'index.html'
    parser_source = reader if reader.is_file() else ROOT / 'bash' / 'index.html'
    page = parser_source.read_text()
    start = page.index('function flagForms(label) {')
    end = page.index('function optionSpecifications(', start)
    # Execute only this pure function, not the document's application scripts.
    node_script = r'''
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {};
vm.createContext(context);
vm.runInContext(input.source, context, {timeout:1000});
const result = Object.fromEntries(Object.entries(input.commands).map(([name, flags]) =>
  [name, flags.flatMap(label => context.flagForms(label))]));
process.stdout.write(JSON.stringify(result));
'''
    completed = subprocess.run(['node', '-e', node_script],
                               input=json.dumps(dict(source=page[start:end], commands=commands)),
                               capture_output=True, text=True, check=True, timeout=10)
    forms = json.loads(completed.stdout)
    # Independent expectations from the Docker CLI interface, not from labels.
    expected = {
        'docker': {'--context': True, '--host': True, '--version': False, '--debug': False},
        'docker run': {'--name': True, '--pull': True, '--detach': False,
                       '--interactive': False, '--tty': False, '--publish': True,
                       '--env': True, '--mount': True, '--read-only': False,
                       '--user': True, '--memory': True, '--cpus': True,
                       '--cap-drop': True, '--security-opt': True, '--rm': False},
        'docker ps': {'--all': False, '--filter': True, '--no-trunc': False},
        'docker logs': {'--tail': True, '--since': True, '--timestamps': False, '--follow': False},
        'docker stop': {'--timeout': True},
        'docker exec': {'-i': False, '-t': False, '--user': True},
        'docker buildx build': {'--file': True, '--tag': True, '--platform': True,
                               '--load': False, '--push': False, '--no-cache': False,
                               '--pull': False, '--secret': True, '--sbom': None,
                               '--provenance': None},
        'docker image save': {'--output': True},
        'docker image load': {'--input': True},
        'docker stats': {'--no-stream': False},
        'docker system df': {'--verbose': False},
        'docker compose': {'--file': True, '--project-name': True},
        'docker compose up': {'--detach': False, '--no-deps': False, '--force-recreate': False},
        'docker compose down': {'--volumes': False},
        'docker context ls': {},
        'docker context inspect': {},
        'docker context create': {'--docker': True},
        'docker version': {},
        'docker info': {},
        'docker create': {'--name': True, '--pull': True},
        'docker start': {},
        'docker wait': {},
        'docker attach': {},
        'docker rm': {},
        'docker port': {},
        'docker network create': {'--driver': True, '--subnet': True},
        'docker network inspect': {},
        'docker volume create': {},
        'docker volume inspect': {},
        'docker image inspect': {'--format': True},
        'docker image history': {'--no-trunc': False},
        'docker buildx ls': {},
        'docker buildx inspect': {'--bootstrap': False},
        'docker buildx imagetools inspect': {},
        'docker events': {'--since': True, '--filter': True},
        'docker login': {'--password-stdin': False},
        'docker compose config': {},
        'docker compose ps': {},
        'docker compose logs': {'--tail': True, '--timestamps': False},
        'docker compose stop': {},
        'docker compose start': {},
    }
    for name, options in expected.items():
        require(name in forms, f'Missing expected command help {name}')
        actual = {form['name']: form['expectsValue'] for form in forms.get(name, [])}
        for option, takes_value in options.items():
            require(option in actual, f'{name}: reader cannot recognize {option}')
            # The two attestation shorthands allow optional values in Buildx;
            # check recognition, not mandatory-argument semantics for them.
            if option in actual and takes_value is not None:
                require(actual[option] is takes_value,
                        f'{name}: wrong argument contract for {option}')

    for name, labels in commands.items():
        for label in labels:
            require(not re.search(r'-[A-Za-z][A-Za-z-]*,\s+--', label),
                    f'{name}: comma-separated aliases are unsupported by reader: {label}')

    if not args.source_only:
        require(reader.is_file(), 'Build docker/index.html, or use --source-only')
        if reader.is_file():
            doc = parse(reader)
            duplicates = [key for key, count in Counter(doc.ids).items() if count > 1]
            require(not duplicates, f'Duplicate HTML IDs: {duplicates}')
            for chapter in chapters:
                require(chapter in doc.ids, f'Published reader misses chapter {chapter}')
            payloads = {attributes.get('id'): json.loads(body)
                        for attributes, body in doc.scripts
                        if attributes.get('type') == 'application/json'}
            book = payloads.get('book-data', [])
            require([item['id'] for item in book] == chapters,
                    'Published book-data order disagrees with declared reading order')
            for item in book:
                require(isinstance(item.get('words'), int) and item['words'] > 0,
                        f'{item.get("id")}: invalid reading-size metadata')
            published_commands = {
                item['name'] for item in payloads.get('command-reference-data', [])
                if item.get('volume') == 'docker'
            }
            require(published_commands == set(commands),
                    'Published Docker command cards differ from accumulated source declarations')
            local_links(doc, reader, set(doc.ids))

    if errors:
        print(f'Docker static review: FAIL ({len(errors)} issues, {checks} checks)')
        for error in errors:
            print(' -', error)
        return 1
    print(f'Docker static review: PASS ({checks} checks; {len(source_documents)} source chapters; '
          f'{len(commands)} command entries; {len(glossary)} terms)')
    print('No Docker/host service commands were run; container behavior remains a manual check.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError) as error:
        print(f'Docker static review: ERROR: {error}', file=sys.stderr)
        sys.exit(2)
