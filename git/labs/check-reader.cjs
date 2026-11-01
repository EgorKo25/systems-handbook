'use strict';
// Validate the JavaScript and data actually shipped in each independent reader.
// This checker neither runs chapter commands nor substitutes its own search parser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const volumes = ['git', 'go', 'jenkins', 'gitlab', 'practicum'];
const endMarker = "})(typeof globalThis !== 'undefined' ? globalThis : this);";
let assertions = 0;
function ok(value, message) { assert(value, message); assertions++; }
function equal(actual, expected, message) { assert.equal(actual, expected, message); assertions++; }
function jsonData(page, id) {
  const match = page.match(new RegExp('<script\\b[^>]*id="' + id + '"[^>]*>([\\s\\S]*?)<\\/script>'));
  ok(match, id + ': embedded JSON exists');
  return JSON.parse(match[1]);
}
function shippedSearch(page, slug) {
  const scripts = [...page.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  let executable = 0;
  for (const [, attributes, source] of scripts) {
    if (/type\s*=\s*["']application\/json["']/.test(attributes) || !source.trim()) continue;
    new vm.Script(source, {filename: slug + '/index.html:inline-' + (++executable)});
  }
  ok(executable > 0, slug + ': executable JavaScript found and parses');
  const candidates = scripts.map(m => m[2]).filter(s => s.includes('root.CommandReferenceSearch = search;'));
  equal(candidates.length, 1, slug + ': exactly one search implementation');
  const bundle = candidates[0];
  const normalize = bundle.indexOf('function normalizeText');
  const begin = bundle.lastIndexOf('(function (root) {', normalize);
  const end = bundle.indexOf(endMarker, begin);
  ok(begin >= 0 && end > begin, slug + ': search IIFE boundaries');
  const source = bundle.slice(begin, end + endMarker.length);
  const scope = {module: {exports: {}}, console};
  vm.runInNewContext(source, scope, {filename: slug + ':shipped-search', timeout: 10000});
  const search = scope.module.exports;
  for (const key of ['searchCommands', 'analyzeQuery', 'queryFromCode', 'queryForCommand', 'flagForms', 'tokenizeQuery']) {
    equal(typeof search[key], 'function', slug + ': exports ' + key);
  }
  // Native tools must link to the real lab rather than offer fake browser execution.
  const native = "['" + volumes.join("','") + "']";
  ok(bundle.includes(native + '.includes(command.volume)'), slug + ': native command guard');
  ok(bundle.includes('function mount(container,command){if(' + native + '.includes(command.volume))return;'), slug + ': flag emulator guard');
  return search;
}
function resultFor(search, commands, query, name, label) {
  const results = search.searchCommands(commands, query);
  equal(results.length, 1, label + ': one result for ' + query);
  const result = results[0];
  equal(result.command.name, name, label + ': selected name for ' + query);
  ok(result.analysis.explicit, label + ': explicit command for ' + query);
  return result;
}
function optionResult(search, commands, query, name, option, value, label) {
  const result = resultFor(search, commands, query, name, label);
  const found = result.analysis.options.find(item => item.name === option);
  ok(found, label + ': parsed option ' + option);
  ok(result.analysis.matchedIndices.some(index => search.flagForms(result.command.flags[index].flag).some(f => f.name === option)), label + ': matched flag ' + option);
  if (value !== undefined) {
    ok(found.hasValue, label + ': option has value ' + option);
    equal(found.value, value, label + ': option value ' + option);
  }
  return result;
}
const observed = [];
for (const slug of volumes) {
  const pagePath = path.join(root, slug, 'index.html');
  ok(fs.existsSync(pagePath), slug + ': build index.html before running the reader check');
  const page = fs.readFileSync(pagePath, 'utf8');
  ok(page.includes('data-volume="' + slug + '"'), slug + ': reader volume is independent');
  ok(page.includes('data-storage-key="' + slug + '-book-v1"'), slug + ': notes/read state storage key');
  const search = shippedSearch(page, slug);
  const commands = jsonData(page, 'command-reference-data');
  ok(Array.isArray(commands) && commands.length > 30, slug + ': substantial shipped command catalog');
  const disk = JSON.parse(fs.readFileSync(path.join(root, slug, 'commands.json'), 'utf8'));
  equal(JSON.stringify(commands), JSON.stringify(disk), slug + ': embedded and text/JSON export use same catalog');
  const names = new Set();
  let native = 0, flagQueries = 0, nonOptionForms = 0;
  for (const command of commands) {
    ok(!names.has(command.name), slug + ': unique command ' + command.name); names.add(command.name);
    for (const key of ['name', 'purpose', 'syntax', 'chapter', 'volume']) equal(typeof command[key], 'string', slug + ': command field ' + key);
    ok(Array.isArray(command.flags), slug + ': flags array ' + command.name);
    // Every card, including all new Go cards, must be selectable by its whole name.
    resultFor(search, commands, command.name, command.name, slug);
    for (const alias of command.aliases || []) resultFor(search, commands, alias, command.name, slug + ': alias');
    if (volumes.includes(command.volume)) native++;
    for (const [index, flag] of command.flags.entries()) {
      for (const key of ['flag', 'action', 'when', 'example', 'result']) equal(typeof flag[key], 'string', slug + ': flag field ' + command.name + ' ' + key);
      const forms = search.flagForms(flag.flag);
      if (!forms.length) { nonOptionForms++; continue; } // prose/context/subcommand forms are not option tokens
      for (const form of forms) {
        const value = form.qualifier || 'bookvalue';
        const query = command.name + ' ' + form.name + (form.expectsValue ? ' ' + value : '');
        const r = resultFor(search, commands, query, command.name, slug);
        ok(r.analysis.matchedIndices.includes(index), slug + ': reachable flag form ' + command.name + ' ' + flag.flag);
        flagQueries++;
      }
    }
  }
  ok(native >= 30, slug + ': Git/Go/Jenkins cards are present together');
  for (const [query, name, flag] of [
    ['git diff --cached', 'git diff', '--cached'],
    ['git reset --soft HEAD~1', 'git reset', '--soft'],
    ['git push --force-with-lease', 'git push', '--force-with-lease'],
    ['git fetch --prune', 'git fetch', '--prune'],
    ['grep -nE error access.log', 'grep', '-n'],
    ['go build -trimpath -buildvcs=false ./cmd/service', 'go build', '-trimpath'],
    ['go test -race -benchmem -count=1 ./...', 'go test', '-race'],
    ['go tool compile -%', 'go tool compile', '-%'],
    ['go tool compile -+', 'go tool compile', '-+'],
  ]) optionResult(search, commands, query, name, flag, undefined, slug);
  for (const [query, name, flag, value] of [
    ['go build -o ./out/app .', 'go build', '-o', './out/app'],
    ['go build -o=./out/app .', 'go build', '-o', './out/app'],
    ['go build -gcflags "example.org/lab=-N -l" .', 'go build', '-gcflags', 'example.org/lab=-N -l'],
    ["go build -ldflags='-X main.Version=1.2.3' .", 'go build', '-ldflags', '-X main.Version=1.2.3'],
    ["go test -run '^TestName$' -count 1 ./...", 'go test', '-run', '^TestName$'],
    ['go test -bench=BenchmarkUse -benchtime=200ms -timeout=30s ./...', 'go test', '-benchtime', '200ms'],
    ['go tool compile -p example.org/lab -o lab.a lab.go', 'go tool compile', '-p', 'example.org/lab'],
    ['go mod graph -go=1.25.0', 'go mod graph', '-go', '1.25.0'],
  ]) optionResult(search, commands, query, name, flag, value, slug);
  const build = commands.find(c => c.name === 'go build');
  const query = search.queryFromCode(build, ' -o ./out/app -gcflags "example.org/lab=-N -l" . | tee output.log');
  const round = resultFor(search, commands, query, 'go build', slug + ': code round trip');
  equal(round.analysis.options.find(o => o.name === '-o')?.value, './out/app', slug + ': code link preserves separate output value');
  equal(round.analysis.options.find(o => o.name === '-gcflags')?.value, 'example.org/lab=-N -l', slug + ': code link preserves quoted nested flags');
  ok(!query.includes('tee'), slug + ': code query stops at pipeline');
  const test = commands.find(c => c.name === 'go test');
  const regexQuery = search.queryFromCode(test, " -run '^(TestOne|TestTwo)$' -count 1 ./... | tee output.log");
  const regexResult = resultFor(search, commands, regexQuery, 'go test', slug + ': regex code round trip');
  equal(regexResult.analysis.options.find(o => o.name === '-run')?.value, '^(TestOne|TestTwo)$', slug + ': quoted alternation is not a pipeline');
  equal(regexResult.analysis.options.find(o => o.name === '-count')?.value, '1', slug + ': options after quoted regex retained');
  ok(!regexQuery.includes('tee'), slug + ': real pipeline still stops code query');

  // A real whole-name search must win over a shorter prefix even if ordering changes.
  for (const name of ['git diff', 'go build', 'go mod graph', 'go tool compile']) {
    const card = commands.find(c => c.name === name); ok(card, slug + ': expected compound card ' + name);
    const words = name.split(' ');
    const prefixes = words.slice(0, -1).map((_, i) => ({...card, name: words.slice(0, i + 1).join(' '), aliases: []}));
    resultFor(search, [...prefixes, card], name + ' -book-unknown', name, slug + ': longest prefix');
  }
  // Validate each actual diagram without requiring a historical fixed diagram count.
  const seen = new Set(); let steps = 0;
  for (const raw of page.matchAll(/<script\b[^>]*class="ds-data"[^>]*>([\s\S]*?)<\/script>/g)) {
    const d = JSON.parse(raw[1]);
    ok(!seen.has(d.id), slug + ': unique diagram ID ' + d.id); seen.add(d.id);
    equal(d.volume, slug, slug + ': diagram belongs to reader');
    ok(page.includes('id="' + d.chapter + '"'), slug + ': diagram chapter exists');
    const nodes = new Set(d.nodes.map(n => n.id)), edges = new Set(d.edges.map(e => e.id));
    equal(nodes.size, d.nodes.length, slug + ': unique nodes'); equal(edges.size, d.edges.length, slug + ': unique edges');
    ok(nodes.size >= 2, slug + ': diagram has participants');
    ok(d.steps.length >= 3, slug + ': diagram has meaningful progression');
    for (const e of d.edges) { ok(nodes.has(e.from), slug + ': edge source'); ok(nodes.has(e.to), slug + ': edge destination'); }
    for (const s of d.steps) {
      steps++;
      for (const key of ['title', 'explanation', 'actor']) equal(typeof s[key], 'string', slug + ': step ' + key);
      for (const x of s.focus) ok(nodes.has(x), slug + ': focus participant');
      for (const x of s.active) ok(edges.has(x), slug + ': active edge');
      equal(Object.keys(s.states).length, nodes.size, slug + ': state for every participant');
      for (const x of nodes) equal(typeof s.states[x], 'string', slug + ': state text');
      ok(s.fields.length > 0 && s.bands.length > 0, slug + ': before/after and visible fields');
      for (const field of s.fields) for (const key of ['name', 'before', 'after', 'why']) equal(typeof field[key], 'string', slug + ': field ' + key);
      for (const band of s.bands) for (const key of ['label', 'value', 'detail']) equal(typeof band[key], 'string', slug + ': band ' + key);
    }
  }
  ok(seen.size >= 1, slug + ': has an interactive diagram');
  ok(steps >= 6, slug + ': has enough diagram steps to validate');
  observed.push({volume: slug, commands: commands.length, nativeCards: native, flagQueries, nonOptionForms, diagrams: seen.size, steps});
}
console.log(JSON.stringify({ok: true, assertions, readers: observed}));
