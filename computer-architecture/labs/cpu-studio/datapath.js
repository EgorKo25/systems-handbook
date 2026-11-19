(function () {
  'use strict';

  const cpu = typeof module === 'object' ? require('../logic/model.js') : window.M32Logic;
  const base = 0x2000;
  const instructions = {
    ADDI: immediate => `addi x6, x6, ${immediate}`,
    LW: immediate => `lw x6, ${immediate}(x5)`,
    SW: immediate => `sw x6, ${immediate}(x5)`,
  };

  function create(value = 42, immediate = 1, operation = 'ADDI', memoryWord = 0x11223344) {
    if (!Object.hasOwn(instructions, operation)) throw new Error('Выберите ADDI, LW или SW.');
    if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
      throw new Error('Начальное x6 должно быть целым числом от 0 до 4294967295.');
    }
    if (!Number.isInteger(immediate) || immediate < -2048 || immediate > 2047) {
      throw new Error('Константа или смещение должны быть целым числом от −2048 до 2047.');
    }

    const source = instructions[operation](immediate);
    const instruction = cpu.assemble(source)[0].word;
    const memory = new Uint8Array(cpu.SIZE);
    cpu.write32(memory, cpu.ENTRY, instruction);

    if (operation !== 'ADDI') {
      if (!Number.isInteger(memoryWord) || memoryWord < 0 || memoryWord > 0xffffffff) {
        throw new Error('Начальное слово в памяти должно быть целым числом от 0 до 4294967295.');
      }
      // Initialize the chosen data word. Unaligned accesses stop at the memory stage.
      const address = base + immediate;
      if (address % 4 === 0) cpu.write32(memory, address, memoryWord);
    }
    return {
      operation, source, memory, instruction, cycle: 0, pc: cpu.ENTRY, x6: value,
      ir: null, decoded: null, operand: null, result: null, access: null, fault: null,
    };
  }

  function clock(state) {
    switch (state.cycle) {
      case 0:
        return { ...state, cycle: 1, ir: cpu.read32(state.memory, state.pc) };
      case 1:
        return {
          ...state, cycle: 2, decoded: cpu.decode(state.ir),
          operand: state.operation === 'ADDI' ? state.x6 : base,
        };
      case 2:
        return { ...state, cycle: 3, result: cpu.u32(state.operand + state.decoded.immediate) };
      case 3:
        return finish(state);
      default:
        return state;
    }
  }

  function finish(state) {
    const completed = { ...state, cycle: 4, pc: cpu.u32(state.pc + 4) };
    if (state.decoded.op === 'ADDI') return { ...completed, x6: state.result };

    const address = state.result;
    try {
      const before = cpu.read32(state.memory, address);
      if (state.decoded.op === 'LW') {
        return { ...completed, x6: before, access: { address, before, after: before } };
      }
      const memory = state.memory.slice();
      cpu.write32(memory, address, state.x6);
      return { ...completed, memory, access: { address, before, after: state.x6 } };
    } catch (error) {
      return { ...state, cycle: 4, fault: 'data:' + error.message };
    }
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = { create, clock };
    return;
  }

  const $ = id => document.getElementById(id);
  let state = create();
  window.M32Appearance?.mount($('studio-theme'), $('warmth'));
  const hex = value => value === null ? '—' : '0x' + cpu.hex(value);

  function render() {
    const arithmetic = state.operation === 'ADDI';
    const store = state.operation === 'SW';
    const address = state.result;
    const hasWord = !arithmetic && address !== null && address % 4 === 0;
    const stages = ['Выборка', 'Декодирование', arithmetic ? 'Сложение' : 'Вычисление адреса', 'Завершение'];
    $('instruction-source').textContent = state.source;
    $('word').textContent = hex(state.instruction);
    $('ir').textContent = hex(state.ir);
    $('operand-label').textContent = arithmetic ? 'x6 и константа' : 'x5 и смещение';
    $('operand').textContent = state.operand === null ? '—' : hex(state.operand) + ' + (' + state.decoded.immediate + ')';
    $('alu-label').textContent = arithmetic ? 'Младшие 32 бита суммы' : 'Адрес в памяти';
    $('alu').textContent = hex(address);
    $('register').textContent = hex(state.x6);
    $('pc').textContent = hex(state.pc);
    $('base-line').hidden = arithmetic;
    $('store-line').hidden = !store;
    $('store-word').textContent = hex(state.decoded ? state.x6 : null);
    $('memory-line').hidden = arithmetic;
    $('memory-address').textContent = hex(address);
    $('memory-bytes').textContent = hasWord
      ? Array.from(state.memory.slice(address, address + 4), byte => cpu.hex(byte, 2)).join(' ')
      : '—';
    $('commit-heading').textContent = arithmetic ? '4. Запись x6 и смена PC' : store
      ? '4. Запись четырёх байтов и смена PC' : '4. Чтение слова, запись x6 и смена PC';
    $('effect').textContent = state.fault
      ? 'Исключение: адрес слова должен делиться на 4. PC, x6 и память сохраняют прежние значения.'
      : state.access
        ? store
          ? hex(state.access.before) + ' → ' + hex(state.access.after) + ' в RAM'
          : hex(state.access.before) + ' → x6'
        : state.cycle === 4 ? 'Результат записан в x6.' : '—';
    $('clock').disabled = state.cycle === stages.length;
    stages.forEach((label, index) => {
      const item = $('stage-' + index);
      if (index + 1 === state.cycle) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    $('status').textContent = state.cycle
      ? 'Такт ' + state.cycle + ' из 4. ' + (state.fault ? 'Исключение доступа.' : stages[state.cycle - 1] + '.')
      : 'Исходное состояние. Инструкция ещё в памяти.';
  }

  function reset() {
    try {
      const value = $('initial').value.trim();
      const immediate = $('increment').value.trim();
      const operation = $('operation').value;
      const memoryWord = $('memory-initial').value.trim();
      if (!value || !immediate || (operation !== 'ADDI' && !memoryWord)) {
        throw new Error('Заполните поля выбранной команды.');
      }
      state = create(Number(value), Number(immediate), operation, Number(memoryWord));
      render();
    } catch (error) {
      $('status').textContent = error.message;
    }
  }

  let previousArithmetic = true;
  const offsets = { arithmetic: '1', memory: '0' };
  $('operation').addEventListener('change', () => {
    const arithmetic = $('operation').value === 'ADDI';
    offsets[previousArithmetic ? 'arithmetic' : 'memory'] = $('increment').value;
    $('increment').value = offsets[arithmetic ? 'arithmetic' : 'memory'];
    previousArithmetic = arithmetic;
    $('increment-label').textContent = arithmetic ? 'Константа ADDI' : 'Смещение от x5';
    $('memory-settings').hidden = arithmetic;
  });
  $('datapath-settings').addEventListener('submit', event => {
    event.preventDefault();
    reset();
  });
  $('clock').addEventListener('click', () => {
    state = clock(state);
    render();
  });
  render();
}());
