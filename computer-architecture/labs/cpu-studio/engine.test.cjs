'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { defaults, validateConfig, signature, assemble, Machine } = require('./engine.js');

function start(source, config = defaults()) {
  const program = assemble(source, config);
  const machine = new Machine(config);
  machine.load(program);
  return { machine, program };
}

function untilHalt(machine) {
  for (let index = 0; index < 100; index += 1) {
    const result = machine.step();
    if (result.kind === 'halt') return;
    assert.equal(result.kind, 'step', result.message);
  }
  assert.fail('Program did not halt');
}

test('assembler places code, forward addresses and little-endian data', () => {
  const { machine, program } = start(`
    .org 0x20
    .word start, -1
    .byte -1, 0b1010, 0xff
    .ascii "A;,", "Я"
    .asciiz "Z"
    .org 0x40
    .entry start
    start: LDI r3, -2
    next: ADD r5, r3, r4
    HALT
  `);
  assert.equal(program.origin, 0x20);
  assert.equal(program.entry, 0x40);
  assert.deepEqual(program.symbols, { start: 0x40, next: 0x44 });
  assert.deepEqual(program.listing[0].bytes, [0x40, 0, 0, 0, 255, 255, 255, 255]);
  assert.deepEqual(program.listing[2].bytes, [65, 59, 44, 208, 175]);
  assert.deepEqual(program.listing[3].bytes, [90, 0]);
  assert.deepEqual(program.listing[4].bytes, [2, 3, 254, 255]);
  assert.deepEqual(program.listing[5].bytes, [3, 0x35, 4, 0]);
  assert.equal(program.bytes[0x32 - program.origin], 0);
  assert.equal(machine.pc, 0x40);
  assert.equal(machine.stackFloor, 0x4c);
  untilHalt(machine);
  assert.equal(machine.registers[5], 0xfffffffe);
});

test('ALU wraps at configured width and sets carry, borrow, sign and overflow', () => {
  const config = { ...defaults(), bits: 8, registers: 4, memorySize: 256 };
  const { machine } = start(`
    LDI r0, 127
    ADDI r0, 1
    ADD r1, r0, r0
    SUB r2, r1, r0
    CMP r2, r2
    LDI r0, 255
    MUL r0, r0, r0
    HALT
  `, config);
  machine.step();
  machine.step();
  assert.equal(machine.registers[0], 128);
  assert.deepEqual(machine.flags, { z: false, n: true, c: false, v: true });
  machine.step();
  assert.deepEqual(machine.flags, { z: true, n: false, c: true, v: true });
  machine.step();
  assert.equal(machine.registers[2], 128);
  assert.deepEqual(machine.flags, { z: false, n: true, c: true, v: true });
  machine.step();
  assert.deepEqual(machine.flags, { z: true, n: false, c: false, v: false });
  untilHalt(machine);
  assert.equal(machine.registers[0], 1);
  assert.deepEqual(machine.flags, { z: false, n: false, c: true, v: false });
});

test('conditional loop, nested calls, data stack and ports operate together', () => {
  const config = { ...defaults(), bits: 8, memorySize: 4096 };
  const { machine } = start(`
    .org 0x200
    LDI r0, 4
    LDI r1, 0
    loop: CALL outer
    ADDI r0, -1
    JNZ loop
    OUT r1, 65535
    HALT
    outer: PUSH r0
    CALL inner
    POP r0
    RET
    inner: ADD r1, r1, r0
    LDI r0, 0
    RET
  `, config);
  untilHalt(machine);
  assert.deepEqual(machine.outputs, [{ port: 65535, value: 10 }]);
  assert.equal(machine.sp, 4096);
  assert.equal(machine.registers[0], 0);
});

test('the next fetch reads newly written machine bytes', () => {
  const { machine, program } = start(`
    LDI r0, target
    LDI r1, 31
    STB r1, [r0]
    JMP target
    target: NOP
    LDI r2, 77
    HALT
  `);
  untilHalt(machine);
  assert.equal(machine.memory[program.symbols.target], 31);
  assert.equal(machine.registers[2], 0);
  assert.equal(machine.steps, 5);
});

test('memory operands support signed displacements and narrow byte access', () => {
  const { machine } = start(`
    LDI r1, end
    LDI r0, -2
    ST r0, [r1 - 4]
    LD r2, r1, -4
    LDB r3, [r1 - 4]
    HALT
    data: .word 0
    end:
  `);
  untilHalt(machine);
  assert.equal(machine.registers[2], 0xfffffffe);
  assert.equal(machine.registers[3], 0xfe);
});

