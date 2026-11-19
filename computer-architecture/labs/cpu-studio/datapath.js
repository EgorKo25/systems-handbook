(function () {
  'use strict';

  const cpu = typeof module === 'object' ? require('../logic/model.js') : window.M32Logic;
  const defaultBase = 0x2000;
  const instructions = {
    ADDI: immediate => `addi x6, x6, ${immediate}`,
    LW: immediate => `lw x6, ${immediate}(x5)`,
    SW: immediate => `sw x6, ${immediate}(x5)`,
  };

  function create(value = 42, immediate = 1, operation = 'ADDI', memoryWord = 0x11223344, wiring = {}, context = {}) {
    const { pc = cpu.ENTRY, base = defaultBase } = context;
    cpu.checkWord(pc);
    if (!Number.isInteger(base) || base < 0 || base > 0xffffffff) throw new Error('Недопустимое значение x5.');
    const { useZero = false, inhibitRegister = false, inhibitStore = false } = wiring;
    if ([useZero, inhibitRegister, inhibitStore].some(flag => typeof flag !== 'boolean')) {
      throw new Error('Параметры управляющих сигналов должны принимать значение 0 или 1.');
    }
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
    cpu.write32(memory, pc, instruction);

    if (operation !== 'ADDI') {
      if (!Number.isInteger(memoryWord) || memoryWord < 0 || memoryWord > 0xffffffff) {
        throw new Error('Начальное слово в памяти должно быть целым числом от 0 до 4294967295.');
      }
      // Initialize the chosen data word. Unaligned accesses stop at the memory stage.
      const address = cpu.u32(base + immediate);
      if (address % 4 === 0 && address <= cpu.SIZE - 4) {
        if (address === pc && memoryWord !== instruction) {
          throw new Error('Слово по адресу PC уже содержит код команды.');
        }
        cpu.write32(memory, address, memoryWord);
      }
    }
    return {
      operation, source, memory, instruction, cycle: 0, pc, base, x6: value,
      ir: null, decoded: null, operand: null, result: null, access: null, fault: null,
      wiring: { useZero, inhibitRegister, inhibitStore }, signals: null,
    };
  }

  function clock(state) {
    switch (state.cycle) {
      case 0:
        return { ...state, cycle: 1, ir: cpu.read32(state.memory, state.pc) };
      case 1: {
        const decoded = cpu.decode(state.ir);
        const store = decoded.op === 'SW';
        return {
          ...state, cycle: 2, decoded, operand: decoded.op === 'ADDI' ? state.x6 : state.base,
          signals: {
            right: state.wiring.useZero ? 0 : decoded.immediate,
            registerWrite: !store && !state.wiring.inhibitRegister,
            memoryWrite: store && !state.wiring.inhibitStore,
          },
        };
      }
      case 2:
        return { ...state, cycle: 3, result: cpu.u32(state.operand + state.signals.right) };
      case 3:
        return finish(state);
      default:
        return state;
    }
  }

  function finish(state) {
    const completed = { ...state, cycle: 4, pc: cpu.u32(state.pc + 4) };
    const { registerWrite, memoryWrite } = state.signals;
    if (state.decoded.op === 'ADDI') {
      return { ...completed, x6: registerWrite ? state.result : state.x6 };
    }
    if (state.decoded.op === 'SW' && !memoryWrite) return completed;

    const address = state.result;
    try {
      const before = cpu.read32(state.memory, address);
      if (state.decoded.op === 'LW') {
        return { ...completed, x6: registerWrite ? before : state.x6, access: { address, before, after: before } };
      }
      const memory = state.memory.slice();
      cpu.write32(memory, address, state.x6);
      return { ...completed, memory, access: { address, before, after: state.x6 } };
    } catch (error) {
      return { ...state, cycle: 4, fault: 'data:' + error.message };
    }
  }

  function fromSnapshot(hash) {
    if (!hash.startsWith('#sw?') || hash.length > 100) throw new Error('Неизвестный формат снимка.');
    const params = new URLSearchParams(hash.slice(4));
    const names = ['pc', 'word', 'x5', 'x6', 'ram'];
    if ([...params].length !== names.length || names.some(name => !/^[0-9a-f]{8}$/i.test(params.get(name) ?? ''))) {
      throw new Error('В снимке нужны 32-битные PC, код команды, x5, x6 и слово RAM.');
    }
    const [pc, word, base, value, memoryWord] = names.map(name => parseInt(params.get(name), 16));
    const decoded = cpu.decode(word);
    if (decoded.op !== 'SW' || decoded.rs1 !== 5 || decoded.rs2 !== 6) throw new Error('Снимок должен содержать SW из x6 по адресу на основе x5.');
    cpu.checkWord(cpu.u32(base + decoded.immediate));
    const context = { pc, base };
    const state = create(value, decoded.immediate, 'SW', memoryWord, {}, context);
    if (state.instruction !== word) throw new Error('Машинное слово снимка не совпало с результатом сборки.');
    return { context, state, memoryWord, offset: decoded.immediate };
  }

  if (typeof module === 'object' && module.exports) {
    module.exports = { create, clock, fromSnapshot };
    return;
  }

  const $ = id => document.getElementById(id);
  let state = create();
  let context = {};
  window.M32Appearance?.mount($('studio-theme'), $('warmth'));
  const hex = value => value === null ? '—' : '0x' + cpu.hex(value);

  function render() {
    const arithmetic = state.operation === 'ADDI';
    const store = state.operation === 'SW';
    const address = state.result;
    const hasWord = !arithmetic && address !== null && address % 4 === 0 && address <= cpu.SIZE - 4;
    const stages = ['Выборка', 'Декодирование', arithmetic ? 'Сложение' : 'Вычисление адреса', 'Завершение'];
    $('instruction-source').textContent = state.source;
    $('word').textContent = hex(state.instruction);
    $('instruction-address').textContent = hex(context.pc ?? cpu.ENTRY);
    $('base-value').textContent = hex(state.base);
    $('ir').textContent = hex(state.ir);
    $('operand-label').textContent = arithmetic ? 'x6 и константа' : 'x5 и смещение';
    $('operand').textContent = state.operand === null ? '—' : hex(state.operand) + ' + (' + state.signals.right + ')';
    $('alu-source').textContent = !state.signals ? '—' : state.wiring.useZero
      ? 'x0 → 0' : 'поле команды → ' + state.decoded.immediate;
    $('register-enable').textContent = state.signals ? Number(state.signals.registerWrite) : '—';
    $('memory-enable').textContent = state.signals ? Number(state.signals.memoryWrite) : '—';
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
    $('effect').textContent = effectText(state);
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

  function effectText(state) {
    if (state.cycle < 4) return '—';
    if (state.fault) {
      const reason = state.fault === 'data:address-misaligned'
        ? 'адрес слова должен делиться на 4' : 'слово выходит за пределы RAM';
      return 'Исключение: ' + reason + '. PC, x6 и память сохраняют прежние значения.';
    }
    if (state.operation === 'SW') {
      return state.signals.memoryWrite
        ? hex(state.access.before) + ' → ' + hex(state.access.after) + ' в RAM'
        : 'MemWrite = 0. Записи в RAM нет.';
    }
    if (!state.signals.registerWrite) {
      return state.access
        ? 'Прочитано ' + hex(state.access.before) + '. RegWrite = 0, x6 прежний.'
        : 'RegWrite = 0. Сумма в x6 не записана.';
    }
    return state.access ? hex(state.access.before) + ' → x6' : 'Результат записан в x6.';
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
      state = create(Number(value), Number(immediate), operation, Number(memoryWord), {
        useZero: $('alu-zero').checked,
        inhibitRegister: $('stop-reg-write').checked,
        inhibitStore: $('stop-mem-write').checked,
      }, context);
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
  let snapshotError;
  if (window.location.hash.startsWith('#sw')) {
    try {
      const snapshot = fromSnapshot(window.location.hash);
      ({ context, state } = snapshot);
      $('operation').value = 'SW';
      $('operation').dispatchEvent(new Event('change'));
      $('initial').value = hex(state.x6);
      $('increment').value = snapshot.offset;
      $('memory-initial').value = hex(snapshot.memoryWord);
      $('snapshot-note').hidden = false;
    } catch (error) {
      snapshotError = 'Не удалось открыть снимок из IDE. Открыт исходный пример ADDI.';
    }
  }
  render();
  if (snapshotError) $('status').textContent = snapshotError;
}());
