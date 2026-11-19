(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CPUStudio = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  const ORIGIN = 0x1000;
  const INSTRUCTION_SIZE = 4;
  const MAX_MICRO_OPS = 32;
  const MAX_QUEUED_INPUT = 65536;
  const NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;
  const FORMATS = {
    NONE: [], R: ['d'], RR: ['d', 's'], RRR: ['d', 's', 't'],
    RI: ['d', 'imm'], RM: ['d', 's', 'imm'], A: ['imm'], IO: ['d', 'imm'],
  };
  const ARITHMETIC = ['add', 'sub', 'mul', 'div', 'and', 'or', 'xor', 'shl', 'shr', 'sar'];
  const OPERATIONS = {
    mov: ['dst', 'a'], not: ['dst', 'a'], cmp: ['a', 'b'],
    load8: ['dst', 'addr'], load: ['dst', 'addr'],
    store8: ['addr', 'a'], store: ['addr', 'a'],
    jump: ['addr'], call: ['addr'], ret: [], push: ['a'], pop: ['dst'],
    in: ['dst', 'port'], out: ['port', 'a'], halt: [], nop: [],
  };
  for (const op of ARITHMETIC) OPERATIONS[op] = ['dst', 'a', 'b'];
  const CONDITIONS = ['always', 'z', 'nz', 'n', 'nn', 'c', 'nc', 'v', 'nv'];

  const rk = (op) => ({ op, dst: 'd', a: 's', b: 't' });
  const op = (name, opcode, format, ...microcode) => ({ name, opcode, format, microcode });
  const DEFAULT_INSTRUCTIONS = [
    op('NOP', 0x00, 'NONE', { op: 'nop' }),
    op('MOV', 0x01, 'RR', { op: 'mov', dst: 'd', a: 's' }),
    op('LDI', 0x02, 'RI', { op: 'mov', dst: 'd', a: 'imm' }),
    op('ADD', 0x03, 'RRR', rk('add')),
    op('ADDI', 0x04, 'RI', { op: 'add', dst: 'd', a: 'd', b: 'imm' }),
    op('SUB', 0x05, 'RRR', rk('sub')),
    op('MUL', 0x06, 'RRR', rk('mul')),
    op('DIV', 0x07, 'RRR', rk('div')),
    op('AND', 0x08, 'RRR', rk('and')),
    op('OR', 0x09, 'RRR', rk('or')),
    op('XOR', 0x0a, 'RRR', rk('xor')),
    op('NOT', 0x0b, 'RR', { op: 'not', dst: 'd', a: 's' }),
    op('SHL', 0x0c, 'RRR', rk('shl')),
    op('SHR', 0x0d, 'RRR', rk('shr')),
    op('SAR', 0x0e, 'RRR', rk('sar')),
    op('CMP', 0x0f, 'RR', { op: 'cmp', a: 'd', b: 's' }),
    op('LD', 0x10, 'RM', { op: 'load', dst: 'd', addr: 's', offset: 'imm' }),
    op('ST', 0x11, 'RM', { op: 'store', a: 'd', addr: 's', offset: 'imm' }),
    op('LDB', 0x12, 'RM', { op: 'load8', dst: 'd', addr: 's', offset: 'imm' }),
    op('STB', 0x13, 'RM', { op: 'store8', a: 'd', addr: 's', offset: 'imm' }),
    op('JMP', 0x14, 'A', { op: 'jump', addr: 'imm' }),
    op('JZ', 0x15, 'A', { op: 'jump', addr: 'imm', when: 'z' }),
    op('JNZ', 0x16, 'A', { op: 'jump', addr: 'imm', when: 'nz' }),
    op('JN', 0x17, 'A', { op: 'jump', addr: 'imm', when: 'n' }),
    op('JC', 0x18, 'A', { op: 'jump', addr: 'imm', when: 'c' }),
    op('CALL', 0x19, 'A', { op: 'call', addr: 'imm' }),
    op('RET', 0x1a, 'NONE', { op: 'ret' }),
    op('PUSH', 0x1b, 'R', { op: 'push', a: 'd' }),
    op('POP', 0x1c, 'R', { op: 'pop', dst: 'd' }),
    op('IN', 0x1d, 'IO', { op: 'in', dst: 'd', port: 'imm' }),
    op('OUT', 0x1e, 'IO', { op: 'out', a: 'd', port: 'imm' }),
    op('HALT', 0x1f, 'NONE', { op: 'halt' }),
    op('JNC', 0x20, 'A', { op: 'jump', addr: 'imm', when: 'nc' }),
    op('JV', 0x21, 'A', { op: 'jump', addr: 'imm', when: 'v' }),
  ];

  function defaults() {
    return {
      name: 'Учебный процессор',
      bits: 32,
      registers: 16,
      memorySize: 65536,
      instructions: DEFAULT_INSTRUCTIONS.map((instruction) => ({
        ...instruction, microcode: instruction.microcode.map((item) => ({ ...item })),
      })),
    };
  }

  function assert(ok, message) {
    if (!ok) throw new Error(message);
  }

  function integer(value, min, max) {
    return Number.isInteger(value) && value >= min && value <= max;
  }

  function record(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function own(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  function list(value, check) {
    return Array.isArray(value) && Object.keys(value).length === value.length && Array.from(value).every(check);
  }

  function validateConfig(config) {
    assert(record(config), 'Конфигурация процессора должна быть объектом');
    assert(typeof config.name === 'string' && config.name.trim() && config.name.length <= 100,
      'Введите название процессора длиной до 100 символов');
    assert([8, 16, 32].includes(config.bits), 'Разрядность должна быть 8, 16 или 32');
    assert([4, 8, 16].includes(config.registers), 'Число регистров должно быть 4, 8 или 16');
    assert(integer(config.memorySize, 256, 65536), 'Размер памяти должен быть от 256 до 65536 байт');
    assert(list(config.instructions, record) && integer(config.instructions.length, 1, 256),
      'Нужен список из 1–256 инструкций');
    const names = new Set();
    const opcodes = new Set();
    const instructions = config.instructions.map((instruction, index) => {
      assert(typeof instruction.name === 'string' && instruction.name.length <= 40 && NAME.test(instruction.name),
        `Недопустимое имя инструкции №${index + 1}`);
      const name = instruction.name.toUpperCase();
      const { opcode, format } = instruction;
      assert(!names.has(name), `Повтор имени инструкции ${name}`);
      assert(integer(opcode, 0, 255), `${name} — код операции должен быть от 0 до 255`);
      assert(!opcodes.has(opcode), `${name} — код операции ${opcode} уже занят`);
      assert(typeof format === 'string' && own(FORMATS, format), `${name} — неизвестный формат ${format}`);
      assert(list(instruction.microcode, record) && integer(instruction.microcode.length, 1, MAX_MICRO_OPS),
        `${name} — требуется от 1 до ${MAX_MICRO_OPS} микроопераций`);
      names.add(name);
      opcodes.add(opcode);
      const operands = FORMATS[format];
      const microcode = instruction.microcode.map((item, subindex) => {
        const prefix = `${name}, микрооперация ${subindex + 1}`;
        assert(typeof item.op === 'string' && own(OPERATIONS, item.op), `${prefix} — неизвестная операция ${item.op}`);
        const required = OPERATIONS[item.op];
        const fields = ['op', ...required, 'when'];
        if (required.includes('addr') && !['jump', 'call'].includes(item.op)) fields.push('offset');
        assert(Object.keys(item).every((key) => fields.includes(key)), `${prefix} — неизвестное поле`);
        const validateOperand = (value, field) => {
          const valid = field === 'dst'
            ? ['d', 's', 't'].includes(value) && operands.includes(value)
            : integer(value, -0x80000000, 0xffffffff) || ['pc', 'sp', ...operands].includes(value);
          assert(valid, `${prefix} — недопустимый операнд в поле ${field}`);
          return value;
        };
        const normalized = { op: item.op };
        for (const field of required) normalized[field] = validateOperand(item[field], field);
        if (own(item, 'offset')) normalized.offset = validateOperand(item.offset, 'offset');
        if (own(item, 'when')) {
          assert(CONDITIONS.includes(item.when), `${prefix} — неизвестное условие ${item.when}`);
          if (item.when !== 'always') normalized.when = item.when;
        }
        return normalized;
      });
      return { name, opcode, format, microcode };
    });
    return {
      name: config.name.trim(), bits: config.bits, registers: config.registers,
      memorySize: config.memorySize, instructions,
    };
  }

  function configKey(config) {
    const instructions = [...config.instructions].sort((left, right) => left.opcode - right.opcode);
    return JSON.stringify([config.bits, config.registers, config.memorySize, instructions]);
  }

  function signature(config) {
    return configKey(validateConfig(config));
  }

  function splitOperands(text) {
    if (!text.trim()) return [];
    const parts = [];
    let quoted = false;
    let escaped = false;
    let bracket = false;
    let start = 0;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (quoted) {
        if (escaped) escaped = false;
        else if (char === '\\') escaped = true;
        else if (char === '"') quoted = false;
      } else if (char === '"') {
        quoted = true;
      } else if (char === '[') {
        assert(!bracket, 'Вложенная квадратная скобка');
        bracket = true;
      } else if (char === ']') {
        assert(bracket, 'Лишняя закрывающая квадратная скобка');
        bracket = false;
      } else if (char === ',' && !bracket) {
        parts.push(text.slice(start, index).trim());
        start = index + 1;
      }
    }
    assert(!quoted && !bracket, 'Незакрытая строка или квадратная скобка');
    parts.push(text.slice(start).trim());
    assert(parts.every(Boolean), 'Пропущен операнд');
    return parts;
  }

  function withoutComment(text) {
    let quoted = false;
    let escaped = false;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (escaped) escaped = false;
      else if (quoted && char === '\\') escaped = true;
      else if (char === '"') quoted = !quoted;
      else if (char === ';' && !quoted) return text.slice(0, index);
    }
    return text;
  }

  function valueOf(text, symbols) {
    const expression = /^([+-]?\s*(?:0x[\da-f]+|0b[01]+|\d+)|[A-Za-z_]\w*)(?:\s*([+-])\s*(0x[\da-f]+|0b[01]+|\d+))?$/i.exec(text);
    assert(expression, `Некорректное число или метка «${text}»`);
    const atom = expression[1].replace(/\s/g, '');
    let value;
    if (NAME.test(atom)) {
      assert(symbols.has(atom), `Неизвестная метка «${atom}»`);
      value = symbols.get(atom);
    } else {
      const sign = atom.startsWith('-') ? -1 : 1;
      value = sign * Number(atom.replace(/^[+-]/, ''));
    }
    if (expression[2]) value += (expression[2] === '-' ? -1 : 1) * Number(expression[3]);
    assert(Number.isSafeInteger(value), `Число «${text}» выходит за допустимый диапазон`);
    return value;
  }

  function writeNumber(value, size) {
    const bytes = [];
    for (let index = 0; index < size; index += 1) {
      bytes.push(value & 0xff);
      value >>>= 8;
    }
    return bytes;
  }

  function encodeInstruction(info, operands, config, symbols) {
    const { format, opcode } = info;
    const fields = FORMATS[format];
    if (format === 'RM' && operands.length === 2) {
      const address = /^\[\s*(r\d+)\s*(?:([+-])\s*(.+?))?\s*\]$/i.exec(operands[1]);
      assert(address, 'Адрес памяти запишите как [rN + смещение]');
      const offset = address[3] || '0';
      const displayOffset = address[2] === '-' ? `-${offset}` : offset;
      operands = [operands[0], address[1], displayOffset];
    }
    assert(operands.length === fields.length, `${info.name} — ожидается операндов: ${fields.length}`);
    let word = opcode;
    for (let index = 0; index < fields.length; index += 1) {
      const field = fields[index];
      const text = operands[index];
      if (field === 'imm') {
        const value = valueOf(text, symbols);
        const signed = format === 'RI' || format === 'RM';
        assert(integer(value, signed ? -32768 : 0, 65535), `Операнд «${text}» не помещается в поле из 16 бит`);
        if (format === 'A') checkPc(value, config.memorySize);
        word |= (value & 0xffff) << 16;
        continue;
      }
      const match = /^r(0|[1-9]\d*)$/i.exec(text);
      assert(match && integer(Number(match[1]), 0, config.registers - 1), `Неизвестный регистр «${text}»`);
      word |= Number(match[1]) << (8 + ['d', 's', 't'].indexOf(field) * 4);
    }
    return writeNumber(word, INSTRUCTION_SIZE);
  }

  function lineError(line, fn) {
    try {
      return fn();
    } catch (error) {
      throw new Error(`Строка ${line}: ${error.message}`);
    }
  }

  function assemble(source, inputConfig = defaults()) {
    const config = validateConfig(inputConfig);
    assert(typeof source === 'string', 'Исходный текст должен быть строкой');
    const instructions = new Map(config.instructions.map((info) => [info.name, info]));
    const symbols = new Map();
    const occupied = new Uint8Array(config.memorySize);
    const rows = [];
    let address = Math.min(ORIGIN, Math.floor(config.memorySize / 8) * 4);
    let firstInstruction;
    let entryDirective;
    let origin = config.memorySize;
    let end = 0;

    function addRow(row) {
      assert(integer(address, 0, config.memorySize - row.size), 'Данные или инструкция выходят за пределы памяти');
      for (let index = address; index < address + row.size; index += 1) {
        assert(!occupied[index], `Адрес 0x${index.toString(16)} уже занят`);
      }
      occupied.fill(1, address, address + row.size);
      rows.push({ address, ...row });
      if (row.size) {
        origin = Math.min(origin, address);
        end = Math.max(end, address + row.size);
      }
      address += row.size;
    }

    for (const [index, text] of source.split(/\r?\n/).entries()) {
      const line = index + 1;
      lineError(line, () => {
        let command = withoutComment(text).trim();
        while (true) {
          const label = /^([A-Za-z_]\w*)\s*:\s*/.exec(command);
          if (!label) break;
          assert(!symbols.has(label[1]), `Повтор метки «${label[1]}»`);
          symbols.set(label[1], address);
          command = command.slice(label[0].length);
        }
        if (!command) return;
        const match = /^(\.?[A-Za-z_]\w*)(?:\s+(.*))?$/.exec(command);
        assert(match, 'Ожидалась инструкция или директива');
        const name = match[1].toUpperCase();
        const operands = splitOperands(match[2] || '');
        const baseRow = { line, text, operands, name };
        if (name === '.ORG' || name === '.ENTRY') {
          assert(operands.length === 1, `${name} — ожидается один адрес`);
          if (name === '.ORG') {
            address = valueOf(operands[0], symbols);
            assert(integer(address, 0, config.memorySize - 1), 'Адрес .org вне памяти');
          } else {
            assert(!entryDirective, 'Повтор директивы .entry');
            entryDirective = { value: operands[0], line };
          }
          return;
        }
        if (name === '.BYTE' || name === '.WORD') {
          assert(operands.length, `${name} — ожидается хотя бы одно число`);
          const width = name === '.BYTE' ? 1 : config.bits / 8;
          addRow({ ...baseRow, size: width * operands.length, width, isData: true });
          return;
        }
        if (name === '.ASCII' || name === '.ASCIIZ') {
          assert(operands.length, `${name} — ожидается хотя бы одна строка в двойных кавычках`);
          const bytes = [];
          const encoder = new TextEncoder();
          for (const operand of operands) {
            assert(operand.startsWith('"') && operand.endsWith('"'), 'Строка должна быть в двойных кавычках');
            let string;
            try {
              string = JSON.parse(operand);
            } catch {
              throw new Error(`Некорректная строка ${operand}`);
            }
            for (const byte of encoder.encode(string)) bytes.push(byte);
            if (name === '.ASCIIZ') bytes.push(0);
          }
          addRow({ ...baseRow, bytes, size: bytes.length, isData: true });
          return;
        }
        const instruction = instructions.get(name);
        assert(instruction, `Неизвестная инструкция или директива «${name}»`);
        checkPc(address, config.memorySize);
        firstInstruction ??= address;
        addRow({ ...baseRow, instruction, size: INSTRUCTION_SIZE, isData: false });
      });
    }
    assert(end > origin, 'Исходный текст не создаёт ни одного байта');
    let entry = firstInstruction ?? origin;
    if (entryDirective) {
      entry = lineError(entryDirective.line, () => {
        const value = valueOf(entryDirective.value, symbols);
        checkPc(value, config.memorySize);
        return value;
      });
    }
    checkPc(entry, config.memorySize);
    assert(entry >= origin && entry + INSTRUCTION_SIZE <= end,
      'Точка входа и её четырёхбайтовая инструкция должны находиться внутри образа');
    const bytes = Array(end - origin).fill(0);
    const listing = rows.map((row) => lineError(row.line, () => {
      let encoded = row.bytes;
      if (row.instruction) encoded = encodeInstruction(row.instruction, row.operands, config, symbols);
      if (row.width) {
        encoded = [];
        const limit = 2 ** (row.width * 8);
        for (const operand of row.operands) {
          const value = valueOf(operand, symbols);
          assert(integer(value, -limit / 2, limit - 1), `Число «${operand}» не помещается в ${row.width} байт`);
          encoded.push(...writeNumber(value, row.width));
        }
      }
      encoded.forEach((byte, index) => { bytes[row.address - origin + index] = byte; });
      return { address: row.address, line: row.line, text: row.text, bytes: encoded, isData: row.isData };
    }));
    return { bytes, origin, entry, listing, symbols: Object.fromEntries(symbols), source, configSignature: configKey(config) };
  }

  function checkPc(address, memorySize) {
    assert(integer(address, 0, memorySize - INSTRUCTION_SIZE), `Адрес инструкции ${address} находится за пределами памяти`);
    assert(address % INSTRUCTION_SIZE === 0, `Адрес инструкции ${address} должен быть кратен 4`);
  }

  function readNumber(readByte, address, size) {
    let value = 0;
    for (let index = 0; index < size; index += 1) value += readByte(address + index) * 256 ** index;
    return value;
  }

  function emptyFlags() {
    return { z: false, n: false, c: false, v: false };
  }

  function decode(word, instruction, registerCount) {
    const present = FORMATS[instruction.format];
    const raw = {
      d: (word >>> 8) & 15,
      s: (word >>> 12) & 15,
      t: (word >>> 16) & 15,
      imm: word >>> 16,
    };
    const result = {};
    for (const field of ['d', 's', 't']) {
      if (present.includes(field)) {
        assert(raw[field] < registerCount, `Регистр r${raw[field]} отсутствует в конфигурации`);
        result[field] = raw[field];
      } else if (field !== 't' || !present.includes('imm')) {
        assert(raw[field] === 0, 'В неиспользуемом поле регистра обнаружены ненулевые биты');
      }
    }
    if (present.includes('imm')) {
      const signed = instruction.format === 'RI' || instruction.format === 'RM';
      result.imm = signed && raw.imm >= 0x8000 ? raw.imm - 0x10000 : raw.imm;
    } else {
      assert((present.includes('t') ? raw.imm >>> 4 : raw.imm) === 0,
        'В неиспользуемой части инструкции обнаружены ненулевые биты');
    }
    return result;
  }

  function signedValue(value, bits) {
    return BigInt.asIntN(bits, value);
  }

  function alu(operation, left, right, bits) {
    const a = BigInt.asUintN(bits, BigInt(left));
    const b = BigInt.asUintN(bits, BigInt(right));
    const width = BigInt(bits);
    const limit = 1n << width;
    const sign = limit >> 1n;
    const signedA = signedValue(a, bits);
    const signedB = signedValue(b, bits);
    let raw;
    let signed;
    let c = false;
    switch (operation) {
      case 'add':
        raw = a + b;
        signed = signedA + signedB;
        c = raw >= limit;
        break;
      case 'sub':
      case 'cmp':
        raw = a - b;
        signed = signedA - signedB;
        c = a < b;
        break;
      case 'mul':
        raw = a * b;
        signed = signedA * signedB;
        c = raw >= limit;
        break;
      case 'div':
        assert(b !== 0n, 'Деление на ноль');
        raw = a / b;
        break;
      case 'and': raw = a & b; break;
      case 'or': raw = a | b; break;
      case 'xor': raw = a ^ b; break;
      case 'not': raw = ~a; break;
      case 'shl':
        raw = b < width ? a << b : 0n;
        if (b > 0n && b <= width) c = Boolean((a >> (width - b)) & 1n);
        break;
      case 'shr':
      case 'sar':
        {
          const shifted = operation === 'sar' ? signedA : a;
          raw = shifted >> (b < width ? b : width);
          if (b > 0n && b <= width) c = Boolean((a >> (b - 1n)) & 1n);
        }
        break;
    }
    const result = BigInt.asUintN(bits, raw);
    const flags = {
      z: result === 0n,
      n: Boolean(result & sign),
      c,
      v: signed !== undefined && (signed < -sign || signed >= sign),
    };
    return { value: Number(result), flags };
  }

  function enabled(condition, flags) {
    if (!condition) return true;
    return condition.length === 1 ? flags[condition] : !flags[condition.slice(1)];
  }

  function freezeConfig(config) {
    for (const instruction of config.instructions) {
      instruction.microcode.forEach(Object.freeze);
      Object.freeze(instruction.microcode);
      Object.freeze(instruction);
    }
    Object.freeze(config.instructions);
    return Object.freeze(config);
  }

  class Machine {
    constructor(config = defaults()) {
      this.config = freezeConfig(validateConfig(config));
      this.configSignature = configKey(this.config);
      this.instructionSet = new Map(this.config.instructions.map((instruction) => [instruction.opcode, instruction]));
      this.reset();
    }

    reset() {
      this.registers = Array(this.config.registers).fill(0);
      this.memory = new Uint8Array(this.config.memorySize);
      this.pc = 0;
      this.sp = this.memory.length;
      this.stackFloor = 0;
      this.flags = emptyFlags();
      this.inputs = {};
      this.outputs = [];
      this.halted = false;
      this.steps = 0;
      this.fault = null;
    }

    load(program) {
      assert(record(program) && program.configSignature === this.configSignature, 'Образ собран для другой конфигурации процессора');
      assert(Array.isArray(program.bytes) && program.bytes.length <= this.config.memorySize &&
        list(program.bytes, (value) => integer(value, 0, 255)), 'Образ программы должен содержать массив байтов');
      assert(integer(program.origin, 0, this.config.memorySize - program.bytes.length), 'Образ программы выходит за пределы памяти');
      checkPc(program.entry, this.config.memorySize);
      const end = program.origin + program.bytes.length;
      assert(program.entry >= program.origin && program.entry + INSTRUCTION_SIZE <= end, 'Точка входа находится вне образа');
      this.reset();
      this.memory.set(program.bytes, program.origin);
      this.pc = program.entry;
      this.stackFloor = end;
    }

    feed(port, values) {
      assert(integer(port, 0, 65535), 'Номер порта должен быть от 0 до 65535');
      if (!Array.isArray(values)) values = [values];
      const limit = 2 ** this.config.bits - 1;
      assert(values.length <= MAX_QUEUED_INPUT && list(values, (value) => integer(value, 0, limit)),
        'Значение ввода не помещается в регистр или очередь слишком длинная');
      const queue = this.inputs[port] ?? [];
      assert(queue.length + values.length <= MAX_QUEUED_INPUT, 'Очередь ввода переполнена');
      if (values.length) this.inputs[port] = queue.concat(values);
    }

    snapshot() {
      return {
        configSignature: this.configSignature,
        registers: [...this.registers], pc: this.pc, sp: this.sp, stackFloor: this.stackFloor, flags: { ...this.flags },
        memory: Array.from(this.memory),
        inputs: Object.fromEntries(Object.entries(this.inputs).map(([port, values]) => [port, [...values]])),
        outputs: this.outputs.map((value) => ({ ...value })),
        halted: this.halted, steps: this.steps, fault: this.fault,
      };
    }

    restore(snapshot) {
      const { bits, registers, memorySize } = this.config;
      const maxValue = 2 ** bits - 1;
      const validWord = (value) => integer(value, 0, maxValue);
      assert(record(snapshot) && snapshot.configSignature === this.configSignature,
        'Снимок относится к другой конфигурации процессора');
      assert(Array.isArray(snapshot.registers) && snapshot.registers.length === registers && list(snapshot.registers, validWord),
        'Некорректные регистры в снимке');
      assert(Array.isArray(snapshot.memory) && snapshot.memory.length === memorySize &&
        list(snapshot.memory, (value) => integer(value, 0, 255)), 'Некорректная память в снимке');
      const lastInstruction = Math.floor((memorySize - INSTRUCTION_SIZE) / INSTRUCTION_SIZE) * INSTRUCTION_SIZE;
      assert(integer(snapshot.pc, 0, lastInstruction + INSTRUCTION_SIZE) && snapshot.pc % INSTRUCTION_SIZE === 0,
        'Некорректный PC в снимке');
      assert(integer(snapshot.stackFloor, 0, memorySize) && integer(snapshot.sp, snapshot.stackFloor, memorySize),
        'Некорректные границы стека или SP в снимке');
      assert(record(snapshot.flags) && Object.keys(snapshot.flags).length === 4 &&
        Object.keys(emptyFlags()).every((key) => own(snapshot.flags, key) && typeof snapshot.flags[key] === 'boolean'),
        'Некорректные флаги в снимке');
      assert(record(snapshot.inputs), 'Некорректные очереди ввода в снимке');
      const inputs = {};
      for (const [port, values] of Object.entries(snapshot.inputs)) {
        assert(/^(0|[1-9]\d*)$/.test(port) && integer(Number(port), 0, 65535) &&
          Array.isArray(values) && values.length <= MAX_QUEUED_INPUT && list(values, validWord), 'Некорректная очередь порта');
        if (values.length) inputs[port] = [...values];
      }
      assert(list(snapshot.outputs, (item) => record(item) && integer(item.port, 0, 65535) && validWord(item.value)),
        'Некорректный журнал вывода в снимке');
      assert(typeof snapshot.halted === 'boolean' && integer(snapshot.steps, 0, Number.MAX_SAFE_INTEGER) &&
        (snapshot.fault === null || typeof snapshot.fault === 'string'), 'Некорректное состояние выполнения в снимке');
      Object.assign(this, {
        registers: [...snapshot.registers], pc: snapshot.pc, sp: snapshot.sp, stackFloor: snapshot.stackFloor,
        flags: { ...snapshot.flags }, memory: Uint8Array.from(snapshot.memory), inputs,
        outputs: snapshot.outputs.map(({ port, value }) => ({ port, value })),
        halted: snapshot.halted, steps: snapshot.steps, fault: snapshot.fault,
      });
    }

    inspectInstruction(address = this.pc) {
      const result = { address, bytes: [], word: null, instruction: null, operands: null, error: null };
      try {
        checkPc(address, this.memory.length);
        result.bytes = Array.from(this.memory.subarray(address, address + INSTRUCTION_SIZE));
        result.word = readNumber((index) => result.bytes[index - address], address, INSTRUCTION_SIZE);
        const opcode = result.word & 0xff;
        result.instruction = this.instructionSet.get(opcode) ?? null;
        assert(result.instruction, `Неизвестный код операции 0x${opcode.toString(16).padStart(2, '0')}`);
        result.operands = decode(result.word, result.instruction, this.config.registers);
      } catch (error) {
        result.error = error.message;
      }
      return result;
    }

    step() {
      if (this.halted) return { kind: 'halt', message: 'Процессор остановлен', pc: this.pc };
      const address = this.pc;
      try {
        checkPc(address, this.memory.length);
        assert(this.steps < Number.MAX_SAFE_INTEGER, 'Счётчик шагов переполнен');
        const { instruction, operands, error } = this.inspectInstruction(address);
        assert(error === null, error);
        const { opcode } = instruction;
        const state = {
          registers: [...this.registers], pc: address + INSTRUCTION_SIZE, sp: this.sp, flags: this.flags,
          writes: new Map(), consumed: new Map(), outputs: [], halted: false,
        };
        for (const micro of instruction.microcode) {
          if (!enabled(micro.when, state.flags)) continue;
          const waiting = this.execute(micro, operands, state, address);
          if (waiting !== undefined) {
            return { kind: 'input', message: `Ожидается ввод в порт ${waiting}`, port: waiting, pc: address, address, opcode, instruction: instruction.name };
          }
          if (state.halted) break;
        }
        for (const [index, byte] of state.writes) this.memory[index] = byte;
        for (const [port, count] of state.consumed) {
          const rest = this.inputs[port].slice(count);
          if (rest.length) this.inputs[port] = rest;
          else delete this.inputs[port];
        }
        this.outputs.push(...state.outputs);
        Object.assign(this, {
          registers: state.registers, pc: state.pc, sp: state.sp, flags: state.flags,
          halted: state.halted, steps: this.steps + 1, fault: null,
        });
        return {
          kind: state.halted ? 'halt' : 'step',
          message: state.halted ? 'Процессор остановлен' : `Выполнена инструкция ${instruction.name}`,
          pc: state.pc, address, opcode, instruction: instruction.name,
          writes: Array.from(state.writes, ([address, value]) => ({ address, value })),
          outputs: state.outputs.map((item) => ({ ...item })),
        };
      } catch (error) {
        this.fault = error.message;
        return { kind: 'fault', message: this.fault, pc: address, address };
      }
    }

    execute(micro, operands, state, address) {
      const bits = this.config.bits;
      const width = bits / 8;
      const get = (value) => {
        if (value === 'pc') return address;
        if (value === 'sp') return state.sp;
        if (value === 'imm') return operands.imm;
        if (typeof value === 'string') return state.registers[operands[value]];
        return value;
      };
      const put = (dst, value) => {
        state.registers[operands[dst]] = Number(BigInt.asUintN(bits, BigInt(value)));
      };
      const read = (addr, size) => {
        assert(integer(addr, 0, this.memory.length - size), `Чтение ${size} байт с адреса ${addr} выходит за пределы памяти`);
        return readNumber((index) => state.writes.get(index) ?? this.memory[index], addr, size);
      };
      const write = (addr, size, value) => {
        assert(integer(addr, 0, this.memory.length - size), `Запись ${size} байт с адреса ${addr} выходит за пределы памяти`);
        writeNumber(value, size).forEach((byte, index) => state.writes.set(addr + index, byte));
      };
      const push = (size, value) => {
        assert(integer(state.sp, this.stackFloor + size, this.memory.length), 'Стек переполнен или пересекается с загруженным образом');
        state.sp -= size;
        write(state.sp, size, value);
      };
      const pop = (size) => {
        assert(integer(state.sp, this.stackFloor, this.memory.length - size), 'В стеке недостаточно байтов');
        const value = read(state.sp, size);
        state.sp += size;
        return value;
      };
      const effective = () => get(micro.addr) + (micro.offset === undefined ? 0 : get(micro.offset));
      const jump = (target) => {
        checkPc(target, this.memory.length);
        state.pc = target;
      };
      const portNumber = () => {
        const port = get(micro.port);
        assert(integer(port, 0, 65535), 'Номер порта должен быть от 0 до 65535');
        return port;
      };
      switch (micro.op) {
        case 'nop': break;
        case 'mov': put(micro.dst, get(micro.a)); break;
        case 'load8': put(micro.dst, read(effective(), 1)); break;
        case 'load': put(micro.dst, read(effective(), width)); break;
        case 'store8': write(effective(), 1, get(micro.a)); break;
        case 'store': write(effective(), width, get(micro.a)); break;
        case 'jump': jump(get(micro.addr)); break;
        case 'call':
          jump(get(micro.addr));
          push(INSTRUCTION_SIZE, address + INSTRUCTION_SIZE);
          break;
        case 'ret': jump(pop(INSTRUCTION_SIZE)); break;
        case 'push': push(width, get(micro.a)); break;
        case 'pop': put(micro.dst, pop(width)); break;
        case 'halt': state.halted = true; break;
        case 'in':
          {
            const port = portNumber();
            const index = state.consumed.get(port) ?? 0;
            const value = this.inputs[port]?.[index];
            if (value === undefined) return port;
            state.consumed.set(port, index + 1);
            put(micro.dst, value);
          }
          break;
        case 'out':
          state.outputs.push({ port: portNumber(), value: Number(BigInt.asUintN(bits, BigInt(get(micro.a)))) });
          break;
        default:
          {
            const { value, flags } = alu(micro.op, get(micro.a), micro.b === undefined ? 0 : get(micro.b), bits);
            state.flags = flags;
            if (micro.dst !== undefined) put(micro.dst, value);
          }
      }
    }
  }

  return { defaults, validateConfig, signature, assemble, Machine };
});