test('custom instruction format encodes operands and executes custom microcode', () => {
  const config = defaults();
  config.instructions.push({
    name: 'inc4', opcode: 0xa7, format: 'R',
    microcode: [{ op: 'add', dst: 'd', a: 'd', b: 4 }],
  });
  const { machine, program } = start('LDI r7, 6\nINC4 r7\nHALT', config);
  assert.deepEqual(program.listing[1].bytes, [0xa7, 7, 0, 0]);
  assert.equal(signature(config), signature({ ...config, instructions: config.instructions.slice().reverse() }));
  assert.equal(validateConfig(config).instructions.at(-1).name, 'INC4');
  untilHalt(machine);
  assert.equal(machine.registers[7], 10);
});

test('waiting for a second input rolls back the entire instruction and preserves FIFO input', () => {
  const config = defaults();
  config.instructions.push({
    name: 'COMBINE', opcode: 0x99, format: 'RR',
    microcode: [
      { op: 'mov', dst: 'd', a: 45 },
      { op: 'in', dst: 's', port: 1 },
      { op: 'store8', addr: 50, a: 's' },
      { op: 'out', port: 2, a: 'd' },
      { op: 'in', dst: 'd', port: 1 },
      { op: 'out', port: 2, a: 'd' },
    ],
  });
  const { machine } = start('COMBINE r0, r1\nHALT', config);
  machine.feed(1, [77]);
  const before = machine.snapshot();
  assert.equal(machine.step().port, 1);
  assert.deepEqual(machine.snapshot(), before);
  machine.feed(1, 90);
  untilHalt(machine);
  assert.deepEqual(machine.registers.slice(0, 2), [90, 77]);
  assert.deepEqual(machine.outputs, [{ port: 2, value: 45 }, { port: 2, value: 90 }]);
  assert.equal(machine.memory[50], 77);
  assert.deepEqual(machine.snapshot().inputs, {});
});

test('memory overflow and division faults are atomic across multiple microoperations', () => {
  const config = defaults();
  config.instructions.push({
    name: 'TXN', opcode: 0x85, format: 'R',
    microcode: [
      { op: 'add', dst: 'd', a: 'd', b: 1 },
      { op: 'store8', addr: 50, a: 'd' },
      { op: 'store', addr: 65535, a: 'd' },
    ],
  });
  const txn = start('TXN r0\nHALT', config).machine;
  const div = start('DIV r0, r0, r1\nHALT').machine;
  for (const [machine, diagnostic] of [[txn, /Запись/], [div, /Деление на ноль/]]) {
    const before = machine.snapshot();
    const event = machine.step();
    assert.equal(event.kind, 'fault');
    assert.match(event.message, diagnostic);
    assert.deepEqual(machine.snapshot(), { ...before, fault: event.message });
  }
});

test('invalid PC, stack underflow, and collision with loaded image produce faults', () => {
  const config = { ...defaults(), memorySize: 256 };
  const { machine } = start('.org 248\nPUSH r0\nHALT', config);
  assert.match(machine.step().message, /Стек/);
  assert.equal(machine.sp, 256);
  const emptyReturn = start('RET', config).machine;
  assert.match(emptyReturn.step().message, /стеке/);
  emptyReturn.pc += 1;
  assert.match(emptyReturn.step().message, /кратен/);
});

test('restore and load validate all fields before committing', () => {
  const { machine, program } = start('LDI r1, 19\nHALT');
  machine.step();
  const saved = JSON.parse(JSON.stringify(machine.snapshot()));
  machine.step();
  machine.restore(saved);
  assert.deepEqual(machine.snapshot(), saved);
  const malformed = { ...saved, registers: saved.registers.map(() => 1), inputs: { '-1': [1] } };
  assert.throws(() => machine.restore(malformed), /очередь/);
  assert.deepEqual(machine.snapshot(), saved);
  const incompatible = assemble('HALT', { ...defaults(), bits: 8 });
  assert.throws(() => machine.load(incompatible), /другой конфигурации/);
  assert.throws(() => machine.load({ ...program, bytes: [999] }), /массив байтов/);
  assert.deepEqual(machine.snapshot(), saved);
});

test('assembler reports source lines for overlaps, malformed values and illegal operands', () => {
  const examples = [
    ['HALT\n.org 0x1001\n.byte 1', /Строка 3.*уже занят/],
    ['x: HALT\nx: HALT', /Строка 2.*Повтор метки/],
    ['HALT\nJMP unknown', /Строка 2.*Неизвестная метка/],
    ['JMP 3', /Строка 1.*кратен/],
    ['LDI r99, 5', /Строка 1.*Неизвестный регистр/],
    ['LDI r0, 65536', /Строка 1.*не помещается/],
    ['HALT\n.byte -129', /Строка 2.*не помещается/],
    ['.ascii "unclosed', /Строка 1.*Незакрытая/],
    ['.org 0xffff\n.word 1', /Строка 2.*за пределы/],
  ];
  for (const [source, diagnostic] of examples) assert.throws(() => assemble(source), diagnostic);
});

