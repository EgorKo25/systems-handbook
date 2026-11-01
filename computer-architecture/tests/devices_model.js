// Pure model tests. No real device, timing, firmware or operating-system claim.
'use strict';const assert=require('assert'),M=require('../labs/devices/engine.js');let checks=0;
function ok(s,a,arg){const r=M.step(s,a,arg);assert(r.ok,a+': '+r.error);checks++;return r.state;}
function denied(s,a,arg){const before=JSON.stringify(s),r=M.step(s,a,arg);assert(!r.ok,a+' unexpectedly accepted');assert.strictEqual(r.state,s);assert.equal(JSON.stringify(s),before,'failed action mutated input');checks++;return r.error;}
let s=M.initial();assert.equal(s.media.length,512);assert.equal(s.media[0],42);assert(s.media.slice(1).every(x=>x===0));assert(s.ram.slice(0x2000,0x2400).every(x=>x===0));assert.deepStrictEqual(s.ram.slice(0x1000,0x1014),[0xB7,0x22,0,0,0x03,0xA3,0x02,0,0x13,0x03,0x13,0,0x23,0xA0,0x62,0x20,0x73,0,0x10,0]);checks++;
for(const a of ['publish','dma-read','complete-read','deliver-irq','observe','ack','cpu-result','prepare-output','prepare-write','accept-write','complete-write','flush','complete-flush','unknown'])denied(s,a);
s=ok(s,'prepare-read');s=ok(s,'publish');denied(s,'edit-address',0x2200);s=ok(s,'dma-read');assert.equal(s.ram[0x2000],42);assert.equal(s.irq.pending,false);denied(s,'observe');s=ok(s,'complete-read');s=ok(s,'mask');denied(s,'deliver-irq');s=ok(s,'observe');assert.equal(s.readObserved,true);s=ok(s,'unmask');s=ok(s,'deliver-irq');assert.equal(s.cpu.savedPC,0x1000);assert.equal(s.cpu.pc,0x1800);assert.equal(s.cpu.mode,'handler');denied(s,'cpu-result');s=ok(s,'ack');assert.equal(s.cpu.pc,0x1000);s=ok(s,'cpu-result');assert.equal(s.cpu.pc,0x1010);assert(s.cpu.trap);assert.deepStrictEqual(s.ram.slice(0x2200,0x2204),[43,0,0,0]);assert(s.ram.slice(0x2204,0x2400).every(x=>x===0));checks++;
s=ok(s,'prepare-write');denied(s,'publish');s=ok(s,'prepare-output');s=ok(s,'publish');s=ok(s,'accept-write');assert.equal(s.cache[0],43);assert.equal(s.media[0],42);s=ok(s,'complete-write');assert.equal(s.flushed,false);let lost=ok(s,'power-loss');assert.equal(lost.cache,null);assert.equal(lost.media[0],42);checks++;
s=ok(s,'flush');let pendingLost=ok(s,'power-loss');assert.equal(pendingLost.media[0],42);s=ok(s,'complete-flush');assert.equal(s.media[0],43);assert.equal(s.cache,null);s=ok(s,'power-loss');assert.equal(s.media[0],43);assert.equal(s.powerLosses,1);checks++;
const exported=M.exportState(s);assert.deepStrictEqual(M.importState(exported),s);checks++;
for(const mutate of [x=>x.version=999,x=>x.ram[0]=-1,x=>x.media.pop(),x=>x.cpu.pc=1.5,x=>x.irq.vector=3,x=>x.iommu.mappings[0].pa=65535,x=>x.published=true]){const bad=JSON.parse(exported);mutate(bad);assert.throws(()=>M.importState(JSON.stringify(bad)));checks++;}
function readProfile(){let t=M.initial();t=ok(t,'set-iommu',true);t=ok(t,'prepare-read');assert.equal(t.descriptor.address,0x4000);return t;}
let t=readProfile();t=ok(t,'publish');t=ok(t,'dma-read');assert.equal(t.ram[0x2000],42);checks++;
let bad=readProfile();bad=ok(bad,'edit-address',0x00402000);bad=ok(bad,'publish');assert(denied(bad,'dma-read').includes('IOMMU fault'));
bad=readProfile();bad.iommu.mappings[0].write=false;bad=ok(bad,'publish');assert(denied(bad,'dma-read').includes('направление'));
bad=readProfile();bad.descriptor.device=2;bad=ok(bad,'publish');denied(bad,'dma-read');
bad=readProfile();bad.iommu.mappings[0].length=511;bad=ok(bad,'publish');denied(bad,'dma-read');
bad=M.initial();bad=ok(bad,'prepare-read');bad=ok(bad,'edit-address',0xFFFF);bad=ok(bad,'publish');assert(denied(bad,'dma-read').includes('PA'));
// Additional explicit pattern tests all 508 preserved bytes, not only zero defaults.
t=M.initial();for(let i=4;i<512;i++)t.media[i]=(i*13)&255;
for(const a of ['prepare-read','publish','dma-read','complete-read','observe','cpu-result'])t=ok(t,a);
assert(t.ram.slice(0x2204,0x2400).every(x=>x===0));t=ok(t,'prepare-output');assert.deepStrictEqual(t.ram.slice(0x2204,0x2400),t.media.slice(4));
for(const a of ['prepare-write','publish','accept-write','complete-write','flush','complete-flush'])t=ok(t,a);assert.deepStrictEqual(t.media.slice(4),t.ram.slice(0x2004,0x2200));checks++;
// Full-width numeric range checks; JS number arithmetic must not create 32-bit wrapping mappings.
let overflow=M.initial();overflow.iommu.mappings[0].iova=0xFFFFFFFF;assert.throws(()=>M.importState(JSON.stringify(overflow)));checks++;
overflow=M.initial();overflow=ok(overflow,'set-iommu',true);overflow=ok(overflow,'prepare-read');overflow=ok(overflow,'edit-address',0xFFFFFFFF);overflow=ok(overflow,'publish');assert(denied(overflow,'dma-read').includes('32бит'));
for(const mutate of [x=>x.irq.delivered=true,x=>{x.cpu.mode='handler';x.irq.pending=true;x.irq.delivered=true;},x=>x.trace=[{}],x=>x.completion={op:'READ',status:'SUCCESS',bytes:511}]){let bad=M.initial();mutate(bad);assert.throws(()=>M.importState(JSON.stringify(bad)));checks++;}
// The compact UI must preserve every normal semantic transition, not skip DMA/completion/prepare/flush.
let normal=M.initial(),actions=[];for(let i=0;i<30;i++){const n=M.nextNormal(normal);if(!n)break;actions.push(n[0]);normal=ok(normal,n[0]);}
assert.deepStrictEqual(actions,['prepare-read','publish','dma-read','complete-read','deliver-irq','observe','ack','cpu-result','prepare-output','prepare-write','publish','accept-write','complete-write','flush','complete-flush']);checks++;
assert.equal(normal.media[0],43);assert.equal(M.nextNormal(normal),null);checks++;
let interrupted=M.initial();interrupted=ok(interrupted,'power-loss');assert.equal(M.nextNormal(interrupted),null);checks++;
let masked=M.initial();for(const a of ['prepare-read','publish','dma-read','complete-read','mask'])masked=ok(masked,a);assert.equal(M.nextNormal(masked)[0],'unmask');checks++;
console.log(JSON.stringify({kind:'pure M32-I/O1 model, no native hardware',checks,defaultBytes:'2A000000→2B000000',ramRead:'PA2000..21FF',cpuStore:'PA2200..2203',writePrepare:'explicit512B',irqIsContextSwitch:false}));
