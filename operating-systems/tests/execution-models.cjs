'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const m=require('../labs/execution/models.js');let checks=0;
const ok=(x,msg)=>{assert.ok(x,msg);checks++;};
const eq=(a,b,msg)=>{assert.deepEqual(a,b,msg);checks++;};
const contract=JSON.parse(fs.readFileSync(path.join(__dirname,'../labs/trace-contract.json'),'utf8'));
eq(m.TRACE.file,contract.file.name);eq(Buffer.from(m.TRACE.before).toString('hex'),contract.file.before_hex);eq(Buffer.from(m.TRACE.after).toString('hex'),contract.file.after_hex);eq(m.TRACE.va.toLowerCase(),contract.memory.user_buffer_va.toLowerCase());eq(m.TRACE.pa.toLowerCase(),contract.memory.user_buffer_pa.toLowerCase());eq(m.TRACE.rewriteOffset,0);eq(m.TRACE.afterReadOffset,4);
const cached=m.boundaryTrace('cached');eq(cached.map(s=>s.thread),cached.map(()=> 'T1'));eq(cached.at(-1).switches,0);eq(cached.at(-1).buffer,[42,0,0,0]);eq(cached.at(-1).offset,4);eq(cached[1].mode,'пользователь');eq(cached[1].sp,'0x007FEFFC');eq(cached[3].savedUser.pc,'0x00402010');eq(cached[3].savedUser.sp,'0x007FEFFC');eq(cached.at(-1).pc,'0x00401004');eq(cached.at(-1).sp,'0x007FF000');eq(cached.at(-1).registers.result,4);
const frame=m.savedUserWords(cached[3].savedUser),completedFrame=m.savedUserWords(cached.at(-1).savedUser);
eq(frame.length,8);eq(frame[0].bytes,[16,32,64,0]);eq(frame[1].bytes,[252,239,127,0]);eq(frame[3].value,7);eq(frame[5].bytes,[36,49,64,0]);eq(frame[7].valid,false);eq(frame[7].address,'0x8000F00C');eq(completedFrame[7].valid,true);eq(completedFrame[7].bytes,[4,0,0,0]);
for(const f of frame){eq(Buffer.from(f.bytes).readUInt32LE(),f.value>>>0);eq(f.bytes.length,4);}eq(frame.slice(0,7),completedFrame.slice(0,7),'result may change without corrupting caller state');assert.throws(()=>m.savedUserWords(null));assert.throws(()=>m.savedUserWords(m.boundaryTrace('fault')[1].savedUser));
const blocked=m.boundaryTrace('blocked'),irq=blocked.find(s=>s.mode==='ядро/IRQ'),other=blocked.find(s=>s.process==='P2'&&s.mode==='пользователь');eq(other.thread,'T2');eq(other.addressSpace,'AS2');eq(other.registers,{R1:99,R2:0});eq(irq.thread,'T2');eq(irq.savedUser.owner,'T1/P1/AS1');eq(irq.irqFrame.thread,'T2');eq(irq.irqFrame.registers,{R1:99,R2:0});eq(irq.threads.T1,'готов');eq(irq.switches,1);eq(irq.buffer,[]);const afterIRQ=blocked[blocked.indexOf(irq)+1];eq(afterIRQ.thread,'T2');eq(afterIRQ.registers,{R1:99,R2:0});const resumed=blocked.find(s=>s.title.startsWith('T1 продолжает'));eq(resumed.pc,resumed.savedKernel.pc);eq(resumed.sp,resumed.savedKernel.sp);eq(resumed.registers.operation,7);eq(blocked.at(-1).switches,2);eq(blocked.at(-1).offset,4);eq(blocked.at(-1).registers.result,4);
const fault=m.boundaryTrace('fault');eq(fault[0].pc,fault[3].pc);eq(fault.at(-1).registers.result,42);eq(fault.at(-1).offset,0);eq(fault.at(-1).switches,0);const bad=m.boundaryTrace('bad-buffer');eq(bad.at(-1).bufferAllowed,false);eq(cached.at(-1).bufferAllowed,true);eq(bad.at(-1).offset,0);eq(bad.at(-1).buffer,[]);eq(bad.at(-1).registers.result,{error:'BAD_BUFFER',transferred:0});
eq(m.savedUserWords(bad.at(-1).savedUser).at(-1).bytes,[242,255,255,255]);
for(const badName of ['',null,'bogus'])assert.throws(()=>m.boundaryTrace(badName));
const fc=m.schedule(m.WORKLOADS.cpu,{policy:'fcfs'}),rr=m.schedule(m.WORKLOADS.cpu,{policy:'rr',quantum:2});eq(fc.jobs.map(j=>j.response),[0,7,8]);eq(fc.jobs.map(j=>j.finish),[8,10,11]);eq(rr.jobs.map(j=>j.response),[0,1,2]);eq(rr.jobs.map(j=>j.finish),[11,4,5]);eq(rr.jobs.map(j=>j.readyWait),[3,1,2]);eq(rr.wall,11);eq(rr.cpu,11);eq(rr.switches,3);
for(const policy of ['rr','fcfs']){
 const io=m.schedule(m.WORKLOADS.io,{policy,quantum:2});eq(io.wall,9);eq(io.jobs[0].blocked,3);eq(io.cpu,9);ok(io.timeline.find(r=>r.waiting.some(w=>w.id==='A'&&w.wake===5)),'IO wake boundary');
 for(const j of io.jobs)eq(j.turnaround,j.cpu+j.readyWait+j.blocked,'conservation');
}
let seed=20261101;const random=n=>{seed=(seed*1664525+1013904223)>>>0;return seed%n;};
for(let scenario=0;scenario<80;scenario++){
 const jobs=Array.from({length:1+random(5)},(_,i)=>({id:'J'+i,arrival:random(8),bursts:random(2)?[1+random(7)]:[1+random(5),1+random(5),1+random(5)]}));
 const original=JSON.stringify(jobs);
 for(const policy of ['rr','fcfs']){
  const r=m.schedule(jobs,{policy,quantum:1+random(4)});eq(JSON.stringify(jobs),original,'no mutation');eq(r.cpu,jobs.reduce((a,j)=>a+j.bursts.filter((_,i)=>i%2===0).reduce((x,y)=>x+y,0),0));eq(r.timeline.filter(x=>x.running!==null).length,r.cpu);
  for(const j of r.jobs){eq(j.turnaround,j.cpu+j.readyWait+j.blocked);ok(j.response>=0);ok(j.finish>j.first);}
  for(const row of r.timeline){ok(!row.running||!row.ready.includes(row.running));eq(new Set(row.ready).size,row.ready.length);ok(!row.waiting.some(w=>row.ready.includes(w.id)));if(row.ready.length)ok(row.running!==null);}
 }
}
for(const jobs of [[],[{id:'A',arrival:0,bursts:[0]}],[{id:'A',arrival:0,bursts:[1,2]}],[{id:'A',arrival:-1,bursts:[1]}],[{id:'A',arrival:0,bursts:[1]},{id:'A',arrival:0,bursts:[1]}]])assert.throws(()=>m.schedule(jobs));assert.throws(()=>m.schedule(m.WORKLOADS.cpu,{quantum:0}));
const single=m.schedule([{id:'A',arrival:3,bursts:[1,2,1]}]);eq(single.cpu,2);eq(single.wall,7);eq(single.jobs[0].blocked,2);eq(single.jobs[0].readyWait,0);eq(single.jobs[0].response,0);
for(const affinity of ['both','cpu0']){const r=m.smp(affinity);eq(r.cpu,12);eq(r.wall,affinity==='both'?6:12);eq(r.utilization,affinity==='both'?1:.5);for(const row of r.timeline){const active=row.cpus.filter(Boolean);eq(new Set(active).size,active.length);if(affinity==='cpu0')eq(row.cpus[1],null);}}
const life=m.lifecycleTrace(),loadFailure=m.lifecycleTrace('load');eq(life.filter(r=>r.child!==null).map(r=>r.child),['P1','P1','P1','P1']);eq(life.at(-1).publicObjects,[]);eq(life.at(-1).result,7);eq(loadFailure.at(-1).privateObjects,[]);eq(loadFailure.at(-1).publicObjects,[]);eq(loadFailure.at(-1).child,null);
const service=m.serviceTrace();ok(service.findIndex(r=>!r.accepting&&r.inflight===2)>service.findIndex(r=>r.accepting));eq(service.at(-1).durable,true);eq(service.at(-1).inflight,0);eq(m.serviceTrace('prepare-fails').some(r=>r.ready),false);eq(m.serviceTrace('forced-stop').at(-1).durable,false);eq(m.serviceTrace('forced-stop').at(-1).inflight,2);
const snapshots=JSON.parse(fs.readFileSync(path.join(__dirname,'../labs/execution/traces.json'),'utf8'));
for(const kind of ['cached','blocked','fault','bad-buffer'])eq(snapshots.boundary[kind],m.boundaryTrace(kind),'served diagram state must equal the executable model');
for(const branch of ['none','load'])eq(snapshots.lifecycle[branch],m.lifecycleTrace(branch));
for(const branch of ['normal','prepare-fails','forced-stop'])eq(snapshots.service[branch],m.serviceTrace(branch));
eq(snapshots.scheduling.fcfs,m.schedule(m.WORKLOADS.cpu,{policy:'fcfs'}));eq(snapshots.scheduling.rr,m.schedule(m.WORKLOADS.cpu,{policy:'rr',quantum:2}));eq(snapshots.scheduling.io,m.schedule(m.WORKLOADS.io,{policy:'rr',quantum:2}));
for(const affinity of ['both','cpu0'])eq(snapshots.smp[affinity],m.smp(affinity));
for(const q of [1,2,4,8]){const r=m.schedule(m.WORKLOADS.cpu,{policy:'rr',quantum:q});eq(r.cpu,11);eq(r.wall,11);}eq(m.schedule(m.WORKLOADS.cpu,{policy:'rr',quantum:1}).jobs.map(j=>j.response),[0,0,1]);eq(m.schedule(m.WORKLOADS.cpu,{policy:'rr',quantum:8}).jobs.map(j=>j.finish),[8,10,11]);
console.log('PASS execution models: '+checks+' assertions; pure teaching state machines, no native OS or UI claim');
