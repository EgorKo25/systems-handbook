(function () {
  'use strict';

  const cpu = typeof module === 'object' ? require('../logic/model.js') : window.M32Logic;
  const defaultBase = 0x2000;
  const instructions = {
    ADDI: immediate => `addi x6, x6, ${immediate}`,
    LW: immediate => `lw x6, ${immediate}(x5)`,
    SW: immediate => `sw x6, ${immediate}(x5)`,
    BNE: immediate => `bne x7, x0, ${immediate}`,
  };

  function create(value = 42, immediate = 1, operation = 'ADDI', memoryWord = 0x11223344, wiring = {}, context = {}) {
    const { pc = cpu.ENTRY, base = defaultBase } = context;
    cpu.checkWord(pc);
    if (!Number.isInteger(base) || base < 0 || base > 0xffffffff) throw new Error('Недопустимое значение x5.');
    const { useZero = false, inhibitRegister = false, inhibitStore = false } = wiring;
    if ([useZero, inhibitRegister, inhibitStore].some(flag => typeof flag !== 'boolean')) {
      throw new Error('Параметры управляющих сигналов должны принимать значение 0 или 1.');
    }
    if (!Object.hasOwn(instructions, operation)) throw new Error('Выберите ADDI, LW, SW или BNE.');
    if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
      throw new Error('Начальное значение регистра должно быть целым числом от 0 до 4294967295.');
    }
    const branch = operation === 'BNE';
    if (!branch && (!Number.isInteger(immediate) || immediate < -2048 || immediate > 2047)) {
      throw new Error('Константа или смещение должны быть целым числом от −2048 до 2047.');
    }

    const source = instructions[operation](immediate);
    const instruction = cpu.assemble(source)[0].word;
    const memory = new Uint8Array(cpu.SIZE);
    cpu.write32(memory, pc, instruction);

    if (operation === 'LW' || operation === 'SW') {
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
      operation, source, memory, instruction, cycle: 0, pc, base, x6: branch ? 0 : value,
      x7: branch ? value : 0, branchEvent: null,
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
        if (decoded.op === 'BNE') {
          return { ...state, cycle: 2, decoded, operand: state.x7,
            signals: { right: 0, registerWrite: false, memoryWrite: false } };
        }
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
        if (state.decoded.op === 'BNE') {
          // Evaluate with the IDE's instruction rule. Commit its PC on clock 4.
          const registers = new Uint32Array(32);
          registers[7] = state.x7;
          const preview = {
            pc: state.pc, memory: state.memory, regs: registers,
            status: 'ready', attempts: 0, retired: 0, trace: [], traceDropped: 0,
          };
          return { ...state, cycle: 3, branchEvent: cpu.step(preview) };
        }
        return { ...state, cycle: 3, result: cpu.u32(state.operand + state.signals.right) };
      case 3:
        return finish(state);
      default:
        return state;
    }
  }

  function finish(state) {
    if (state.decoded.op === 'BNE') {
      const event = state.branchEvent;
      return { ...state, cycle: 4, pc: event.pcAfter, fault: event.cause ?? null };
    }
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
    const format = /^#(addi|lw|sw|bne)\?/.exec(hash);
    if (!format || hash.length > 100) throw new Error('Неизвестный формат снимка.');
    const operation = format[1].toUpperCase();
    const arithmetic = operation === 'ADDI';
    const params = new URLSearchParams(hash.slice(format[0].length));
    const branch = operation === 'BNE';
    const names = branch ? ['pc', 'word', 'x7'] : arithmetic ? ['pc', 'word', 'x6'] : ['pc', 'word', 'x6', 'x5', 'ram'];
    if ([...params].length !== names.length || names.some(name => !/^[0-9a-f]{8}$/i.test(params.get(name) ?? ''))) {
      throw new Error('Снимок содержит лишние, пропущенные или неверные значения.');
    }
    const [pc, word, value, base, memoryWord] = names.map(name => parseInt(params.get(name), 16));
    const decoded = cpu.decode(word);
    const register = operation === 'SW' ? decoded.rs2 : decoded.rd;
    const matchingRegisters = branch ? decoded.rs1 === 7 && decoded.rs2 === 0
      : decoded.rs1 === (arithmetic ? 6 : 5) && register === 6;
    if (decoded.op !== operation || !matchingRegisters) {
      throw new Error('Команда и регистры снимка не совпадают с профилем тракта.');
    }
    if (!arithmetic && !branch) cpu.checkWord(cpu.u32(base + decoded.immediate));
    const context = arithmetic || branch ? { pc } : { pc, base };
    const state = create(value, decoded.immediate, operation, memoryWord, {}, context);
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
    const branch = state.operation === 'BNE';
    const event = state.branchEvent;
    const address = state.result;
    const hasWord = !arithmetic && address !== null && address % 4 === 0 && address <= cpu.SIZE - 4;
    const stages = ['Выборка', 'Декодирование', branch ? 'Сравнение и выбор адреса' : arithmetic ? 'Сложение' : 'Вычисление адреса', 'Завершение'];
    $('instruction-source').textContent = state.source;
    $('word').textContent = hex(state.instruction);
    $('instruction-address').textContent = hex(context.pc ?? cpu.ENTRY);
    $('base-value').textContent = hex(state.base);
    $('ir').textContent = hex(state.ir);
    $('operand-label').textContent = branch ? 'x7 и x0' : arithmetic ? 'x6 и константа' : 'x5 и смещение';
    $('operand').textContent = state.operand === null ? '—' : branch ? hex(state.operand) + ' и 0' : hex(state.operand) + ' + (' + state.signals.right + ')';
    $('alu-source').textContent = !state.signals ? '—' : branch ? 'x0 → 0' : state.wiring.useZero
      ? 'x0 → 0' : 'поле команды → ' + state.decoded.immediate;
    $('register-enable').textContent = state.signals ? Number(state.signals.registerWrite) : '—';
    $('memory-enable').textContent = state.signals ? Number(state.signals.memoryWrite) : '—';
    $('alu-label').textContent = branch ? 'Результат сравнения' : arithmetic ? 'Младшие 32 бита суммы' : 'Адрес в памяти';
    $('alu').textContent = branch ? event ? event.branch.taken ? 'x7 ≠ x0' : 'x7 = x0' : '—' : hex(address);
    $('register-name').textContent = branch ? 'x7' : 'x6';
    $('register').textContent = hex(branch ? state.x7 : state.x6);
    $('branch-addresses').hidden = !event;
    $('branch-target').textContent = hex(event?.branch.target ?? null);
    $('branch-next').textContent = hex(event ? cpu.u32(event.pcBefore + 4) : null);
    $('pc').textContent = hex(state.pc);
    $('base-line').hidden = arithmetic || branch;
    $('store-line').hidden = !store;
    $('store-word').textContent = hex(state.decoded ? state.x6 : null);
    $('memory-line').hidden = arithmetic || branch;
    $('memory-address').textContent = hex(address);
    $('memory-bytes').textContent = hasWord
      ? Array.from(state.memory.slice(address, address + 4), byte => cpu.hex(byte, 2)).join(' ')
      : '—';
    $('commit-heading').textContent = branch ? '4. Запись выбранного PC' : arithmetic ? '4. Запись x6 и смена PC' : store
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
    if (state.operation === 'BNE') {
      if (state.fault) return 'Исключение: выбранная цель не кратна 4. PC, регистры и RAM прежние.';
      return (state.branchEvent.branch.taken ? 'Переход' : 'Следующая команда')
        + ': PC = ' + hex(state.pc) + '. Регистры и RAM прежние.';
    }
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
      if (!value || !immediate || ((operation === 'LW' || operation === 'SW') && !memoryWord)) {
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

  let previousKind = 'arithmetic';
  const offsets = { arithmetic: '1', memory: '0', branch: '-4' };
  $('operation').addEventListener('change', () => {
    const operation = $('operation').value;
    const kind = operation === 'BNE' ? 'branch' : operation === 'ADDI' ? 'arithmetic' : 'memory';
    offsets[previousKind] = $('increment').value;
    $('increment').value = offsets[kind];
    previousKind = kind;
    $('increment-label').textContent = {
      arithmetic: 'Константа ADDI', memory: 'Смещение от x5', branch: 'Смещение от PC',
    }[kind];
    $('initial-label').textContent = kind === 'branch' ? 'Начальное x7' : 'Начальное x6';
    $('memory-settings').hidden = kind !== 'memory';
    $('wiring-settings').hidden = kind === 'branch';
    $('wiring-settings').disabled = kind === 'branch';
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
  if (/^#(?:addi|lw|sw|bne)/.test(window.location.hash)) {
    try {
      const snapshot = fromSnapshot(window.location.hash);
      ({ context, state } = snapshot);
      $('operation').value = state.operation;
      $('operation').dispatchEvent(new Event('change'));
      const branch = state.operation === 'BNE';
      $('initial').value = hex(branch ? state.x7 : state.x6);
      $('increment').value = snapshot.offset;
      if (state.operation === 'LW' || state.operation === 'SW') {
        $('memory-initial').value = hex(snapshot.memoryWord);
      }
      $(branch ? 'snapshot-bne-note' : state.operation === 'ADDI' ? 'snapshot-addi-note' : 'snapshot-note').hidden = false;
    } catch (error) {
      snapshotError = 'Не удалось открыть снимок из IDE. Открыт исходный пример ADDI.';
    }
  }
  render();
  if (snapshotError) $('status').textContent = snapshotError;
}());
