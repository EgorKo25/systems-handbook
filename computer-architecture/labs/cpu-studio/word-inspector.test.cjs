'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { defaults, assemble, Machine } = require('./engine.js');

function start() {
  const config = { ...defaults(), registers: 4, memorySize: 256 };
  config.instructions.push(
    { name: 'INC4', opcode: 0x3c, format: 'R', microcode: [{ op: 'add', dst: 'd', a: 'd', b: 4 }] },
    { name: 'ADJUST', opcode: 0xa7, format: 'RI', microcode: [{ op: 'add', dst: 'd', a: 'd', b: 'imm' }] },
  );
  const program = assemble(`
    .org 0x40
    LDI r3, 6
    INC4 r3
    ADJUST r3, -2
    HALT
  `, config);
  const machine = new Machine(config);
  machine.load(program);
  return { machine, program };
}

test('inspecting INC4 decodes its memory word without running its microcode', () => {
  const { machine } = start();
  assert.equal(machine.step().instruction, 'LDI');
  const before = machine.snapshot();

  const inspected = machine.inspectInstruction();
  assert.equal(inspected.address, 0x44);
  assert.deepEqual(inspected.bytes, [0x3c, 0x03, 0x00, 0x00]);
  assert.equal(inspected.word, 0x0000033c);
  assert.equal(inspected.instruction.name, 'INC4');
  assert.equal(inspected.instruction.format, 'R');
  assert.deepEqual(inspected.operands, { d: 3 });
  assert.equal(inspected.error, null);
  assert.deepEqual(machine.snapshot(), before);

  assert.equal(machine.step().instruction, 'INC4');
  assert.equal(machine.pc, 0x48);
  assert.equal(machine.registers[3], 10);
});

test('inspection and execution use the edited ADJUST word while the listing retains the original bytes', () => {
  const { machine, program } = start();
  const originalBytes = [0xa7, 0x03, 0xfe, 0xff];
  const beforeExecution = machine.inspectInstruction(0x48);
  assert.deepEqual(beforeExecution.bytes, originalBytes);
  assert.equal(beforeExecution.word, 0xfffe03a7);
  assert.deepEqual(beforeExecution.operands, { d: 3, imm: -2 });

  assert.equal(machine.step().instruction, 'LDI');
  assert.equal(machine.step().instruction, 'INC4');
  assert.equal(machine.registers[3], 10);
  machine.memory[0x4a] = 0xff;
  const beforeInspection = machine.snapshot();

  const edited = machine.inspectInstruction();
  assert.equal(edited.address, 0x48);
  assert.deepEqual(edited.bytes, [0xa7, 0x03, 0xff, 0xff]);
  assert.equal(edited.word, 0xffff03a7);
  assert.equal(edited.instruction.name, 'ADJUST');
  assert.equal(edited.instruction.format, 'RI');
  assert.deepEqual(edited.operands, { d: 3, imm: -1 });
  assert.equal(edited.error, null);
  assert.deepEqual(machine.snapshot(), beforeInspection);
  assert.deepEqual(program.listing.find(row => row.address === 0x48).bytes, originalBytes);

  assert.equal(machine.step().instruction, 'ADJUST');
  assert.equal(machine.pc, 0x4c);
  assert.equal(machine.registers[3], 9);
});

test('reserved register bits are reported by inspection and do not advance PC or change registers on execution', () => {
  const { machine } = start();
  assert.equal(machine.step().instruction, 'LDI');
  machine.memory[0x45] = 0x13;
  const before = machine.snapshot();

  const inspected = machine.inspectInstruction();
  assert.equal(inspected.address, 0x44);
  assert.deepEqual(inspected.bytes, [0x3c, 0x13, 0x00, 0x00]);
  assert.equal(inspected.word, 0x0000133c);
  assert.equal(inspected.instruction.name, 'INC4');
  assert.equal(inspected.operands, null);
  assert.match(inspected.error, /неиспользуемом поле регистра/);
  assert.deepEqual(machine.snapshot(), before);

  const event = machine.step();
  assert.equal(event.kind, 'fault');
  assert.equal(event.pc, before.pc);
  assert.equal(event.message, inspected.error);
  assert.deepEqual(machine.snapshot(), { ...before, fault: inspected.error });
});
