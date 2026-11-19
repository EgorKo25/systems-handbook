'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const cpu = require('../logic/model.js');
const {create, clock, fromSnapshot} = require('./datapath.js');

const samples = [
  ['jal', 0x1004, 0x008000ef, 0,      0x100c, 0x1008],
  ['jal', 0x1014, 0x010000ef, 0x1008, 0x1024, 0x1018],
  ['jalr',0x1028, 0x00008067, 0x1018, 0x1018, 0x1018],
  ['jalr',0x1020, 0x00008067, 0x1008, 0x1008, 0x1008],
];
for (const [op, pc, word, ra, target, nextRa] of samples) {
  test(op + ' snapshot at ' + cpu.hex(pc), () => {
    const {state} = fromSnapshot('#' + op + '?pc=' + cpu.hex(pc) + '&word=' + cpu.hex(word) + '&x1=' + cpu.hex(ra));
    const ram = state.memory.slice();
    let current = state;
    for (let tick = 1; tick <= 3; tick++) {
      current = clock(current);
      assert.equal(current.pc, pc);
      assert.equal(current.x1, ra);
    }
    assert.deepEqual(current.jumpEvent.jump, {target, link:pc + 4, register:op === 'jal' ? 1 : 0});
    const end = clock(current);
    assert.equal(end.pc, target);
    assert.equal(end.x1, nextRa);
    assert.equal(end.fault, null);
    assert.deepEqual(end.memory, ram);
  });
}

test('JALR clears bit zero before the alignment check', () => {
  const finish = value => clock(clock(clock(clock(create(value, 0, 'JALR')))));
  assert.equal(finish(0x1019).pc, 0x1018);
  const trap = finish(0x101b);
  assert.equal(trap.fault, 'instruction-address-misaligned');
  assert.equal(trap.x1, 0x101b);
  assert.equal(trap.pc, cpu.ENTRY);
});
test('A trapping JAL leaves the saved continuation untouched', () => {
  const before = create(0x1008, 2, 'JAL', undefined, {}, {pc:0x1014});
  const end = clock(clock(clock(clock(before))));
  assert.equal(end.fault, 'instruction-address-misaligned');
  assert.equal(end.pc, 0x1014);
  assert.equal(end.x1, 0x1008);
  assert.deepEqual(end.memory, before.memory);
});
test('Snapshot rejects the wrong JAL destination and JALR profile', () => {
  for (const [op, source] of [['jal','jal x0, 8'], ['jalr','jalr x1, 0(x1)'], ['jalr','jalr x0, 4(x1)']]) {
    const word = cpu.assemble(source)[0].word;
    assert.throws(() => fromSnapshot('#' + op + '?pc=00001004&word=' + cpu.hex(word) + '&x1=00001018'));
  }
  assert.throws(() => fromSnapshot('#jal?pc=00001004&word=008000ef&x1=00000000&x1=00001018'));
});
