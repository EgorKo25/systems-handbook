'use strict';
// Validate the JavaScript and data actually shipped in each independent reader.
// This checker neither runs chapter commands nor substitutes its own search parser.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const volumes = JSON.parse(fs.readFileSync(path.join(root, 'published-volumes.json'), 'utf8')).volumes.filter(row => row.build === 'managed').map(row => row.slug);
const readerRootIndex=process.argv.indexOf('--reader-root');
const readerRoot=readerRootIndex>=0?path.resolve(process.argv[readerRootIndex+1]):root;
const onlyIndex=process.argv.indexOf('--only');
const selectedVolumes=onlyIndex>=0?process.argv[onlyIndex+1].split(','):volumes;
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
function queryForFlag(command, index, form, value) {
  const invocation = form.name + (form.expectsValue ? ' ' + value : '');
  const owner = command.flagScopes?.[index];
  return owner && owner !== command.name && command.name.startsWith(owner + ' ')
    ? owner + ' ' + invocation + ' ' + command.name.slice(owner.length + 1)
    : command.name + ' ' + invocation;
}
function commaAliasRegressions(search, commands, label) {
  // Use real frozen source cards. Expected spellings/operands are specified
  // explicitly, not discovered by flagForms (which would hide a lost alias).
  const template=commands.find(c=>c.name==='helm template');
  const get=commands.find(c=>c.name==='kubectl get');
  if(template && get) {
    ok(template.flags.some(f=>f.flag==='-f, --values <файл>'),label+': real Helm comma label');
    ok(get.flags.some(f=>f.flag==='--watch, -w'),label+': real kubectl boolean label');
    const check=(query,name,options,words,help) => {
      const result=resultFor(search,commands,query,name,label+': comma alias');
      equal(result.analysis.unmatched.length,0,label+': all requested aliases known');
      equal(JSON.stringify(result.analysis.words),JSON.stringify(words),label+': operands neither lost nor eaten');
      for(const [option,value]of options) {
        const found=result.analysis.options.find(item=>item.name===option);
        ok(found,label+': explicit expected option '+option);
        equal(found.hasValue,value!==null,label+': expected arity '+option);
        if(value!==null)equal(found.value,value,label+': exact option value '+option);
      }
      for(const text of help)ok(result.analysis.matchedIndices.some(i=>result.command.flags[i].flag===text),label+': correct explanation '+text);
      return result;
    };
    for(const invocation of ['-f "env[prod],east.yaml"','--values="env[prod],east.yaml"','-fenv[prod],east.yaml'])
      check('helm template ledger ./chart '+invocation,'helm template',
        [[invocation.startsWith('--')?'--values':'-f','env[prod],east.yaml']],['ledger','./chart'],['-f, --values <файл>']);
    for(const option of ['--namespace','-n'])
      check('kubectl '+option+' helm-lab get pods','kubectl get',[[option,'helm-lab']],['pods'],['--namespace NAME, -n NAME']);
    for(const watch of ['--watch','-w'])
      check('kubectl -n lab get '+watch+' pods -l app=ledger-api','kubectl get',
        [['-n','lab'],[watch,null],['-l','app=ledger-api']],['pods'],['--watch, -w']);
    for(const output of ['yaml','json']) {
      const result=check('kubectl --namespace lab get pods -o '+output,'kubectl get',
        [['--namespace','lab'],['-o',output]],['pods'],['-o yaml, -o json']);
      ok(!result.analysis.matchedIndices.some(i=>result.command.flags[i].flag==='-o wide'),label+': output qualifiers stay separate');
    }
    for(const follow of ['--follow','-f'])
      check('kubectl -n lab logs ledger-api '+follow+' -c api','kubectl logs',
        [['-n','lab'],[follow,null],['-c','api']],['ledger-api'],['--follow, -f']);
    const root=commands.find(c=>c.name==='helm');
    for(const continuation of ['\\'+String.fromCharCode(10),'\\'+String.fromCharCode(13,10)]) {
      const query=search.queryFromCode(root,' template ledger ./chart '+continuation+' --values "env[prod],a|b.yaml" | ignored');
      check(query,'helm template',[['--values','env[prod],a|b.yaml']],['ledger','./chart'],['-f, --values <файл>']);
      ok(!query.includes('ignored'),label+': alias code roundtrip ends at real separator');
    }
  }
  // Bracketed operand notation is metadata, not an alias delimiter. Test the
  // resulting command interpretation, including no accidental -VALUE option.
  const fixture={name:'alias-probe',aliases:[],purpose:'probe',syntax:'probe',flags:[
    {flag:'--map <KEY,-VALUE>, -m',action:'map',when:'probe'},
    {flag:'-F, --field [<LEFT,RIGHT>]',action:'field',when:'probe'},
    {flag:'--limit <[MIN / MAX]>, -l',action:'limit',when:'probe'},
  ]};
  const result=resultFor(search,[fixture],'alias-probe -m "key,-value [x]" --field "left,right" -l "1 / 2"','alias-probe',label+': bracketed metadata');
  equal(result.analysis.unmatched.length,0,label+': bracketed metadata aliases known');
  equal(result.analysis.options.length,3,label+': no phantom option from operand notation');
  equal(result.analysis.options[0].value,'key,-value [x]',label+': comma and brackets in actual value preserved');
  equal(result.analysis.options[1].value,'left,right',label+': shared bracketed operand arity');
  equal(result.analysis.options[2].value,'1 / 2',label+': slash within metadata operand does not split aliases');
  equal(JSON.stringify(result.analysis.matchedIndices),JSON.stringify([0,1,2]),label+': correct three help records');
  const slash=search.flagForms('-l [NUMBER] / -L');
  equal(slash.find(f=>f.name==='-l').expectsValue,true,label+': existing optional list operand retained');
  equal(slash.find(f=>f.name==='-L').expectsValue,false,label+': slash-separated action does not inherit operand');
}
function parserRegressions(search, commands, label) {
  const lf='\\' + String.fromCharCode(10), crlf='\\' + String.fromCharCode(13,10);
  const docker=commands.find(c=>c.name==='docker');
  ok(docker,label+': Docker root card exists');
  for (const query of [
    'docker --context study '+lf+' compose up -d',
    'docker --context '+lf+' study compose up -d',
    'docker --context study compose '+crlf+' -f compose.yaml '+crlf+' up -d',
    'docker -D -cstudy compose -fcompose.yaml up -d',
    'docker -H unix:///var/run/docker.sock compose --file="a b.yaml" up --detach',
    'docker --context "-study" compose up -d',
  ]) {
    const result=resultFor(search,commands,query,'docker compose up',label+': prefix and continuation');
    equal(result.analysis.unmatched.length,0,label+': known prefix/local flags recognised');
    ok(!result.analysis.words.some(word=>/[\r\n]/.test(word)),label+': no artificial continuation operand');
  }
  const scoped=resultFor(search,commands,'docker --context study compose -f compose.yaml logs -f echo','docker compose logs',label+': scopes');
  const f=scoped.analysis.options.filter(o=>o.name==='-f');
  equal(f.length,2,label+': both scoped -f occurrences retained');
  equal(f[0].value,'compose.yaml',label+': parent -f has filename');
  equal(f[1].hasValue,false,label+': local -f is boolean follow');
  equal(JSON.stringify(scoped.analysis.words),JSON.stringify(['echo']),label+': service operand not eaten');
  const selected=scoped.analysis.matchedIndices.map(i=>scoped.command.flags[i].flag);
  ok(selected.some(f=>f.includes('--file')),label+': parent file help selected');
  ok(selected.some(f=>f.includes('--follow')),label+': local follow help selected');
  const late=resultFor(search,commands,'docker compose logs --file compose.yaml -f echo','docker compose logs',label+': parent is prefix-only');
  ok(late.analysis.unmatched.some(o=>o.name==='--file'),label+': late Compose file option is rejected like real CLI');
  const lateRoot=resultFor(search,commands,'docker run --context study IMAGE','docker run',label+': Docker root is prefix-only');
  ok(lateRoot.analysis.unmatched.some(o=>o.name==='--context'),label+': client context after run is not falsely inherited');
  for(const [query,name,words,option]of[
    ['docker --context study run --rm IMAGE sh -ceu "echo ok"','docker run',['IMAGE','sh','-ceu','echo ok'],'--rm'],
    ['docker run IMAGE --version','docker run',['IMAGE','--version'],null],
    ['docker create --name C IMAGE --context application','docker create',['IMAGE','--context','application'],'--name'],
    ['docker exec --user 10001:10001 C /echo --context application','docker exec',['C','/echo','--context','application'],'--user'],
    ['docker run -- IMAGE --rm','docker run',['IMAGE','--rm'],null],
  ]) {
    const result=resultFor(search,commands,query,name,label+': target argv boundary');
    equal(JSON.stringify(result.analysis.words),JSON.stringify(words),label+': target argv preserved');
    equal(result.analysis.unmatched.length,0,label+': target argv is not unknown Docker flags');
    if(option)ok(result.analysis.options.some(o=>o.name===option),label+': Docker option before operand retained');
    if(!option)equal(result.analysis.options.length,0,label+': only target options remain in argv');
  }
  const unit=resultFor(search,commands,'python3 -B -m unittest -v','python3 -m unittest',label+': fixed selector');
  ok(unit.analysis.options.some(o=>o.name==='-B'),label+': interpreter option before module retained');
  ok(unit.analysis.options.some(o=>o.name==='-v'),label+': module local option retained');
  const misplaced=resultFor(search,commands,'python3 -m unittest -B','python3 -m unittest',label+': interpreter flags stay prefix-only');
  ok(misplaced.analysis.unmatched.some(o=>o.name==='-B'),label+': post-module interpreter flag not falsely inherited');
  resultFor(search,commands,'python3 -m -B unittest','python3',label+': no option inserted into fixed selector operand');
  const collisions=resultFor(search,commands,'docker -c study run -c 512 -v study-data:/data IMAGE','docker run',label+': root/local short collisions');
  equal(collisions.analysis.options.filter(o=>o.name==='-c')[0].value,'study',label+': root c means context');
  equal(collisions.analysis.options.filter(o=>o.name==='-c')[1].value,'512',label+': local c means CPU shares');
  const meaning=collisions.analysis.matchedIndices.map(i=>collisions.command.flags[i].flag);
  ok(meaning.some(f=>f.includes('--cpu-shares')),label+': CPU help selected');
  ok(meaning.some(f=>f.includes('--volume')),label+': local v means volume');
  ok(!meaning.some(f=>f.includes('--version')),label+': volume is not client version');
  const literal='a'+lf+'b', literalCR='a'+crlf+'b';
  equal(JSON.stringify(search.tokenizeQuery("docker --context '"+literal+"' compose up")),JSON.stringify(['docker','--context',literal,'compose','up']),label+': single quotes retain literal LF');
  equal(JSON.stringify(search.tokenizeQuery("docker --context '"+literalCR+"' compose up")),JSON.stringify(['docker','--context',literalCR,'compose','up']),label+': single quotes retain literal CRLF');
  equal(JSON.stringify(search.tokenizeQuery('docker --context "a'+lf+'b" compose up')),JSON.stringify(['docker','--context','ab','compose','up']),label+': double quotes join continuation');
  equal(JSON.stringify(search.tokenizeQuery('docker com'+lf+'pose up')),JSON.stringify(['docker','compose','up']),label+': adjacent word fragments join');
  const coded=search.queryFromCode(docker,' --context study '+lf+' compose -f "a|b.yaml" up -d | tee ignored');
  const codeResult=resultFor(search,commands,coded,'docker compose up',label+': complete code invocation');
  equal(codeResult.analysis.options.find(o=>o.name==='-f')?.value,'a|b.yaml',label+': quoted pipe retained');
  ok(!coded.includes('ignored'),label+': actual outer pipeline excluded');
  for(const continuation of [lf,crlf]) {
    const raw=search.queryFromCode(docker,' --context "stu'+continuation+'dy" '+continuation+' compose -f "a|b.yaml" '+continuation+' up -d | ignored');
    const result=resultFor(search,commands,raw,'docker compose up',label+': raw LF/CRLF scanner round trip');
    equal(result.analysis.options.find(o=>o.name==='--context')?.value,'study',label+': quoted continuation preserved through scanner');
    equal(result.analysis.options.find(o=>o.name==='-f')?.value,'a|b.yaml',label+': scanner keeps quoted pipe with continuation');
    ok(!raw.includes('ignored'),label+': scanner reaches real separator after CRLF');
  }
  const longCode=search.queryFromCode(docker,' --context study compose -f "'+ 'a'.repeat(300)+'.yaml" up -d; ignored');
  resultFor(search,commands,longCode,'docker compose up',label+': command longer than old 240-char limit');
  equal(search.queryForCommand(codeResult.command,coded),coded,label+': explicit invocation is not reduced to flags');
  resultFor(search,commands,'docker --unknown-prefix value compose up -d','docker',label+': unknown flag is not skipped');
  resultFor(search,commands,'docker compose -- up -d','docker compose',label+': terminator blocks subcommand scan');
  // A synthetic family proves ownership is data-driven, including aliases and
  // repeated local qualifiers, rather than a special case for Compose's -f.
  const flags=[{flag:'-f / --follow'},{flag:'-s alpha'},{flag:'-s beta'},
               {flag:'-c NAME / --context NAME'},{flag:'-f FILE / --file FILE'}].map(f=>({...f,action:'test',when:'test'}));
  const family={name:'tool group show',aliases:['t g s'],purpose:'test',syntax:'test',flags,
    flagScopes:['tool group show','tool group show','tool group show','tool','tool group'],
    prefixFlags:{tool:['-c NAME / --context NAME'],'tool group':['-c NAME / --context NAME','-f FILE / --file FILE']}};
  const fixtures=[{...family,name:'tool',aliases:[],flags:[],flagScopes:[],prefixFlags:{}},family];
  const alias=resultFor(search,fixtures,'t -c lab g -f before s -f -s beta operand','tool group show',label+': synthetic scoped alias');
  equal(alias.analysis.options.filter(o=>o.name==='-f')[0].value,'before',label+': alias parent operand');
  equal(alias.analysis.options.filter(o=>o.name==='-f')[1].hasValue,false,label+': alias local boolean');
  ok(alias.analysis.matchedIndices.includes(2)&&!alias.analysis.matchedIndices.includes(1),label+': same-scope qualifiers remain distinct');
  equal(JSON.stringify(alias.analysis.words),JSON.stringify(['operand']),label+': alias operands preserved');
  const strict=resultFor(search,fixtures,'tool group show --context lab','tool group show',label+': default strict scope');
  ok(strict.analysis.unmatched.some(o=>o.name==='--context'),label+': undeclared persistence not inferred');
  const persistent={...family,persistentScopes:['tool','tool group']};
  const inherited=resultFor(search,[persistent],'tool group --context lab show --file after -f operand','tool group show',label+': explicitly persistent family');
  equal(inherited.analysis.options.find(o=>o.name==='--context')?.value,'lab',label+': declared root persistence before child');
  equal(inherited.analysis.options.find(o=>o.name==='--file')?.value,'after',label+': unshadowed long persistent spelling after child');
  equal(inherited.analysis.options.find(o=>o.name==='-f')?.hasValue,false,label+': local short spelling shadows persistent parent');
  commaAliasRegressions(search,commands,label);

}
if(process.argv.includes('--source-only')) {
  const generated=JSON.parse(cp.execFileSync('python3',['-c',`
import sys,json
from pathlib import Path
sys.dont_write_bytecode=True
import scripts.build_volume as b
page=b.reader_commands(Path("cache/sources/reader-shell.html").read_text())
commands=b.command_catalog()
# Frozen source cards may await publication. Load through the real catalog in
# memory only, without registering files or changing native UI guards.
b.CONFIGS=dict(b.CONFIGS)
b.TARGETS=dict(b.TARGETS)
for slug in ("helm","kubernetes"):
    source=Path(slug)/"volume_config.py"
    if source.is_file():
        cfg=b.module(source).CONFIG
        b.CONFIGS[slug]=cfg
        b.TARGETS.update({i:slug for _,ids in cfg["sections"] for i in ids if i not in {"00-route","99-glossary"}})
print(json.dumps(dict(page=page,commands=commands,aliasCommands=b.command_catalog())))
  `],{cwd:root,encoding:'utf8',maxBuffer:20*1024*1024}));
  const search=shippedSearch(generated.page,'production-transform');
  parserRegressions(search,generated.commands,'source production parser');
  commaAliasRegressions(search,generated.aliasCommands,'real pending source cards');
  // Exercise every actual source card and inherited form before a full site
  // build. Prefix-owned flags must be queried at their declared position.
  for(const command of generated.commands) {
    resultFor(search,generated.commands,command.name,command.name,'source catalog');
    for(const alias of command.aliases||[])resultFor(search,generated.commands,alias,command.name,'source catalog alias');
    for(const [index,flag]of command.flags.entries())for(const form of search.flagForms(flag.flag)) {
      const value=form.qualifier||'bookvalue';
      const result=resultFor(search,generated.commands,queryForFlag(command,index,form,value),command.name,'source catalog flag');
      ok(result.analysis.matchedIndices.includes(index),'source: reachable scoped flag '+command.name+' '+flag.flag);
    }
  }
  for(const [query,name,option,value]of[
    ['go build -o ./out/app -gcflags "example.org/lab=-N -l" -trimpath .','go build','-gcflags','example.org/lab=-N -l'],
    ['go tool compile -N=false -% -+ -o file.a file.go','go tool compile','-N','false'],
    ["go test -run '^(TestOne|TestTwo)$' -count=1 ./...",'go test','-run','^(TestOne|TestTwo)$'],
    ['grep -nE error access.log','grep','-E',undefined],
    ['git reset --soft HEAD~1','git reset','--soft',undefined],
  ])optionResult(search,generated.commands,query,name,option,value,'source compatibility');

  console.log(JSON.stringify({ok:true,assertions,sourceOnly:true,implementation:'actual reader_commands transform'}));
  process.exit(0);
}

const observed = [];
for (const slug of selectedVolumes) {
  const pagePath = path.join(readerRoot, slug, 'index.html');
  ok(fs.existsSync(pagePath), slug + ': build index.html before running the reader check');
  const page = fs.readFileSync(pagePath, 'utf8');
  ok(page.includes('data-volume="' + slug + '"'), slug + ': reader volume is independent');
  ok(page.includes('data-storage-key="' + slug + '-book-v1"'), slug + ': notes/read state storage key');
  const search = shippedSearch(page, slug);
  const commands = jsonData(page, 'command-reference-data');
  ok(Array.isArray(commands) && commands.length > 30, slug + ': substantial shipped command catalog');
  const disk = JSON.parse(fs.readFileSync(path.join(readerRoot, slug, 'commands.json'), 'utf8'));
  equal(JSON.stringify(commands), JSON.stringify(disk), slug + ': embedded and text/JSON export use same catalog');
  parserRegressions(search,commands,slug);
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
        const query = queryForFlag(command,index,form,value);
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
