(() => {
  'use strict';

  const cpu = window.CPUStudio;
  const $ = id => document.getElementById(id);
  const sample = {
    counter: {
      source: '; 42 → 43\n.org 0x20\n.entry start\nstart:\n    LDI R0, 42\n    LDI R1, 0x80\n    ADDI R0, 1\n    ST R0, [R1]\n    HALT\n',
      tip: 'Перед ST сравните R0 и байт по адресу 0x0080. После ST в памяти появится 2B.'
    },
    loop: {
      source: '; Сумма 3 + 2 + 1\n.org 0x20\n.entry start\nstart:\n    LDI R0, 0\n    LDI R1, 3\n    LDI R2, 0\nagain:\n    CALL accumulate\n    ADDI R1, -1\n    CMP R1, R2\n    JNZ again\n    HALT\naccumulate:\n    ADD R0, R0, R1\n    RET\n',
      tip: 'CALL сохраняет адрес возврата в стеке. Сравните SP до CALL, внутри подпрограммы и после RET. При HALT в R0 будет 6.'
    },
    echo: {
      source: '; Вход из порта 1, выход в порт 2\n.org 0x20\n.entry start\nstart:\n    IN R0, 1\n    OUT R0, 2\n    JMP start\n',
      tip: 'Добавьте 65, 66 и 67 в порт 1 и запустите. После трёх записей в порт 2 выполнение снова будет ждать ввод.'
    }
  };
  const runLimit = 100000;
  const batchSize = 192;
  const pageSize = 64;
  const flagNames = {
    z: 'Нулевой результат', n: 'Отрицательный результат', c: 'Перенос', v: 'Знаковое переполнение'
  };

  let config;
  let program;
  let machine;
  let breakpoints = new Set();
  let lastValues = null;
  let lastWrites = new Set();
  let lastRegisterAdd = null;
  let memoryStart = 0;
  let hasResidentByte = new Set();
  let running = false;
  let runToken = 0;
  let stoppedAt = null;
  let listingByAddress = new Map();
  let breakpointButtons = new Map();
  let executableLines = new Set();
  let sourceButtons = [];
  let memoryInputs = [];
  let memoryLabels = [];
  let displayedOutputLength = -1;
  let renderedAddress = null;
  let currentSourceButton = null;
  let example = null;

  function node(tag, value = '', className = '') {
    const part = document.createElement(tag);
    part.textContent = value;
    if (className) part.className = className;
    return part;
  }

  function hex(value, length) {
    return Number(value).toString(16).toUpperCase().padStart(length, '0');
  }

  const address = value => '0x' + hex(value, 4);
  const numberFormat = new Intl.NumberFormat('ru-RU');

  function message(value, kind = '') {
    $('status').textContent = value;
    $('status').dataset.kind = kind;
  }

  function report(error, operation) {
    message(operation + '. ' + (error?.message || String(error)), 'error');
  }

  function readInteger(text, maximum, label) {
    const value = text.trim();
    if (!/^(?:0x[\da-f]+|\d+)$/i.test(value)) throw new Error(label + ' должен быть целым числом.');
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed) || parsed > maximum) {
      throw new Error(label + ' вне диапазона 0–' + maximum + '.');
    }
    return parsed;
  }

  function instructionRows(nextProgram = program) {
    return nextProgram.listing.filter(row => row.bytes.length && !row.isData);
  }

  function installedSource() {
    return $('source').value === program.source;
  }

  function architectureDraft() {
    return {
      name: $('cpu-name').value,
      bits: Number($('cpu-bits').value),
      registers: Number($('cpu-registers').value),
      memorySize: Number($('cpu-memory').value),
      instructions: JSON.parse($('instruction-json').value)
    };
  }

  function architectureDirty() {
    try {
      return JSON.stringify(cpu.validateConfig(architectureDraft())) !== JSON.stringify(config);
    } catch {
      return true;
    }
  }

  function renderDraft() {
    const notices = [];
    if (!installedSource()) notices.push('Исходник изменён. Исполняется последняя успешная сборка.');
    if (architectureDirty()) notices.push('Настройки архитектуры ждут применения.');
    $('draft-state').textContent = notices.join(' ');
    $('draft-state').hidden = !notices.length;
  }

  function renderConfig() {
    $('architecture-name').textContent = config.name;
    $('diagram-registers').textContent = config.registers + ' × ' + config.bits + ' бит';
    $('diagram-alu').textContent = config.bits + ' бит · Z N C V';
    $('diagram-decoder').textContent = config.instructions.length + ' кодов';
    $('diagram-memory').textContent = numberFormat.format(config.memorySize) + ' байт';
    $('cpu-name').value = config.name;
    $('cpu-bits').value = config.bits;
    $('cpu-registers').value = config.registers;
    $('cpu-memory').value = config.memorySize;
    $('instruction-json').value = '[\n' + config.instructions.map(ins => '  ' + JSON.stringify(ins)).join(',\n') + '\n]';
  }

  function setSource(source, sampleName = null) {
    $('source').value = source;
    example = sampleName;
    $('example-tip').textContent = example ? sample[example].tip : '';
    renderSource();
  }

  function highlightSource(text) {
    const fragment = document.createDocumentFragment();
    const tokens = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|;[^\n]*|\b[A-Za-z_][\w.]*:(?!\w)|\.[a-z]+|\b[A-Za-z_][\w]*\b/gi;
    const commands = new Set(config.instructions.map(ins => ins.name));
    let end = 0;
    for (const match of text.matchAll(tokens)) {
      fragment.append(text.slice(end, match.index));
      const token = match[0];
      if (token.startsWith(';')) fragment.append(node('span', token, 'comment'));
      else if (token.endsWith(':')) fragment.append(node('span', token, 'definition'));
      else if (token.startsWith('.') || commands.has(token.toUpperCase())) fragment.append(node('span', token, 'keyword'));
      else fragment.append(token);
      end = match.index + token.length;
    }
    fragment.append(text.slice(end) + '\n');
    $('highlight').replaceChildren(fragment);
  }

  function syncEditor() {
    $('line-numbers').parentElement.scrollTop = $('source').scrollTop;
    $('highlight').scrollTop = $('source').scrollTop;
    $('highlight').scrollLeft = $('source').scrollLeft;
  }

  function renderSource() {
    const source = $('source');
    highlightSource(source.value);
    const count = source.value.split('\n').length;
    const lines = document.createDocumentFragment();
    sourceButtons = [];
    for (let line = 1; line <= count; line++) {
      const button = makeBreakpointButton(line, 'line-number');
      button.disabled = !installedSource() || !executableLines.has(line);
      sourceButtons.push(button);
      lines.append(button);
    }
    $('line-numbers').replaceChildren(lines);
    syncEditor();
    renderBreakpoints();
    renderDraft();
  }

  function makeBreakpointButton(line, className) {
    const button = node('button', String(line), className);
    button.type = 'button';
    button.dataset.line = line;
    button.setAttribute('aria-label', 'Точка останова, строка ' + line);
    return button;
  }

  function renderBreakpoints() {
    for (const [line, button] of breakpointButtons) {
      const active = breakpoints.has(line);
      button.setAttribute('aria-pressed', String(active));
      button.textContent = (active ? '● ' : '') + line;
    }
    const currentSource = installedSource();
    sourceButtons.forEach((button, index) => {
      const line = index + 1;
      const active = currentSource && breakpoints.has(line);
      button.setAttribute('aria-pressed', String(active));
      button.textContent = (active ? '● ' : '') + line;
    });
    renderSourcePC();
  }

  function renderSourcePC() {
    const line = listingByAddress.get(machine.pc)?.line;
    const next = installedSource() && !machine.halted ? sourceButtons[line - 1] : null;
    if (next === currentSourceButton) return;
    currentSourceButton?.removeAttribute('aria-current');
    next?.setAttribute('aria-current', 'true');
    currentSourceButton = next;
  }

  function renderListing() {
    listingByAddress = new Map();
    breakpointButtons = new Map();
    executableLines = new Set();
    hasResidentByte = new Set();
    renderedAddress = null;
    const fragment = document.createDocumentFragment();
    program.listing.forEach(row => {
      const tr = node('tr');
      const lineCell = node('td');
      if (!row.isData && row.bytes.length) {
        const stop = makeBreakpointButton(row.line, 'listing-breakpoint');
        lineCell.append(stop);
        breakpointButtons.set(row.line, stop);
        listingByAddress.set(row.address, { line: row.line, element: tr, text: row.text });
        executableLines.add(row.line);
      } else {
        tr.className = 'data-row';
        lineCell.textContent = row.line;
      }
      const next = node('span');
      next.className = 'pc-arrow';
      next.setAttribute('aria-hidden', 'true');
      const addressCell = node('td', address(row.address));
      addressCell.prepend(next);
      tr.append(lineCell, addressCell, node('td', row.bytes.map(value => hex(value, 2)).join(' ')), node('td', row.text));
      fragment.append(tr);
      row.bytes.forEach((_, offset) => hasResidentByte.add(row.address + offset));
    });
    $('listing').replaceChildren(fragment);
    const labels = Object.entries(program.symbols).sort(([a], [b]) => a.localeCompare(b, 'ru'));
    $('label-jump').replaceChildren(node('option', 'Выбрать…'));
    $('label-jump').options[0].value = '';
    for (const [label, location] of labels) {
      const option = node('option', label + ' · ' + address(location));
      option.value = label;
      $('label-jump').append(option);
    }
    $('label-jump').disabled = !labels.length;
  }

  function jumpToLabel(label, uses = false) {
    const key = Object.hasOwn(program.symbols, label) ? label : null;
    if (!key) return;
    const location = program.symbols[key];
    const listing = listingByAddress.get(location);
    if (listing) alignListing(listing.element);
    if (!installedSource()) {
      message('Метка ' + key + ' в последней сборке находится по адресу ' + address(location) + '.');
      return;
    }
    const source = $('source');
    const definition = new RegExp('^\\s*(?:[A-Za-z_]\\w*\\s*:\\s*)*' + key + '\\s*:');
    let offset = 0;
    for (const [index, line] of source.value.split('\n').entries()) {
      if (definition.test(line)) {
        source.focus({ preventScroll: true });
        source.setSelectionRange(offset, offset + line.length);
        source.scrollTop = Math.max(0, (index - 2) * 25);
        syncEditor();
        break;
      }
      offset += line.length + 1;
    }
    if (uses) {
      const matches = program.listing.filter(row => {
        const operands = row.text
          .replace(/^\s*(?:[A-Za-z_]\w*\s*:\s*)*/, '')
          .replace(/^\.?[A-Za-z_]\w*/, '')
          .replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, '')
          .split(';')[0];
        return operands.split(/[^\w.]+/).includes(key);
      });
      if (matches.length) message('Ссылки на ' + key + ' в строках ' + matches.map(row => row.line).join(', ') + '.');
    }
  }

  function alignListing(row) {
    const viewport = $('listing-scroll');
    const rowTop = viewport.scrollTop + row.getBoundingClientRect().top - viewport.getBoundingClientRect().top;
    const min = viewport.scrollTop + viewport.querySelector('thead').offsetHeight;
    const max = viewport.scrollTop + viewport.clientHeight;
    if (rowTop < min || rowTop + row.offsetHeight > max) {
      viewport.scrollTop = Math.max(0, rowTop - viewport.clientHeight / 2);
    }
  }

  function renderPC(follow) {
    const pc = machine.halted ? null : machine.pc;
    if (renderedAddress !== pc) {
      const old = listingByAddress.get(renderedAddress)?.element;
      if (old) {
        old.removeAttribute('aria-current');
        old.querySelector('.pc-arrow').textContent = '';
      }
      const current = listingByAddress.get(pc)?.element;
      if (current) {
        current.setAttribute('aria-current', 'true');
        current.querySelector('.pc-arrow').textContent = '▶ ';
        if (follow) alignListing(current);
      }
      renderedAddress = pc;
    }
    renderSourcePC();
  }

  function renderPCWord() {
    const { address: pc, bytes, word, instruction, operands, error } = machine.inspectInstruction();
    const formatBytes = values => values.length ? values.map(value => hex(value, 2)).join(' ') : '—';
    const listing = bytes.length && bytes.every((_, i) => hasResidentByte.has(pc + i))
      ? program.bytes.slice(pc - program.origin, pc - program.origin + bytes.length) : [];
    $('pc-word-address').textContent = address(pc);
    $('pc-word-listing').textContent = formatBytes(listing);
    $('pc-word-memory').textContent = formatBytes(bytes);
    $('pc-word-value').textContent = word === null ? '—' : '0x' + hex(word, 8);
    $('pc-word-changed').hidden = !listing.some((byte, index) => byte !== bytes[index]);
    if (error !== null) {
      $('pc-word-decoded').textContent = 'Ошибка декодирования. ' + error;
    } else {
      const fields = Object.entries(operands).map(([name, value]) =>
        name === 'imm' ? 'imm = ' + value : name + ' = r' + value);
      $('pc-word-decoded').textContent = instruction.name + (fields.length ? ' · ' + fields.join(' · ') : '');
    }
    $('pc-word-open-memory').disabled = bytes.length === 0;
  }

  function renderRegisterAdd() {
    $('register-add-step').hidden = lastRegisterAdd === null;
    if (!lastRegisterAdd) return;
    const { instruction, pcBefore, pcAfter, bytes, register, inputs, constant, after } = lastRegisterAdd;
    const name = 'R' + register;
    const registers = [name];
    if (inputs.length === 2) registers.push(...inputs.map(input => 'R' + input.register));
    $('register-add-decode').textContent =
      address(pcBefore) + ' · ' + bytes.map(byte => hex(byte, 2)).join(' ') + ' · ' + instruction + ' ' + registers.join(', ');
    const inputValues = inputs.map(input => 'R' + input.register + ' = ' + input.value);
    if (constant !== undefined) inputValues.push('константа ' + constant);
    $('register-add-alu').textContent = inputValues.join(' · ') + ' · результат ' + after;
    $('register-add-write').textContent =
      name + ' ← ' + after + ' · PC ← ' + address(pcAfter);
  }

  function renderRegisters() {
    const regs = Array.from(machine.registers, (value, index) => ['R' + index, value, config.bits / 4]);
    regs.push(['PC', machine.pc, 4], ['SP', machine.sp, 4]);
    const boxes = regs.map(([label, value, width], index) => {
      const before = lastValues?.registers[index];
      const box = node('div', '', before !== undefined && value !== before ? 'changed' : '');
      const caption = node('dt', label);
      if (label === 'PC') caption.title = 'Адрес следующей команды';
      if (label === 'SP') caption.title = 'Указатель стека';
      const digits = node('dd', hex(value, width));
      digits.title = value + ' в десятичной записи';
      box.append(caption, digits);
      return box;
    });
    $('registers').replaceChildren(...boxes);
    const flags = Object.entries(flagNames).map(([key, label]) => {
      const value = Boolean(machine.flags[key]);
      const box = node('div', '', lastValues && value !== Boolean(lastValues.flags[key]) ? 'changed' : '');
      box.dataset.active = String(value);
      box.title = label;
      box.append(node('dt', key.toUpperCase()), node('dd', value ? '1' : '0'));
      return box;
    });
    $('flags').replaceChildren(...flags);
    $('steps').textContent = numberFormat.format(machine.steps) + ' · выполнено';
  }

  function createMemoryGrid() {
    const grid = document.createDocumentFragment();
    grid.append(node('span', 'Адрес'));
    for (let col = 0; col < 8; col++) grid.append(node('span', '+' + col));
    memoryInputs = [];
    memoryLabels = [];
    for (let row = 0; row < pageSize / 8; row++) {
      const label = node('span');
      memoryLabels.push(label);
      grid.append(label);
      for (let col = 0; col < 8; col++) {
        const field = node('input');
        field.autocomplete = 'off';
        field.spellcheck = false;
        field.maxLength = 4;
        field.addEventListener('blur', () => updateMemoryField(field, Number(field.dataset.offset)));
        memoryInputs.push(field);
        grid.append(field);
      }
    }
    $('memory-grid').replaceChildren(grid);
  }

  function updateMemoryField(field, offset) {
    const addr = memoryStart + offset;
    field.dataset.offset = offset;
    field.disabled = running || addr >= machine.memory.length;
    field.classList.toggle('resident', hasResidentByte.has(addr));
    field.classList.toggle('written-byte', lastWrites.has(addr));
    field.classList.toggle('next-byte', !machine.halted && machine.pc === addr);
    field.value = addr < machine.memory.length ? hex(machine.memory[addr], 2) : '—';
    field.setAttribute('aria-label', 'Байт по адресу ' + address(addr));
    field.removeAttribute('aria-invalid');
  }

  function renderMemory(force) {
    const end = Math.min(memoryStart + pageSize, machine.memory.length) - 1;
    $('memory-range').textContent = address(memoryStart) + '–' + address(end);
    $('memory-prev').disabled = memoryStart === 0;
    $('memory-next').disabled = end >= machine.memory.length - 1;
    memoryLabels.forEach((label, row) => {
      label.textContent = hex(memoryStart + 8 * row, 4);
    });
    memoryInputs.forEach((field, offset) => {
      if (force || running || field !== document.activeElement) updateMemoryField(field, offset);
    });
  }

  function showMemory(firstAddress) {
    memoryStart = Math.floor(firstAddress / pageSize) * pageSize;
    $('memory-address').value = address(firstAddress);
    renderMemory(true);
  }

  function renderPorts() {
    const portQueues = Object.entries(machine.inputs).filter(([, queue]) => queue.length);
    $('input-queue').textContent = portQueues.length ? portQueues.map(([port, queue]) => {
      const values = queue.slice(0, 10).join(', ');
      return 'Порт ' + port + ' · ' + values + (queue.length > 10 ? ' … (' + queue.length + ')' : '');
    }).join(' · ') : 'Очередь пуста.';
    if (displayedOutputLength !== machine.outputs.length) {
      const displayed = machine.outputs.slice(-200);
      $('output-count').textContent = displayed.length < machine.outputs.length ? 'Последние 200 из ' + machine.outputs.length + ' значений.' : '';
      const display = $('port-output');
      display.textContent = displayed.length ? displayed.map(({ port, value }) => {
        const character = value >= 32 && value <= 126 ? ' · ' + JSON.stringify(String.fromCodePoint(value)) : '';
        return 'Порт ' + port + ' → ' + value + ' / 0x' + hex(value, config.bits / 4) + character;
      }).join('\n') : 'Пока пусто.';
      display.scrollTop = display.scrollHeight;
      displayedOutputLength = machine.outputs.length;
    }
  }

  function renderControls() {
    const finished = machine.halted;
    $('step').disabled = running || finished;
    $('run').disabled = running || finished;
    $('pause').disabled = !running;
    $('feed').disabled = running;
  }

  function renderMachine(follow = false) {
    renderPC(follow);
    renderPCWord();
    renderRegisterAdd();
    renderRegisters();
    renderMemory(false);
    renderPorts();
    renderControls();
  }

  function install(nextConfig, nextProgram, nextMachine, nextBreakpoints, newSource, newExample = null) {
    const changedConfig = config !== nextConfig;
    stopRun();
    config = nextConfig;
    program = nextProgram;
    machine = nextMachine;
    breakpoints = nextBreakpoints;
    lastValues = null;
    lastWrites = new Set();
    lastRegisterAdd = null;
    stoppedAt = null;
    displayedOutputLength = -1;
    if (changedConfig) renderConfig();
    renderListing();
    setSource(newSource, newExample);
    showMemory(Math.min(memoryStart, machine.memory.length - 1));
    renderMachine(true);
  }

  function assemble(nextConfig, text, sampleName = example) {
    const next = cpu.assemble(text, nextConfig);
    const candidate = new cpu.Machine(nextConfig);
    candidate.load(next);
    const valid = new Set(instructionRows(next).map(row => row.line));
    install(nextConfig, next, candidate, new Set([...breakpoints].filter(line => valid.has(line))), text, sampleName);
    message('Собрано ' + numberFormat.format(next.bytes.length) + ' байт. Точка входа ' + address(next.entry) + '.');
  }

  function buildSource() {
    try {
      assemble(config, $('source').value);
    } catch (error) {
      report(error, 'Ошибка сборки');
    }
  }

  function stopRun() {
    running = false;
    runToken++;
  }

  function execute() {
    lastValues = {
      registers: [...machine.registers, machine.pc, machine.sp],
      flags: { ...machine.flags }
    };
    let result;
    try {
      result = machine.step();
    } catch (error) {
      result = { kind: 'fault', message: error.message };
    }
    lastWrites = new Set((result.writes || []).map(write => write.address));
    return result;
  }

  function stepOnce() {
    const { instruction, operands, bytes } = machine.inspectInstruction();
    const result = execute();
    lastRegisterAdd = null;
    if (result.kind !== 'step' || instruction?.microcode.length !== 1) return result;

    const [micro] = instruction.microcode;
    if (micro.op !== 'add' || micro.dst !== 'd' || micro.when !== undefined) return result;

    let sources;
    let constant;
    if (instruction.format === 'RRR' && micro.a === 's' && micro.b === 't') {
      sources = [operands.s, operands.t];
    } else if (instruction.format === 'R' && micro.a === 'd' && typeof micro.b === 'number') {
      sources = [operands.d];
      constant = micro.b;
    } else {
      return result;
    }
    const register = operands.d;
    const inputs = sources.map(source => ({ register: source, value: lastValues.registers[source] }));
    lastRegisterAdd = {
      instruction: result.instruction, pcBefore: result.address, pcAfter: result.pc,
      bytes, register, inputs, constant, after: machine.registers[register],
    };
    return result;
  }

  function reportStep(result) {
    if (result.kind !== 'step') {
      message(result.message || 'Выполнение остановлено.', result.kind === 'fault' ? 'error' : '');
      return;
    }
    message('Выполнена ' + result.instruction + ' по адресу ' + address(result.address) + '. PC = ' + address(machine.pc) + '.');
  }

  function run() {
    const skipFirst = stoppedAt === machine.pc;
    const startSteps = machine.steps;
    stoppedAt = null;
    running = true;
    lastRegisterAdd = null;
    renderRegisterAdd();
    const token = ++runToken;
    renderControls();
    renderMemory(false);
    message('Программа выполняется…');

    function tick() {
      if (token !== runToken) return;
      for (let count = 0; count < batchSize; count++) {
        const line = listingByAddress.get(machine.pc)?.line;
        if (breakpoints.has(line) && !(skipFirst && machine.steps === startSteps)) {
          stoppedAt = machine.pc;
          stopRun();
          renderMachine(true);
          message('Точка останова. Строка ' + line + ', адрес ' + address(machine.pc) + '.');
          return;
        }
        const result = execute();
        if (result.kind !== 'step' || machine.steps - startSteps >= runLimit) {
          if (result.kind === 'input' && skipFirst && machine.steps === startSteps && breakpoints.has(line)) {
            stoppedAt = machine.pc;
          }
          stopRun();
          renderMachine(true);
          if (result.kind === 'step') message('Достигнут предел запуска · ' + numberFormat.format(runLimit) + ' команд.');
          else reportStep(result);
          return;
        }
      }
      renderMachine(true);
      setTimeout(tick, 0);
    }

    setTimeout(tick, 0);
  }

  function saveProject() {
    const project = {
      format: 'cpustudio-project',
      version: 1,
      config,
      source: $('source').value,
      assembledSource: program.source,
      architectureDraft: {
        name: $('cpu-name').value, bits: $('cpu-bits').value, registers: $('cpu-registers').value,
        memorySize: $('cpu-memory').value, instructions: $('instruction-json').value
      },
      breakpoints: [...breakpoints],
      stoppedAt,
      snapshot: machine.snapshot()
    };
    const blob = new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = node('a');
    anchor.href = url;
    anchor.download = 'cpustudio-project.json';
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    message('Проект подготовлен к скачиванию.');
  }

  function loadProject(raw) {
    const project = JSON.parse(raw);
    if (!project || project.format !== 'cpustudio-project' || project.version !== 1) {
      throw new Error('Ожидается проект конструктора процессора версии 1.');
    }
    if (typeof project.source !== 'string' || typeof project.assembledSource !== 'string' || !Array.isArray(project.breakpoints)) {
      throw new Error('В проекте должны быть исходный текст, текст сборки и список точек останова.');
    }
    const draft = project.architectureDraft;
    if (draft !== undefined && (!draft || !['name', 'bits', 'registers', 'memorySize', 'instructions'].every(key => typeof draft[key] === 'string'))) {
      throw new Error('Черновик архитектуры повреждён.');
    }
    const nextConfig = cpu.validateConfig(project.config);
    const nextProgram = cpu.assemble(project.assembledSource.replace(/\r\n?/g, '\n'), nextConfig);
    const valid = new Set(instructionRows(nextProgram).map(row => row.line));
    const stops = new Set(project.breakpoints);
    if (stops.size !== project.breakpoints.length || [...stops].some(line => !valid.has(line))) {
      throw new Error('В проекте есть некорректная точка останова.');
    }
    const nextMachine = new cpu.Machine(nextConfig);
    nextMachine.load(nextProgram);
    nextMachine.restore(project.snapshot);
    const pausedAddress = project.stoppedAt ?? null;
    if (pausedAddress !== null && (pausedAddress !== nextMachine.pc || !instructionRows(nextProgram).some(row => row.address === pausedAddress && stops.has(row.line)))) {
      throw new Error('Адрес остановки не совпадает с точкой останова.');
    }
    install(nextConfig, nextProgram, nextMachine, stops, project.source.replace(/\r\n?/g, '\n'));
    stoppedAt = pausedAddress;
    if (draft) {
      $('cpu-name').value = draft.name;
      $('cpu-bits').value = draft.bits;
      $('cpu-registers').value = draft.registers;
      $('cpu-memory').value = draft.memorySize;
      $('instruction-json').value = draft.instructions;
      renderDraft();
    }
    message('Проект открыт. Состояние процессора восстановлено.');
  }

  function wire() {
    $('assemble').addEventListener('click', buildSource);
    $('step').addEventListener('click', () => {
      stoppedAt = null;
      const result = stepOnce();
      renderMachine(true);
      reportStep(result);
    });
    $('run').addEventListener('click', run);
    $('pause').addEventListener('click', () => {
      stopRun();
      renderMachine();
      message('Пауза. PC = ' + address(machine.pc) + '.');
    });
    $('reset').addEventListener('click', () => {
      const next = new cpu.Machine(config);
      next.load(program);
      const pendingExample = example;
      install(config, program, next, breakpoints, $('source').value, pendingExample);
      message('Последняя сборка снова загружена. Регистры, память и очереди сброшены.');
    });
    $('use-example').addEventListener('click', () => {
      const id = $('examples').value;
      const text = sample[id].source;
      if (!installedSource() && $('source').value !== text && !window.confirm('Заменить текущий черновик текстом примера?')) return;
      try {
        const compiled = cpu.assemble(text, config);
        const candidate = new cpu.Machine(config);
        candidate.load(compiled);
        install(config, compiled, candidate, new Set(), text, id);
        if (id === 'counter') showMemory(0x80);
        message('Пример собран. Точка входа ' + address(compiled.entry) + '.');
      } catch (error) {
        setSource(text, id);
        report(error, 'Пример открыт в редакторе, но текущая архитектура не принимает его команды');
      }
    });

    $('source').addEventListener('input', () => {
      example = null;
      $('example-tip').textContent = '';
      renderSource();
    });
    $('source').addEventListener('scroll', syncEditor);
    $('source').addEventListener('click', event => {
      if (!event.ctrlKey && !event.metaKey) return;
      const source = $('source');
      const before = source.value.slice(0, source.selectionStart).match(/[\w.]+$/)?.[0] || '';
      const after = source.value.slice(source.selectionStart).match(/^[\w.]+/)?.[0] || '';
      if (before || after) jumpToLabel(before + after, true);
    });
    document.addEventListener('keydown', event => {
      if (!event.defaultPrevented && (event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        buildSource();
      }
    });
    $('label-jump').addEventListener('change', event => {
      if (event.target.value) jumpToLabel(event.target.value);
    });
    const toggleBreakpoint = event => {
      const button = event.target.closest('button[data-line]');
      if (!button || button.disabled) return;
      const line = Number(button.dataset.line);
      if (breakpoints.has(line)) {
        breakpoints.delete(line);
        if (listingByAddress.get(stoppedAt)?.line === line) stoppedAt = null;
        message('Точка останова снята со строки ' + line + '.');
      } else {
        breakpoints.add(line);
        message('Точка останова на строке ' + line + '.');
      }
      renderBreakpoints();
    };
    $('line-numbers').addEventListener('click', toggleBreakpoint);
    $('listing').addEventListener('click', toggleBreakpoint);

    $('memory-form').addEventListener('submit', event => {
      event.preventDefault();
      try {
        showMemory(readInteger($('memory-address').value, machine.memory.length - 1, 'Адрес'));
      } catch (error) {
        report(error, 'Ошибка адреса');
      }
    });
    $('memory-prev').addEventListener('click', () => showMemory(memoryStart - pageSize));
    $('pc-word-open-memory').addEventListener('click', () => {
      showMemory(machine.pc);
      $('memory-address').focus();
    });
    $('memory-next').addEventListener('click', () => showMemory(memoryStart + pageSize));
    $('memory-grid').addEventListener('keydown', event => {
      if (event.target.tagName !== 'INPUT' || running || event.key !== 'Enter') return;
      event.preventDefault();
      const field = event.target;
      const addr = memoryStart + Number(field.dataset.offset);
      const text = field.value.trim();
      if (!/^(?:0x)?[\da-f]{1,2}$/i.test(text) || addr >= machine.memory.length) {
        field.setAttribute('aria-invalid', 'true');
        message('Введите один байт от 00 до FF.', 'error');
        return;
      }
      const value = Number.parseInt(text, 16);
      machine.memory[addr] = value;
      updateMemoryField(field, Number(field.dataset.offset));
      renderPCWord();
      message('По адресу ' + address(addr) + ' записано ' + hex(value, 2) + '.');
    });

    $('port-form').addEventListener('submit', event => {
      event.preventDefault();
      if (running) return;
      try {
        const port = readInteger($('input-port').value, 65535, 'Порт');
        const entries = $('input-values').value.trim().split(/\s*,\s*|\s+/);
        const values = entries.map(value => readInteger(value, 2 ** config.bits - 1, 'Значение'));
        machine.feed(port, values);
        $('input-values').value = '';
        renderPorts();
        message('Во входную очередь порта ' + port + ' добавлено значений · ' + values.length + '.');
      } catch (error) {
        report(error, 'Ошибка ввода');
      }
    });

    $('architecture-form').addEventListener('input', renderDraft);
    $('architecture-form').addEventListener('submit', event => {
      event.preventDefault();
      try {
        assemble(cpu.validateConfig(architectureDraft()), $('source').value);
      } catch (error) {
        report(error, 'Архитектура не применена');
      }
    });
    $('add-instruction').addEventListener('click', () => {
      try {
        const draft = architectureDraft();
        if (!Array.isArray(draft.instructions)) throw new Error('Таблица должна быть массивом.');
        if (draft.instructions.some(item => item?.name?.toUpperCase() === 'INC4')) {
          message('В черновике уже есть команда INC4.');
          return;
        }
        const used = new Set(draft.instructions.map(item => item?.opcode));
        let opcode = 60;
        if (used.has(opcode)) opcode = Array.from({ length: 256 }, (_, n) => n).find(n => !used.has(n));
        if (opcode === undefined) throw new Error('Свободные коды команд закончились.');
        const inc = { name: 'INC4', opcode, format: 'R', microcode: [{ op: 'add', dst: 'd', a: 'd', b: 4 }] };
        const text = $('instruction-json');
        draft.instructions.push(inc);
        text.value = '[\n' + draft.instructions.map(ins => '  ' + JSON.stringify(ins)).join(',\n') + '\n]';
        text.scrollTop = text.scrollHeight;
        renderDraft();
        message('INC4 добавлена в черновик с кодом 0x' + hex(opcode, 2) + '.');
      } catch (error) {
        report(error, 'Команда не добавлена');
      }
    });

    $('save').addEventListener('click', saveProject);
    $('load').addEventListener('click', () => $('project-file').click());
    $('project-file').addEventListener('change', async event => {
      const file = event.target.files[0];
      event.target.value = '';
      if (!file) return;
      try {
        loadProject(await file.text());
      } catch (error) {
        report(error, 'Проект не открыт');
      }
    });
  }

  try {
    if (window.M32Appearance) window.M32Appearance.mount($('studio-theme'), $('warmth'));
    createMemoryGrid();
    const initial = cpu.defaults();
    assemble(initial, sample.counter.source, 'counter');
    showMemory(0x80);
    wire();
  } catch (error) {
    report(error, 'Лаборатория не запущена');
  }
})();
