'use strict';const assert=require('assert'),M=require('../labs/devices/boundaries_engine.js');let checks=0;
function ok(s,a){const r=M.step(s,a);assert(r.ok,a+':'+r.error);checks++;return r.state;}function no(s,a){const old=JSON.stringify(s),r=M.step(s,a);assert(!r.ok);assert.strictEqual(r.state,s);assert.equal(JSON.stringify(s),old);checks++;return r.error;}
let s=M.initial();for(const a of ['get-map','allocate','exit','kernel'])no(s,a);for(const a of ['init-memory','discover','load-image','get-map'])s=ok(s,a);assert.equal(s.boot.captured,5);s=ok(s,'allocate');assert.equal(s.boot.mapKey,6);{const old=JSON.stringify(s),r=M.step(s,'exit');assert(!r.ok&&r.changed&&r.error.includes('EFI_INVALID_PARAMETER'));assert.equal(JSON.stringify(s),old);s=r.state;assert(s.boot.restricted);no(s,'boot-service');checks++;}s=ok(s,'get-map');s=ok(s,'exit');assert.equal(s.boot.owner,'loader');assert.equal(s.boot.services,false);no(s,'boot-service');no(s,'get-map');s=ok(s,'kernel');assert.equal(s.boot.owner,'kernel');
for(let i=0;i<3;i++)s=ok(s,'translate');assert.equal(s.virt.result,0x5200);assert(s.virt.trace[0].includes('18004'));assert(s.virt.trace[1].includes('19008'));assert(s.virt.trace[2].includes('5200'));no(s,'translate');no(s,'deny-data-write');checks++;
let denied=M.initial();denied=ok(denied,'deny-data-write');denied=ok(denied,'translate');denied=ok(denied,'translate');assert(no(denied,'translate').includes('write denied'));assert.equal(denied.virt.cursor,2);assert.equal(denied.virt.result,null);checks++;
let root=M.initial();root=ok(root,'remove-root');assert(no(root,'translate').includes('missing G-stage'));assert.equal(root.virt.cursor,0);checks++;
assert.deepStrictEqual(M.importState(M.exportState(s)),s);checks++;
for(const mutate of [x=>x.version=2,x=>x.boot.owner='loader',x=>x.virt.result=0x2200,x=>x.virt.mappings[0].hpa=1,x=>x.boot.trace=[{}]]){const bad=M.initial();mutate(bad);assert.throws(()=>M.importState(JSON.stringify(bad)));checks++;}
for(const alter of [x=>x.virt.mappings[2].hpa=0x6000,x=>x.virt.mappings[1].gpa=0x8000,x=>x.virt.mappings[0].gpa=0xA000]){const bad=M.initial();alter(bad);assert.throws(()=>M.importState(JSON.stringify(bad)));checks++;}
// A completed prefix cannot claim an access denied by its imported mapping.
for(const [cursor,gpa,permission] of [[1,0x8000,'present'],[1,0x8000,'read'],[2,0x8000,'present'],[2,0x9000,'present'],[2,0x9000,'read'],[3,0x8000,'present'],[3,0x8000,'read'],[3,0x9000,'present'],[3,0x9000,'read'],[3,0x2000,'present'],[3,0x2000,'write']]){
 let valid=M.initial();for(let i=0;i<cursor;i++){const r=M.step(valid,'translate');assert(r.ok);valid=r.state;}
 const before=M.exportState(valid),bad=JSON.parse(before);bad.virt.mappings.find(m=>m.gpa===gpa)[permission]=false;
 assert.throws(()=>M.importState(JSON.stringify(bad)),/Пройденный VM-шаг/);assert.equal(M.exportState(valid),before);checks++;
}
// A permission for a future access may be denied; its own step must fault.
for(const [cursor,gpa,permission] of [[0,0x8000,'present'],[1,0x9000,'read'],[2,0x2000,'write']]){
 let prepared=M.initial();for(let i=0;i<cursor;i++)prepared=M.step(prepared,'translate').state;
 prepared.virt.mappings.find(m=>m.gpa===gpa)[permission]=false;
 const restored=M.importState(JSON.stringify(prepared)),before=M.exportState(restored),r=M.step(restored,'translate');assert(!r.ok);assert.strictEqual(r.state,restored);assert.equal(M.exportState(restored),before);checks++;
}
console.log(JSON.stringify({kind:'pure M32-BOUND1, no UEFI/VM native test',checks,bootStaleMapKey:'reject',virtualPath:['GPA8004→HPA18004','GPA9008→HPA19008','GPA2200→HPA5200']}));
