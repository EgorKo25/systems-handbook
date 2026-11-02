'use strict';
// Actual shipped reference-query parser; no shell/CLI execution or publication.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/command-parser-scopes.json'),'utf8'));
const parser=fs.readFileSync(process.env.HANDBOOK_PARSER_SOURCE||path.join(root,'scripts/command_reference_parser.js'),'utf8');
const shell=fs.readFileSync(path.join(root,'cache/sources/reader-shell.html'),'utf8');
const normalizer=shell.match(/function normalizeText\(value\) \{[\s\S]*?\n\}/);assert.ok(normalizer);
const ctx={};vm.createContext(ctx);vm.runInContext(normalizer[0]+'\n'+parser+'\nthis.api={tokenizeQuery,flagForms,optionSpecifications,parseOptions,commandMatch,analyzeQuery,searchCommands};',ctx);
const api=ctx.api,commands=fixture.commands;let groups=0,cases=0;const names=[];
const plain=x=>JSON.parse(JSON.stringify(x));
function test(name,fn){if(process.env.HANDBOOK_PARSER_GROUP&&!name.includes(process.env.HANDBOOK_PARSER_GROUP))return;fn();names.push(name);groups++;console.log('PASS',name);}
function one(query,name){const found=api.searchCommands(commands,query);assert.equal(found.length,1,query);assert.equal(found[0].command.name,name,query);assert.equal(found[0].analysis.explicit,true,query);cases++;return found[0];}
function clean(query,name){const item=one(query,name);assert.equal(item.analysis.unmatched.length,0,query);return item;}
function selected(item,flag,scope){return item.analysis.matchedIndices.some(i=>item.command.flagScopes[i]===scope&&api.flagForms(item.command.flags[i].flag).some(f=>f.name===flag));}
test('dotted lexemes retain complete names, operands and alias arity',()=>{
 for(const [label,names,arity]of [['-postgresql.transactional.lock=false',['-postgresql.transactional.lock'],true],['-postgresql.transactional.lock BOOL',['-postgresql.transactional.lock'],true],['--cache.setting',['--cache.setting'],false],['-x, --engine.setting VALUE',['-x','--engine.setting'],true],['--engine.setting=VALUE / --other.setting VALUE',['--engine.setting','--other.setting'],true]]){const f=api.flagForms(label);assert.deepEqual(Array.from(f,x=>x.name),names);assert.ok(f.every(x=>x.expectsValue===arity));cases++;}
 // Grammar fixture only: this is not a newly declared Flyway command card.
 const c={name:'lexical-fixture',flags:[{flag:'-postgresql.transactional.lock=BOOL'}],purpose:'',syntax:''},spec=api.optionSpecifications(c);
 for(const tokens of [['-postgresql.transactional.lock=false'],['-postgresql.transactional.lock','false'],api.tokenizeQuery('-postgresql.transactional.lock="value with spaces"')]){const p=api.parseOptions(tokens,spec);assert.equal(p.options.length,1);assert.equal(p.options[0].name,'-postgresql.transactional.lock');assert.equal(p.options[0].hasValue,true);assert.equal(p.words.length,0);cases++;}
 const missing=api.parseOptions(['-postgresql.transactional.lock'],spec);assert.equal(missing.options[0].hasValue,false);assert.equal(missing.options[0].value,undefined);
 const bad=api.parseOptions(['-postgresql.transactional.locked=false'],spec);assert.equal(spec.has(bad.options[0].name),false);assert.equal(bad.options[0].name,'-postgresql.transactional.locked');
});
test('Argo final-local flags before/between/after command words select same leaf and correct shadow owner',()=>{
 const name='argocd admin settings rbac can',words=['admin','settings','rbac','can'];
 for(const [flag,value]of [['--server','http://127.0.0.1:9'],['--context','offline lab'],['--kubeconfig','path with spaces/kubeconfig']])for(let position=0;position<=words.length;position++)for(const syntax of [flag+'="'+value+'"',flag+' "'+value+'"',flag+" '"+value+"'"]){const parts=words.slice();parts.splice(position,0,syntax);const q='argocd '+parts.join(' ')+' reader get applications ledger/ledger-gitops --policy-file policy.csv';const item=clean(q,name);assert.ok(selected(item,flag,name),q);assert.ok(!selected(item,flag,'argocd'),q);assert.equal(item.analysis.options.find(x=>x.name===flag).value,value);assert.deepEqual(Array.from(item.analysis.words),['reader','get','applications','ledger/ledger-gitops']);}
 const repeated=clean('argocd --context admin admin settings rbac can --policy-file policy.csv',name);assert.equal(repeated.analysis.options.find(x=>x.name==='--context').value,'admin');
});
test('Argo inherited parent flag stays inherited; shadowed server changes meaning only on actual admin leaf',()=>{
 for(const c of commands.filter(c=>c.name.startsWith('argocd ')&&c.persistentScopes?.includes('argocd'))){const tail=c.name.slice('argocd '.length);for(const query of ['argocd --server=http://127.0.0.1:9 '+tail,c.name+' --server http://127.0.0.1:9']){const item=clean(query,c.name),hasLocal=c.flags.some((f,i)=>c.flagScopes[i]===c.name&&api.flagForms(f.flag).some(x=>x.name==='--server'));assert.ok(selected(item,'--server',hasLocal?c.name:'argocd'),query);}}
 for(const query of ['argocd --config "path with spaces/config" admin settings rbac can','argocd admin settings rbac can --config="path with spaces/config"']){const item=clean(query,'argocd admin settings rbac can');assert.ok(selected(item,'--config','argocd'));}
 const alias=clean('argocd --config isolated-config ctx','argocd context');assert.ok(selected(alias,'--config','argocd'));
});
test('unknown flags and missing values remain visible; command words are never guessed around a missing operand',()=>{
 const leaf='argocd admin settings rbac can';
 for(const q of ['argocd --not-real=1 admin settings rbac can','argocd --context admin settings rbac can','argocd --kubeconfig -- admin settings rbac can']){const item=one(q,'argocd');assert.ok(item.analysis.unmatched.length>0,q);}
 const unknown=one(leaf+' --not-real=x',leaf);assert.equal(unknown.analysis.unmatched[0].name,'--not-real');
 const missing=one(leaf+' --context',leaf);const opt=missing.analysis.options.find(x=>x.name==='--context');assert.equal(opt.hasValue,false);assert.equal(opt.value,undefined);
 // This reference tool highlights a known incomplete flag; it is not a CLI validator.
 const ended=one('argocd -- admin settings rbac can','argocd');assert.equal(ended.analysis.options.length,0);assert.ok(ended.analysis.words.includes('admin'));
 const fly=one('flyway migrate -postgresql.transactional.lock=false','flyway migrate');assert.equal(fly.analysis.unmatched[0].name,'-postgresql.transactional.lock');
});
test('strict Git and Docker scope boundaries survive; Compose global file and local follow stay distinct',()=>{
 const git=clean('git status --short --branch','git status');assert.ok(selected(git,'--short','git status'));assert.equal(api.commandMatch(git.command,['git','--unknown','x','status']).prefix,0);
 const d=clean('docker --context isolated run --rm demo','docker run');assert.ok(selected(d,'--context','docker'));
 const wrong=one('docker run --context isolated demo','docker run');assert.ok(wrong.analysis.unmatched.some(x=>x.name==='--context'));
 const compose=clean('docker compose -f isolated-compose.yaml logs -f --tail 5','docker compose logs');assert.ok(selected(compose,'-f','docker compose'));assert.ok(selected(compose,'-f','docker compose logs'));assert.equal(compose.analysis.options.filter(x=>x.name==='-f').length,2);
 const bad=one('docker --tail 5 compose logs','docker');assert.ok(bad.analysis.unmatched.some(x=>x.name==='--tail'));
});
test('psql/ip/simple flags and quoted operands preserve established parsing',()=>{
 for(const [q,name,values]of [['psql -h localhost -p 55440 -d handbook -c "select 42"','psql',[['-c','select 42'],['-p','55440']]],['ip -br address show','ip',[]],['ls -la /tmp','ls',[]],['head -n 4 file.txt','head',[['-n','4']]],['grep -n "some text" file.txt','grep',[]],['git log --oneline -p','git log',[]],['flyway -configFiles="path with spaces/flyway.conf" migrate -target=2','flyway migrate',[['-configFiles','path with spaces/flyway.conf'],['-target','2']]]]){const item=clean(q,name);for(const [flag,value]of values)assert.ok(item.analysis.options.some(x=>x.name===flag&&x.value===value),q+' '+flag);}
 const py=clean('python3 -B -m unittest -v','python3 -m unittest');assert.equal(py.analysis.interfaceMode,'module');
 const stdin=one('python3 -c "print(42)" -m unittest','python3');assert.equal(stdin.analysis.interfaceMode,'command');
});
test('Argo ancestor arity agrees with all9 pinned native version/help dispatch discriminators',()=>{
 const observation=fixture.nativeArgoDispatch;assert.equal(observation.version,'3.5.6+c2b1e30');assert.equal(observation.binarySHA256,'db9d17b70593d3f86a4dcf08d9ebbb85a42e995426ac5f928b737260656102d3');assert.equal(observation.cases.length,9);
 for(const row of observation.cases){const q='argocd '+row.argv.join(' '),item=one(q,row.referenceCard);assert.ok([0,1].includes(row.nativeExit));
  if(row.referenceFlagMatched){assert.ok(selected(item,row.flag,row.referenceCard),q);}
  else{assert.equal(row.nativeExit,1);assert.ok(item.analysis.unmatched.some(x=>x.name===row.flag),q);assert.ok(!item.analysis.matchedIndices.some(i=>api.flagForms(item.command.flags[i].flag).some(f=>f.name===row.flag)),q);}
 }
 // The --help suffix in some native rows prevents a policy action; this test
 // compares command dispatch/flag owner, not completeness of the help card.
});
test('Argo dispatch keeps known ancestor booleans, string operands and strict nonArgo boundaries',()=>{
 const leaf='argocd admin settings rbac can',words=['admin','settings','rbac','can'];
 for(let position=0;position<=words.length;position++){const parts=words.slice();parts.splice(position,0,'--grpc-web');const item=clean('argocd '+parts.join(' '),leaf);assert.ok(selected(item,'--grpc-web','argocd'));}
 for(const flag of ['--context','--kubeconfig','--server'])for(const value of ['', '-dash']){const item=clean('argocd '+flag+'='+JSON.stringify(value)+' '+words.join(' '),leaf);assert.equal(item.analysis.options[0].value,value);assert.ok(selected(item,flag,leaf));}
 const retained=clean('argocd --client ignored version','argocd version');assert.deepEqual(Array.from(retained.analysis.words),['ignored']);assert.equal(retained.analysis.options[0].hasValue,false);
 // A known flag/selected card still does not validate positional arguments.
 for(const q of ['argocd --client','argocd --quiet admin settings rbac can','argocd --context -- admin settings rbac can']){const item=one(q,'argocd');assert.ok(item.analysis.unmatched.length>0);}
 const after=one(leaf+' --context',leaf);assert.equal(after.analysis.options[0].hasValue,false);
 const original=commands.find(c=>c.name===leaf);
 for(const executable of ['vault','custom']){const clone=plain(original);clone.name=clone.name.replace(/^argocd/,executable);clone.flagScopes=clone.flagScopes.map(s=>s.replace(/^argocd/,executable));clone.prefixFlags=Object.fromEntries(Object.entries(clone.prefixFlags).map(([k,v])=>[k.replace(/^argocd/,executable),v]));clone.persistentScopes=[executable];assert.equal(api.commandMatch(clone,api.tokenizeQuery(executable+' --context value admin settings rbac can')).prefix,0);cases++;}
 const noPersistence=plain(original);delete noPersistence.persistentScopes;assert.equal(api.commandMatch(noPersistence,api.tokenizeQuery('argocd --context value admin settings rbac can')).prefix,0);cases++;
});
assert.ok(groups>0,'group filter matched no tests');console.log(JSON.stringify({status:'PASS',groups,cases,tests:names,scope:'Actual shipped JS reference parser and projected real scoped cards; no CLI, shell, server or publication'}));