test('configuration rejects duplicates and invalid or oversized microcode', () => {
  const example = (name, opcode, microcode) => ({ name, opcode, format: 'R', microcode });
  const configs = [
    (config) => config.instructions.push(example('nop', 0x80, [{ op: 'nop' }])),
    (config) => config.instructions.push(example('OTHER', 0, [{ op: 'nop' }])),
    (config) => config.instructions.push(example('OTHER', 0x80, [{ op: 'eval' }])),
    (config) => config.instructions.push(example('OTHER', 0x80, [{ op: 'mov', dst: 'pc', a: 0 }])),
    (config) => config.instructions.push(example('OTHER', 0x80, [{ op: 'mov', dst: 'd', a: 's' }])),
    (config) => config.instructions.push(example('OTHER', 0x80, [{ op: 'nop', when: 'q' }])),
    (config) => config.instructions.push(example('OTHER', 0x80, Array(33).fill({ op: 'nop' }))),
    (config) => { config.memorySize = 0; },
    (config) => { config.registers = 15; },
  ];
  for (const mutate of configs) {
    const config = defaults();
    mutate(config);
    assert.throws(() => validateConfig(config));
  }
  const config = defaults();
  const copy = validateConfig(config);
  copy.instructions[0].microcode[0].op = 'halt';
  assert.equal(config.instructions[0].microcode[0].op, 'nop');
  assert.equal(defaults().instructions[0].microcode[0].op, 'nop');
});

test('decoder rejects illegal field bits and a register outside the configured files', () => {
  const config = { ...defaults(), registers: 4 };
  const { machine, program } = start('NOP\nHALT', config);
  machine.memory[program.origin + 3] = 4;
  assert.match(machine.step().message, /ненулевые биты/);
  machine.memory[program.origin] = 0x1b;
  machine.memory[program.origin + 1] = 6;
  machine.memory[program.origin + 3] = 0;
  assert.match(machine.step().message, /Регистр r6/);
});

test('32-bit multiplication retains exact low bits and distinguishes both overflow flags', () => {
  const { machine } = start(`
    LDI r0, -1
    MUL r1, r0, r0
    LDI r2, 1
    LDI r3, 30
    SHL r2, r2, r3
    LDI r3, 2
    MUL r2, r2, r3
    HALT
  `);
  machine.step();
  machine.step();
  assert.equal(machine.registers[1], 1);
  assert.deepEqual(machine.flags, { z: false, n: false, c: true, v: false });
  untilHalt(machine);
  assert.equal(machine.registers[2], 0x80000000);
  assert.deepEqual(machine.flags, { z: false, n: true, c: false, v: true });
});

test('misaligned dynamic jump or return rolls back staged stack changes', () => {
  const config = defaults();
  config.instructions.push({
    name: 'GO', opcode: 0x88, format: 'R',
    microcode: [{ op: 'push', a: 'd' }, { op: 'jump', addr: 'd' }],
  });
  for (const source of ['LDI r0, 5\nGO r0\nHALT', 'LDI r0, 5\nPUSH r0\nRET\nHALT']) {
    const { machine } = start(source, config);
    machine.step();
    if (source.includes('PUSH')) machine.step();
    const before = machine.snapshot();
    const event = machine.step();
    assert.equal(event.kind, 'fault');
    assert.match(event.message, /кратен/);
    assert.deepEqual(machine.snapshot(), { ...before, fault: event.message });
  }
});

test('last instruction can halt at the end of memory and restore its exact stopped state', () => {
  const config = { ...defaults(), memorySize: 257 };
  const { machine } = start('.org 252\nHALT', config);
  assert.equal(machine.step().kind, 'halt');
  const saved = machine.snapshot();
  assert.equal(saved.pc, 256);
  const rebuilt = new Machine(config);
  rebuilt.restore(JSON.parse(JSON.stringify(saved)));
  assert.deepEqual(rebuilt.snapshot(), saved);
  assert.equal(rebuilt.step().kind, 'halt');
  assert.deepEqual(rebuilt.snapshot(), saved);
  assert.throws(() => rebuilt.restore({ ...saved, pc: 260 }), /PC/);
  assert.deepEqual(rebuilt.snapshot(), saved);
});
