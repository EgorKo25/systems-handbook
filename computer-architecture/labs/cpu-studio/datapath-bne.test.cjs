'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const cpu = require('../logic/model.js');
const { create, clock, fromSnapshot } = require('./datapath.js');

const pc = 0x1008;
const branchSnapshot = value =>
  '#bne?pc=00001008&word=fe039ee3&x7=' + cpu.hex(value);

for (const [value, expected] of [[2, 0x1004], [1, 0x1004], [0, 0x100C]]) {
  test('BNE snapshot with x7=' + value, () => {
    const {state} = fromSnapshot(branchSnapshot(value));
    const ram = state.memory.slice();
    const decoded = clock(clock(state));
    assert.equal(decoded.signals.registerWrite, false);
    assert.equal(decoded.signals.memoryWrite, false);
    const compared = clock(decoded);
    assert.equal(compared.pc, pc);
    assert.equal(compared.branchEvent.branch.taken, value !== 0);
    assert.equal(compared.branchEvent.branch.target, 0x1004);
    const completed = clock(compared);
    assert.equal(completed.pc, expected);
    assert.equal(completed.x7, value);
    assert.equal(completed.x6, state.x6);
    assert.equal(completed.fault, null);
    assert.deepEqual(completed.memory, ram);
    assert.deepEqual(compared.branchEvent.registers, []);
    assert.deepEqual(compared.branchEvent.memory, []);
  });
}

test('Only a taken misaligned target raises an exception', () => {
  const finish = value => clock(clock(clock(clock(create(value, -2, 'BNE', 0, {}, {pc})))));
  const taken = finish(1);
  assert.equal(taken.fault, 'instruction-address-misaligned');
  assert.equal(taken.pc, pc);
  assert.equal(taken.x7, 1);
  const skipped = finish(0);
  assert.equal(skipped.fault, null);
  assert.equal(skipped.pc, pc + 4);
});

test('BNE snapshot rejects invalid fields and register combinations', () => {
  assert.throws(() => fromSnapshot(branchSnapshot(2) + '&x7=00000000'));
  assert.throws(() => fromSnapshot(branchSnapshot(2).replace('00001008', '0000100a')));
  const wrong = cpu.hex(cpu.assemble('bne x6, x0, -4')[0].word);
  assert.throws(() => fromSnapshot(branchSnapshot(2).replace('fe039ee3', wrong)));
});

for (const [op, source] of [['addi','addi x6,x6,1'],['lw','lw x6,4(x5)'],['sw','sw x6,4(x5)']]) {
  test('Existing ' + op + ' snapshot keeps its format and effect', () => {
    const word = cpu.hex(cpu.assemble(source)[0].word);
    const data = op === 'addi' ? '' : '&x5=00002000&ram=11223344';
    const {state} = fromSnapshot('#' + op + '?pc=00001008&word=' + word + '&x6=0000002a' + data);
    const end = clock(clock(clock(clock(state))));
    assert.equal(end.pc, pc + 4);
    assert.equal(end.x6, {addi:43,lw:0x11223344,sw:42}[op]);
    if (op === 'sw') assert.equal(cpu.read32(end.memory, 0x2004), 42);
  });
}
