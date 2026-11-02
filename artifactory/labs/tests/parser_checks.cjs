// Uses the exact shared production parser read-only; never executes a query.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const [parser, data]=process.argv.slice(2);
const commands=JSON.parse(fs.readFileSync(data,'utf8'));
const ctx={normalizeText:value=>String(value).toLocaleLowerCase().normalize('NFKC')};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(parser,'utf8')+'\nglobalThis.api={searchCommands,analyzeQuery,flagForms,optionSpecifications};',ctx);
const api=ctx.api, own=commands.filter(c=>c.volume==='artifactory');
let assertions=0, forms=0;
function check(condition,message){assert.ok(condition,message);assertions++;}
function find(q){return api.searchCommands(commands,q)[0];}
for(const c of own){
 for(const spelling of [c.name,...(c.aliases||[])]){
  check(find(spelling)?.command.name===c.name,`canonical/alias: ${spelling}`);
 }
 c.flags.forEach((flag,index)=>{
  for(const f of api.flagForms(flag.flag)){
   const option=f.name+(f.expectsValue?'='+JSON.stringify(f.qualifier||'value with space'):'');
   const owner=c.flagScopes?.[index];
   const prefix=owner && owner!==c.name && c.parentOptions!=='persistent';
   const query=prefix ? owner+' '+option+' '+c.name.slice(owner.length+1) : c.name+' '+option;
   const result=api.analyzeQuery(c,query);
   check(result.explicit && result.matchedIndices.includes(index),`selected form ${query}`);forms++;
  }
 });
}
let q='jf rt build-promote receipt 1 generic-releases --comment="Личный выпуск принят" --copy=true';
let r=find(q);check(r.command.name==='jf rt build-promote','specific operation');
check(r.analysis.options.some(o=>o.name==='--comment' && o.value==='Личный выпуск принят'),'quoted operand');
r=find('jf rt upload --flat=true -- --fail-no-op');
check(r.analysis.options.some(o=>o.name==='--flat'),'before delimiter');
check(!r.analysis.options.some(o=>o.name==='--fail-no-op'),'delimiter ends option parsing');
check(find('jf --server-id=lab-publisher rt ping')?.command.name!=='jf rt ping','local flag is not global');
check(find('jf rt --server-id=lab-publisher ping')?.command.name!=='jf rt ping','local flag is not namespace flag');
check(find('python3 tests/local_checks.py --go /verified/go --jf /verified/jf')?.command.name==='python3 tests/local_checks.py','script begins program argv');
check(find('python3 -c "print(1)" tests/local_checks.py --go /verified/go')?.command.name!=='python3 tests/local_checks.py','program argv cannot select another script');
check(find('python3 release_manifest.py create --toolchain "go1.27.3 linux/amd64"')?.command.name==='python3 release_manifest.py create','longest helper command');
console.log(JSON.stringify({scope:'actual shared production parser; reference queries only',commands:own.length,selected_flag_forms:forms,assertions,passed:true}));
