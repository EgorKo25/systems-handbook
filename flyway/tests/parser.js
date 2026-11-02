// Uses the production parser verbatim. No shell or CLI execution.
const fs=require('fs'),path=require('path'),vm=require('vm'),cp=require('child_process'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const raw=JSON.parse(cp.execFileSync('python3',['-B','-c',
  'import importlib.util,json; s=importlib.util.spec_from_file_location("r",'+JSON.stringify(path.join(root,'sources/reference.py'))+'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(json.dumps(m.COMMANDS))'],{encoding:'utf8'}));
// Same parent/persistence contract as build_volume.command_catalog for this
// isolated source set. The parser itself is read only from production source.
const own=new Map(raw.map(c=>[c.name,c.flags.map(f=>({...f}))]));
for(const c of raw){
  c.flags=own.get(c.name).map(f=>({...f}));c.flagScopes=c.flags.map(()=>c.name);
  const parts=c.name.split(' '),parents=[];c.prefixFlags={};
  for(let n=1;n<parts.length;n++){
    const name=parts.slice(0,n).join(' '),p=raw.find(x=>x.name===name);
    if(!p)continue;
    c.prefixFlags[name]=(own.get(name)||[]).map(f=>f.flag);
    if(p.persistentOptions)parents.push(name);
    for(const f of own.get(name)||[]){c.flags.push({...f});c.flagScopes.push(name);}
  }
  if(parents.length)c.persistentScopes=parents;
}
const parserPath=process.env.HANDBOOK_COMMAND_PARSER || path.join(root,'../scripts/command_reference_parser.js');
const context={normalizeText:value=>String(value).toLowerCase(),};vm.createContext(context);
vm.runInContext(fs.readFileSync(parserPath,'utf8')+'\nthis.search=searchCommands;this.forms=flagForms;this.analyze=analyzeQuery;',context);
const cases=[];
function test(query,name,labels=[]){
 const found=context.search(raw,query);assert(found.length,query);assert.equal(found[0].command.name,name,query);
 const item=found[0];assert.equal(item.analysis.unmatched.length,0,query);
 const selected=item.analysis.matchedIndices.map(i=>item.command.flags[i].flag);
 for(const label of labels)assert(selected.includes(label),query+' missing '+label);
 cases.push({query,command:name,matched:selected});
}
test('flyway -configFiles="/home/me/lab copy/flyway.conf" migrate -target=2','flyway migrate',['-configFiles=ФАЙЛЫ','-target=ВЕРСИЯ']);
test('flyway migrate -target=2 -outputType=json','flyway migrate',['-target=ВЕРСИЯ','-outputType=ФОРМАТ']);
test('flyway -outputType=json info -target=2','flyway info',['-target=ВЕРСИЯ','-outputType=ФОРМАТ']);
test('flyway baseline -baselineVersion=1 "-baselineDescription=Принятая схема ноября"','flyway baseline',['-baselineVersion=ВЕРСИЯ','-baselineDescription=ТЕКСТ']);
test('flyway --version','flyway version');test('flyway -v','flyway version');test('flyway version','flyway version');
test('flyway --help','flyway help');test('flyway -h','flyway help');test('flyway -?','flyway help');
test('flyway validate -ignoreMigrationPatterns=*:pending','flyway validate',['-ignoreMigrationPatterns=ШАБЛОНЫ']);
test('flyway repair','flyway repair');test('flyway clean','flyway clean');
test('flyway migrate -postgresql.transactional.lock=false','flyway migrate',['-postgresql.transactional.lock=ЗНАЧЕНИЕ']);
test('flyway -postgresql.transactional.lock=true migrate','flyway migrate',['-postgresql.transactional.lock=ЗНАЧЕНИЕ']);
// Verify scope/boundary behavior, not a claim that Flyway accepts POSIX --.
const m=raw.find(c=>c.name==='flyway migrate');
const ended=context.analyze(m,'flyway migrate -- -target=2');assert.equal(ended.matchedIndices.length,0);
const prefixed=context.analyze(m,'echo flyway migrate -target=2');assert.equal(prefixed.explicit,false);
const dotted=context.forms('-postgresql.transactional.lock=false');
assert.equal(dotted[0].name,'-postgresql.transactional.lock');
console.log(JSON.stringify({kind:'production-parser-source',passed:true,cases:cases.length,
 alias_scope_boundary_assertions:3,dotted_parameter:'complete dotted name preserved; true/false queries select the scoped flag',details:cases},null,2));
