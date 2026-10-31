const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {ttlBounds,slabBudget}=require('../sources/resource-labs.js');
const base={rate:20000,keys:5000,budget:2500,background:0,freshness:1,sourceAge:0,fillDelay:0};
let cases=0;
let r=ttlBounds(base);assert.equal(r.lower,1.75);assert.equal(r.atUpper,4000);assert.equal(r.feasible,false);cases++;
r=ttlBounds({...base,freshness:2});assert.equal(r.feasible,true);cases++;
assert.equal(ttlBounds({...base,background:2500}).feasible,false);cases++;
assert.equal(ttlBounds({...base,rate:0,budget:0}).feasible,true);cases++;
assert.equal(ttlBounds({...base,rate:0,budget:0,background:1}).feasible,false);cases++;
assert.equal(ttlBounds({...base,fillDelay:2}).feasible,false);cases++;
// Substitute every computed finite lower bound into the source-load equation.
for(let rate=100;rate<=10000;rate+=100){for(const budget of [10,100,1000,20000]){
 const v={...base,rate,budget};const x=ttlBounds(v);
 const load=rate/(1+rate/v.keys*x.lower);
 assert.ok(load<=budget+1e-8);if(x.lower>0)assert.ok(Math.abs(load-budget)<1e-8);cases++;
}}
for(let payload=0;payload<=1100;payload++){for(let pages=1;pages<=4;pages++){
 const x=slabBudget({payload,key:16,overhead:64,count:13,pages});
 if(!x.oversize){assert.equal(x.valueBytes+x.metadata+x.padding+x.freeChunks*x.chunk+x.tail,x.reserved);assert.equal(x.stored+x.missing,13);assert.ok(x.chunk>=x.size);}
 cases++;
}}
assert.equal(slabBudget({payload:150,key:16,overhead:64,count:5,pages:1}).missing,1);cases++;
const report={status:'PASS',cases,scope:'TTL infeasible bounds and substitution; slab byte conservation, rounding and capacity'};
fs.writeFileSync(path.join(__dirname,'resource-results.json'),JSON.stringify(report,null,2)+'\n');console.log(report);
