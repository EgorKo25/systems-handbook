const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {simulate}=require('../sources/eviction.js');
const misses=(trace,n,p)=>simulate(trace,n,p).at(-1).misses;
const belady='1 2 3 4 1 2 5 1 2 3 4 5'.split(' ');
assert.equal(misses(belady,3,'FIFO'),9);
assert.equal(misses(belady,4,'FIFO'),10);
let cases=2;
// Exhaustive short traces: OPT lower bound; LRU stack property; resident invariants.
for(let code=0;code<729;code++){
 let x=code;const trace=Array.from({length:6},()=>{const k=String(x%3);x=Math.floor(x/3);return k;});
 for(let n=1;n<=3;n++){
  const opt=misses(trace,n,'OPT');
  for(const policy of ['FIFO','LRU','LFU','CLOCK','OPT']){
   const rows=simulate(trace,n,policy);
   assert.ok(rows.at(-1).misses>=opt);
   for(const r of rows){assert.ok(r.after.length<=n);assert.equal(new Set(r.after).size,r.after.length);assert.ok(r.after.includes(r.key));assert.equal(r.hit,r.before.includes(r.key));}
   cases++;
  }
  if(n<3){assert.ok(misses(trace,n+1,'LRU')<=misses(trace,n,'LRU'));cases++;}
 }
}
assert.throws(()=>simulate(['a'],0,'LRU'));assert.throws(()=>simulate(['a'],1,'unknown'));cases+=2;
const result={status:'PASS',cases,scope:'Belady FIFO anomaly, exhaustive 729 traces, OPT lower bound, LRU stack property, resident invariants, invalid inputs'};
fs.writeFileSync(path.join(__dirname,'eviction-results.json'),JSON.stringify(result,null,2)+'\n');console.log(result);
