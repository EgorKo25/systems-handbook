'use strict';
const assert=require('node:assert/strict');
const m=require('../labs/memory-io/models.js');
let checks=0;function test(name,fn){fn();checks++;console.log('PASS',name);}
test('32bit walk calculates both table addresses and PA independently',()=>{
 const x=m.translate('0x00403124','0x12a');assert.deepEqual([x.outer,x.inner,x.offset,x.rootEntry,x.tableEntry,x.physical],[1,3,292,0x8004,0x900c,0x12a124]);
 assert.equal(x.physical,298*4096+292);
});
test('page end spans two translations; invalid overflow is rejected',()=>{assert.deepEqual(m.range(0x403ffe,4),{first:0x403,last:0x404,pages:2,crosses:true});assert.equal(m.range(0x403ffc,4).pages,1);assert.throws(()=>m.range(0xffffffff,2));assert.throws(()=>m.range(0,0));});
test('invalid addresses, frames and table alignment never silently wrap',()=>{for(const x of [-1,2**32,NaN,'0xno','3.5'])assert.throws(()=>m.translate(x,1));assert.throws(()=>m.translate(1,2**20));assert.throws(()=>m.translate(1,1,0x8001));});
test('four-byte little-endian codec handles boundaries and malformed data',()=>{assert.deepEqual(m.encode(42),[42,0,0,0]);assert.equal(m.decode([0x78,0x56,0x34,0x12]),0x12345678);assert.equal(m.decode(m.encode(0xffffffff)),0xffffffff);assert.throws(()=>m.decode([1,2,3]));assert.throws(()=>m.encode(2**32));assert.throws(()=>m.decode([0,0,0,256]));});
test('COW sharing before write and independent pages after write',()=>{const c=new m.Cow();c.fork();assert.equal(c.state().owners.P.frame,c.state().owners.Q.frame);c.write('P',43);assert.equal(c.state().owners.P.value,43);assert.equal(c.state().owners.Q.value,42);assert.equal(c.state().copiedBytes,4096);assert.notEqual(c.state().owners.P.frame,c.state().owners.Q.frame);c.write('Q',44);assert.equal(c.state().copies,1);assert.equal(c.state().owners.P.value,43);assert.throws(()=>c.fork());assert.throws(()=>c.write('unknown',0));});
test('ordinary writable COW-owner store has no fake fault; copied value follows current bytes',()=>{const c=new m.Cow();c.write('P',43);assert.equal(c.state().copies,0);assert.doesNotMatch(c.state().lastTrace.join(' '),/fault|повтор|TLB/i);assert.equal(c.state().owners.P.value,43);c.fork();c.write('Q',44);assert.match(c.state().lastTrace.join(' '),/число пока 43/);assert.match(c.state().lastTrace.join(' '),/fault/);assert.equal(c.state().owners.P.value,43);assert.equal(c.state().owners.Q.value,44);assert.equal(c.state().copies,1);});
test('zero-length positioned writes do not extend file or shift shared offset',()=>{const f=new m.Descriptors(),fd=f.open();f.read(fd,4);const before=f.state();assert.equal(f.pwrite(fd,[],10),0);assert.deepEqual(f.state(),before);assert.equal(f.write(fd,[]),0);assert.deepEqual(f.state(),before);assert.throws(()=>f.pwrite(999,[],0));});
test('dup shares offset; independent open does not',()=>{const f=new m.Descriptors();const a=f.open(),b=f.dup(a),c=f.open();assert.deepEqual(f.read(a,2),[42,0]);assert.deepEqual(f.read(b,2),[0,0]);assert.deepEqual(f.read(c,2),[42,0]);assert.equal(f.description(a).offset,4);assert.equal(f.description(c).offset,2);f.close(a);assert.deepEqual(f.read(b,1),[]);assert.throws(()=>f.read(a,1));});
test('write after read appends in this non-append opening; pwrite replaces',()=>{const f=new m.Descriptors();const a=f.open();f.read(a,4);f.write(a,m.encode(43));assert.deepEqual(f.state().bytes,[42,0,0,0,43,0,0,0]);const g=new m.Descriptors(),d=g.open();g.read(d,4);g.pwrite(d,m.encode(43),0);assert.equal(g.description(d).offset,4);assert.deepEqual(g.state().bytes,[43,0,0,0]);});
test('fd number reuse does not restore the old description',()=>{const f=new m.Descriptors();const a=f.open();const old=f.fds.get(a);f.close(a);const b=f.open();assert.equal(a,b);assert.notEqual(f.fds.get(b),old);});
test('dirty queue units and service surplus',()=>{assert.equal(m.pressure(60,40,200).fillSeconds,10);assert.equal(m.pressure(30,40,200,100).drainSeconds,10);assert.equal(m.pressure(40,40,200).fillSeconds,null);assert.throws(()=>m.pressure(-1,1,1));assert.throws(()=>m.pressure(1,1,1,2));});
test('acknowledgment and rename do not imply a guaranteed crash result',()=>{const d=new m.Durability();d.advance();assert.deepEqual(d.state().crashAllowed,[42]);d.advance();assert.equal(d.state().tempDurable,true);assert.equal(d.state().visible,42);d.advance();assert.equal(d.state().visible,43);assert.deepEqual(d.state().crashAllowed,[42,43]);d.advance();assert.deepEqual(d.state().crashAllowed,[43]);assert.throws(()=>d.advance());});
test('specified raw bytes and accessed/dirty changes, not just PFN arithmetic',()=>{
 assert.deepEqual(m.inspectEntry(0x900f,true).bytes,[15,144,0,0]);assert.deepEqual(m.inspectEntry(0x12a007).bytes,[7,160,18,0]);
 const read=m.rawWalk(0x403124,0x900f,0x12a007);assert.equal(read.fault,null);assert.equal(read.directoryAfter,0x901f);assert.equal(read.leafAfter,0x12a017);
 const write=m.rawWalk(0x403124,0x900f,0x12a007,'write');assert.equal(write.leafAfter,0x12a037);assert.equal(write.path.physical,0x12a124);
});
test('upper permissions dominate leaf; absent, malformed and COW are distinct',()=>{
 assert.equal(m.rawWalk(0x403124,0x900d,0x12a007,'write').fault,'protection');
 assert.equal(m.rawWalk(0x403124,0x900b,0x12a007,'read').fault,'protection');
 assert.equal(m.rawWalk(0x403124,0x900f,0x12a007,'execute').fault,'protection');
 assert.equal(m.rawWalk(0x403124,0,0).fault,'not-present-directory');assert.equal(m.rawWalk(0x403124,0x900f,0).fault,'not-present-leaf');
 assert.equal(m.rawWalk(0x403124,0x902f,0x12a007).fault,'malformed-directory');assert.equal(m.rawWalk(0x403124,0x900f,0x12a087).fault,'malformed-leaf');
 const cow=m.rawWalk(0x403124,0x901f,0x12a055,'write');assert.equal(cow.fault,'protection');assert.equal(cow.cowCandidate,true);
 assert.equal(m.rawWalk(0x403124,0x900f,0x12a006).fault,'malformed-leaf');
});
test('raw COW rights retain Q and set dirty only on writing owner',()=>{const c=new m.Cow();c.fork();assert.equal(c.state().owners.P.pte,0x12a055);assert.equal(c.state().owners.Q.pte,0x12a055);c.write('P',43);assert.equal(c.state().owners.P.pte,0x12b037);assert.equal(c.state().owners.Q.pte,0x12a055);});
test('shootdown forbids reuse before every CPU and all independent owners release',()=>{const s=new m.Shootdown();assert.throws(()=>s.ack('CPU0'));s.revoke();s.ack('CPU0');s.releaseReference();assert.throws(()=>s.reuse());s.ack('CPU1');s.dmaPins=1;assert.throws(()=>s.reuse());s.dmaPins=0;assert.equal(s.reuse().reused,true);});
test('slot bitmap names actual owners and retains a page with one live object',()=>{const s=new m.Slots64();const addresses=Array.from({length:64},()=>s.allocate(33));assert.equal(new Set(addresses).size,64);assert.equal(s.state().bitmap,'0xffffffffffffffff');assert.throws(()=>s.allocate(1));addresses.slice(1).forEach(x=>s.release(x));assert.deepEqual([s.state().live,s.state().returnable],[1,false]);assert.throws(()=>s.release(addresses[1]));assert.throws(()=>s.release(addresses[0]+1));s.release(addresses[0]);assert.equal(s.state().returnable,true);assert.throws(()=>s.allocate(65));});
test('buddy split/merge preserve arena, and fragmentation is not free byte count',()=>{
 const b=new m.Buddy();const first=b.allocate(3);assert.equal(first.base,0);assert.deepEqual(b.state().free[3],[8]);assert.deepEqual(b.state().free[4],[16]);b.release(0);assert.deepEqual(b.state().free[5],[0]);assert.throws(()=>b.release(0));
 const a=Array.from({length:32},()=>b.allocate(0));a.filter(x=>x.base%2===0).forEach(x=>b.release(x.base));assert.equal(b.state().freeFrames,16);assert.throws(()=>b.allocate(1));a.filter(x=>x.base%2===1).forEach(x=>b.release(x.base));assert.deepEqual(b.state().free[5],[0]);
});
test('buddy mixed history retains all32 frames without overlapping live allocations',()=>{const b=new m.Buddy();let seed=631;const random=n=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%n;};for(let step=0;step<400;step++){const live=b.state().allocated;if(live.length&&random(3)===0)b.release(live[random(live.length)].base);else{try{b.allocate(random(6));}catch(e){assert.match(e.message,/Нет подходящего/);}}const state=b.state(),frames=[];state.free.forEach((bases,order)=>bases.forEach(base=>{for(let i=0;i<2**order;i++)frames.push(base+i);}));state.allocated.forEach(({base,order})=>{for(let i=0;i<2**order;i++)frames.push(base+i);});assert.deepEqual(frames.sort((a,b)=>a-b),Array.from({length:32},(_,i)=>i));}});
test('CLOCK second chance, dirty completion, pin and anonymous no-backing branches',()=>{
 const c=new m.Clock([{id:'A',ref:true},{id:'B',dirty:true},{id:'C',pinned:true},{id:'D',backing:'none'}]);
 assert.deepEqual(Array.from({length:4},()=>c.step().action),['second-chance','start-writeback','pinned','no-backing']);assert.equal(c.step().action,'evicted');assert.equal(c.step().action,'writeback-pending');
 c.complete('B',false);assert.equal(c.state().pages[1].dirty,true);for(let i=0;i<4;i++)c.step();assert.equal(c.state().pages[1].writeback,true);c.complete('B');assert.equal(c.state().pages[1].dirty,false);
 assert.throws(()=>c.touch('A'));assert.throws(()=>c.complete('C'));
});
test('write during writeback cannot be cleared by stale completion',()=>{const c=new m.Clock([{id:'A',dirty:true}]);assert.equal(c.step().action,'start-writeback');c.touch('A',true);c.complete('A');assert.equal(c.state().pages[0].dirty,true);assert.equal(c.step().action,'second-chance');assert.equal(c.step().action,'start-writeback');c.complete('A');assert.equal(c.step().action,'evicted');});
test('OSJ1 fixed bytes, invalid fields/checksum, and incomplete tail',()=>{
 const data=m.journalRecord(1,7,200,43),commit=m.journalRecord(2,7);assert.deepEqual(data.slice(0,20),[79,83,74,49,1,0,4,0,7,0,0,0,200,0,0,0,43,0,0,0]);assert.deepEqual(m.parseRecord(data),{kind:1,sequence:7,target:200,value:43});
 const partial=m.recoverJournal({200:42},[data]);assert.equal(partial.blocks[200],42);assert.deepEqual(partial.applied,[]);assert.equal(m.recoverJournal({200:42},[data,commit]).blocks[200],43);
 const corrupt=[...data];corrupt[16]^=1;assert.throws(()=>m.parseRecord(corrupt));assert.equal(m.recoverJournal({200:42},[corrupt,commit]).blocks[200],42);
 assert.equal(m.recoverJournal({200:42},[data,m.journalRecord(2,8)]).blocks[200],42);assert.throws(()=>m.journalRecord(2,7,1));assert.throws(()=>m.parseRecord(data.slice(0,23)));
});
test('journal replay is idempotent with unchanged checkpoint and stops at invalid prefix',()=>{const log=[m.journalRecord(1,7,200,43),m.journalRecord(2,7)];const x=m.recoverJournal({200:42},log);assert.equal(m.recoverJournal(x.blocks,log).blocks[200],43);assert.equal(m.recoverJournal(x.blocks,log,7).stop,'Нарушен порядок DATA');const bad=m.journalRecord(2,9);assert.deepEqual(m.recoverJournal({200:42},[bad,...log]).applied,[]);});
console.log(JSON.stringify({result:'PASS',checks,kind:'pure models; no hardware/kernel/storage mutation'}));
