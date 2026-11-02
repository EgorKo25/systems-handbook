// Exercise the production parser itself. This script executes no Vault command.
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const cards=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(path.join(__dirname,'../../scripts/command_reference_parser.js'),'utf8');
const shell=fs.readFileSync(path.join(__dirname,'../../cache/sources/reader-shell.html'),'utf8');
const normalize=shell.match(/function normalizeText\(value\) \{[\s\S]*?\r?\n\}/);assert(normalize,'production normalizeText missing');
const context={};vm.createContext(context);vm.runInContext(normalize[0]+'\n'+source,context);
let checks=0;
function check(name,query,expectedFlags,unknown=0){
 const card=cards.find(c=>c.name===name);assert(card,name);
 const a=context.analyzeQuery(card,query);assert(a.explicit,query);assert.equal(a.unmatched.length,unknown,query);
 for(const flag of expectedFlags)assert(a.matchedIndices.some(i=>card.flags[i].flag===flag),query+' missing '+flag);
 checks++;
}
check('vault kv put','vault kv put -mount=secret -cas=1 handbook/config "message=with spaces"',['-mount ПУТЬ','-cas N']);
check('vault kv get','vault kv get -address https://127.0.0.1:18200 -ca-cert "/private/cert with spaces/ca.pem" -format=json -mount=secret handbook/config',['-address АДРЕС','-ca-cert ФАЙЛ','-format ФОРМАТ','-mount ПУТЬ']);
check('vault write','vault write -f -wrap-ttl=60s auth/approle/role/handbook/secret-id',['-f / -force','-wrap-ttl ДЛИТЕЛЬНОСТЬ']);
check('vault write','vault write -force auth/approle/role/handbook/secret-id',['-f / -force']);
check('vault operator raft snapshot restore','vault operator raft snapshot restore -force "/private/snapshot with spaces.snap"',['-force']);
check('vault version','vault -version',[]);
const put=cards.find(c=>c.name==='vault kv put');
let x=context.analyzeQuery(put,'vault kv put -- handbook/config -cas=99');assert.equal(x.options.length,0);checks++;
x=context.analyzeQuery(put,'vault kv put handbook/config -cas=99');assert.equal(x.options.length,0);checks++;
assert.equal(context.commandMatch(put,context.tokenizeQuery('echo vault kv put -cas=1')).prefix,0);checks++;
assert.equal(context.commandMatch(put,context.tokenizeQuery('vault -address=https://127.0.0.1:18200 kv put -cas=1')).prefix,0);checks++;
// Test every declared label's primary option shape, not every alias in native help.
let forms=0;
for(const card of cards)for(const flag of card.flags){
 const parts=flag.flag.split(/\s+\/\s+/);
 for(const part of parts){const m=part.match(/^(-[^\s]+)(?:\s+(.+))?$/);if(!m)continue;
 const q=card.name+' '+m[1]+(m[2]?' "sample value"':'');const a=context.analyzeQuery(card,q);
 assert.equal(a.unmatched.length,0,q);forms++;}
}
console.log(JSON.stringify({kind:'production parser static tests',checks,declaredForms:forms,nativeHelpAliasCoverage:'not claimed'}));
