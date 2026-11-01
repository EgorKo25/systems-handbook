/* Check the published numerical examples and mathematical guarantees, offline. */
'use strict';
const assert = require('node:assert/strict');
const m = require('./theory-models.js');
let assertions = 0;
function equal(a, b) { assert.deepEqual(a, b); assertions++; }
function near(a, b, e=1e-9) { assert.ok(Math.abs(a-b)<e, `${a} != ${b}`); assertions++; }
near(m.capacity(1,20).ratio, 100);
near(m.capacity(1,20).mbps, 6.658211482751795);
near(m.capacity(1,30).mbps, 9.967226258835993);
near(m.capacity(2,20).mbps, 2*m.capacity(1,20).mbps);
equal(m.crc('110101'), { checksum:'111', transmitted:'110101111', received:'110101111', syndrome:'000', detected:false });
equal(m.crc('110101',1).syndrome,'001');
equal(m.remainder(0b110100100),0); // Explicit undetected error = generator polynomial.
// Exhaust every nonzero burst of length <= degree 3, at every possible offset.
// This checks the code's detection guarantee, not just one canned vector.
for (let message = 0; message < 256; message++) {
  const bits = message.toString(2).padStart(8,'0');
  const word = parseInt(m.crc(bits).transmitted,2);
  equal(m.remainder(word),0);
  for (let length=1; length<=3; length++) {
    for (let error=1; error<(1<<length); error++) {
      if (!(error&1) || !(error&(1<<(length-1)))) continue;
      for (let offset=0; offset<=11-length; offset++) {
        assert.notEqual(m.remainder(word^(error<<offset)),0); assertions++;
      }
    }
  }
}
equal(m.crc('000001').transmitted.length,9); // Leading zeroes survive display.
equal(m.crc('1'.repeat(24),27).detected,true); // Maximum allowed bit position.
equal(m.burst(50,10,100,5), {bits:4000000,bytes:500000,waitMs:400,drainMs:800,growingAfter:false});
equal(m.burst(50,10,100,0).drainMs,400);
equal(m.burst(50,10,100,10).drainMs,null);
equal(m.burst(50,10,100,11).drainMs,null);
equal(m.burst(5,10,100,20).drainMs,0); // Empty at end of this observed burst.
equal(m.burst(5,10,100,20).growingAfter,true); // A new queue grows after that instant.
equal(m.burst(5,10,100,10).growingAfter,false); // Equal rates leave the empty queue empty.
equal(m.schedule([0,1,2,3],[2,2,2,2]).map(x=>[x.start,x.end,x.wait,x.total]), [[0,2,0,2],[2,4,1,3],[4,6,2,4],[6,8,3,5]]);
equal(m.schedule([0,10],[2,2]).map(x=>x.wait),[0,0]);
const p=m.pipeline(Array(10).fill(12000),Array(3).fill(100e6));
near(p[0][2].end,0.00036); near(p[9][2].end,0.00144);
// A slower middle resource is the steady-state bottleneck.
const slow=m.pipeline(Array(10).fill(12000),[100e6,10e6,100e6]);
near(slow[9][2].end-slow[8][2].end,0.0012);
for (const run of [()=>m.capacity('',20),()=>m.capacity(1,Infinity),()=>m.crc('102'),()=>m.crc('1',5),()=>m.crc('1',1.1),()=>m.burst(10,0,100,0),()=>m.schedule([2,1],[1,1]),()=>m.pipeline([100],[0])]) {
  assert.throws(run); assertions++;
}
console.log(`Network theory models: PASS (${assertions} assertions; CRC bursts, capacity, queue, pipeline).`);
