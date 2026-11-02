'use strict';
// Real Bash card sources + production parser. No query string is executed.
// --native additionally runs only the fixed builtin argv and own startup files.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),cs=JSON.parse(fs.readFileSync(path.join(root,'bash/commands.json'),'utf8'));
const shell=fs.readFileSync(path.join(root,'cache/sources/reader-shell.html'),'utf8'),context={};
vm.createContext(context);vm.runInContext(shell.match(/function normalizeText\(value\) \{[\s\S]*?\n\}/)[0]+'\n'+fs.readFileSync(path.join(root,'scripts/command_reference_parser.js'),'utf8')+'\nthis.api={tokenizeQuery,flagForms,searchCommands,queryForCommand,parseOptions,optionSpecifications};',context);
const api=context.api,plain=x=>JSON.parse(JSON.stringify(x));let checks=0;
function test(label,fn){fn();checks++;}
function one(q,name){const x=api.searchCommands(cs,q);assert.equal(x.length,1,q);assert.equal(x[0].command.name,name,q);return x[0];}
const bash=cs.find(c=>c.name==='bash'),printf=cs.find(c=>c.name==='printf');
test('independent no-operand startup options own different explanations',()=>{
 for(const flag of ['--noprofile','--norc']){const matches=bash.flags.filter(f=>api.flagForms(f.flag).some(form=>form.name===flag));assert.equal(matches.length,1);assert.equal(matches[0].flag,flag);assert.equal(api.flagForms(matches[0].flag)[0].expectsValue,false);}
 assert.ok(bash.flags.find(f=>f.flag==='--noprofile').action.includes('/etc/profile'));
 assert.ok(bash.flags.find(f=>f.flag==='--norc').result.includes('BASH_ENV'));
});
for(const q of ['bash --noprofile','bash --norc','bash --noprofile --norc','bash --norc --noprofile','bash --noprofile --norc --login'])test('startup flags '+q,()=>{const x=one(q,'bash');assert.equal(x.analysis.unmatched.length,0);for(const o of x.analysis.options)assert.equal(o.hasValue,false);});
test('printf declares format boundary without changing global plus options',()=>{assert.equal(printf.optionBoundary,'first-operand');assert.equal(printf.optionPrefix,'-');const set=one('set +x','set');assert.ok(set.analysis.options.some(o=>o.name==='+x'));assert.equal(set.analysis.unmatched.length,0);});
const good=[
 ["printf '%s\\n' '-u'",[],['%s\\n','-u']],
 ["printf '%s|%s\\n' '--' '-v'",[],['%s|%s\\n','--','-v']],
 ["printf '-'",[],['-']],
 ["printf -- '-%s\\n' x",[],['-%s\\n','x']],
 ["printf -- '--'",[],['--']],
 ["printf -- -v lesson_result",[],['-v','lesson_result']],
 ["printf '+%s\\n' '-u'",[],['+%s\\n','-u']],
 ["printf '' '-u'",[],['','-u']],
 ["printf -v lesson_result '%s\\n' '-u'",[['-v','lesson_result']],['%s\\n','-u']],
 ["printf -vlesson_result '%s' '-u'",[['-v','lesson_result']],['%s','-u']],
 ["printf -v lesson_result -- '-%s' x",[['-v','lesson_result']],['-%s','x']],
 ["printf '%s' '-v' lesson_result",[],['%s','-v','lesson_result']],
 ["printf -- '%s' '--' '-u'",[],['%s','--','-u']],
 ["printf '+x' '-v' lesson_result",[],['+x','-v','lesson_result']],
 ["printf -- '-v' '-u'",[],['-v','-u']],
 ["printf -v lesson_result '' '-u'",[['-v','lesson_result']],['','-u']],
 ["printf -v lesson_result '+%s' '-v'",[['-v','lesson_result']],['+%s','-v']]
];
for(const [q,options,words]of good)test('format stops options '+q,()=>{const x=one(q,'printf');assert.equal(x.analysis.unmatched.length,0);assert.deepEqual(plain(x.analysis.words),words);assert.deepEqual(plain(x.analysis.options.map(o=>[o.name,o.value])),options);assert.equal(api.queryForCommand(printf,q),q);});
for(const q of ['printf -u "%s" x','printf "-%s" x'])test('dash option before format remains unknown '+q,()=>{const x=one(q,'printf');assert.ok(x.analysis.unmatched.length>0);});
test('missing -v operand remains exposed',()=>{const x=one('printf -v','printf');assert.equal(x.analysis.options[0].hasValue,false);});
test('bare end-of-options is not a fictitious format',()=>{const x=one('printf --','printf');assert.deepEqual(plain(x.analysis.options),[]);assert.deepEqual(plain(x.analysis.words),[]);});
// Deliberately do not validate printf's formatting language, variable identifiers,
// operand counts, or every error status. A recognized option isn't CLI success.
let native=0;
if(process.argv.includes('--native')){
 const cp=require('node:child_process'),os=require('node:os'),binary=process.env.HANDBOOK_BASH||'/bin/bash';
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'bash-reference-boundaries-'));
 const env=Object.fromEntries(['HOME','USER','LOGNAME'].filter(k=>process.env[k]!==undefined).map(k=>[k,process.env[k]]));
 Object.assign(env,{PATH:'/usr/bin:/bin',LC_ALL:'C',HISTFILE:'/dev/null',PS1:'',TERM:'dumb'});
 const run=args=>{const r=cp.spawnSync(binary,args,{cwd:temp,env,encoding:'utf8',timeout:10000,stdio:['ignore','pipe','pipe']});assert.ifError(r.error);native++;return r;};
 try{
  const version=run(['--version']);assert.equal(version.status,0);assert.ok(version.stdout.startsWith('GNU bash, version '));
  const helper='unset lesson_result; builtin printf "$@"; lesson_status=$?; if [[ -v lesson_result ]]; then builtin printf "<assigned:%s>" "$lesson_result"; fi; exit "$lesson_status"';
  const cases=[
   [['%s\n','-u'],'-u\n',0],[['%s|%s\n','--','-v'],'--|-v\n',0],[['-'],'-',0],
   [['--','-%s\n','x'],'-x\n',0],[['--','--'],'--',0],[['--','-v','lesson_result'],'-v',0],
   [['+%s\n','-u'],'+-u\n',0],[['','-u'],'',0],
   [['-v','lesson_result','%s\n','-u'],'<assigned:-u\n>',0],
   [['-vlesson_result','%s','-u'],'<assigned:-u>',0],
   [['-v','lesson_result','--','-%s','x'],'<assigned:-x>',0],
   [['-u','%s','x'],'',2],[['-%s','x'],'',2],[['--'],'',2],[['-v'],'',2],[['-v','lesson_result'],'',2]
  ];
  for(const [args,text,status]of cases){const r=run(['--noprofile','--norc','-c',helper,'printf-native',...args]);assert.equal(r.status,status,JSON.stringify(args));assert.equal(r.stdout,text,JSON.stringify(args));}
  fs.writeFileSync(path.join(temp,'own-env.bash'),"builtin printf 'ENV\\n'\n");
  fs.writeFileSync(path.join(temp,'own-rc.bash'),"builtin printf 'RC\\n'\n");
  env.BASH_ENV=path.join(temp,'own-env.bash');
  for(const flags of [[],['--norc'],['--noprofile'],['--noprofile','--norc']]){
   const noninteractive=run([...flags,'-c',"builtin printf 'BODY\\n'"]);assert.equal(noninteractive.status,0);assert.equal(noninteractive.stdout,'ENV\nBODY\n');
   const interactive=run(['--rcfile',path.join(temp,'own-rc.bash'),...flags,'-ic',"builtin printf 'BODY\\n'"]);assert.equal(interactive.status,0);assert.equal(interactive.stdout,(flags.includes('--norc')?'':'RC\n')+'BODY\n');
  }
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
}
console.log(JSON.stringify({status:'PASS',sourceChecks:checks,nativeInvocations:native,scope:'Actual source cards and parser; optional fixed Bash builtin/startup cases, no user query execution or general CLI validation'}));
