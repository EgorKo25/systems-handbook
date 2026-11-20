(() => {
  'use strict';

  const cpu = window.M32Logic;
  const $ = id => document.getElementById(id);
  const editor = $('rv32-source');
  const listing = $('rv32-listing');
  const loopSource = [
    'addi x7, x0, 3',
    'loop: addi x7, x7, -1',
    'bne x7, x0, loop',
    'ebreak',
  ].join('\n');
  const callsSource = [
    'lui x2, 0x4',
    'jal x1, outer',
    'ebreak',
    'outer: addi x2, x2, -16',
    'sw x1, 12(x2)',
    'jal x1, inner',
    'lw x1, 12(x2)',
    'addi x2, x2, 16',
    'jalr x0, 0(x1)',
    'inner: addi x6, x6, 1',
    'jalr x0, 0(x1)',
  ].join('\n');
  const byteOrderSource = [
    'lui x5, 0x2',
    'lui x6, 0x12345',
    'addi x6, x6, 0x678',
    'sw x6, 512(x5)',
    'ebreak',
  ].join('\n');
  let assembled;
  let machine;
  let listingWords;
  let listingLines;
  let currentLine;
  let lastStore;
  let lastBranch;
  let lastJump;

  const address = value => '0x' + cpu.hex(value, 4);
  const bytes = (memory, start) =>
    Array.from(memory.slice(start, start + 4), value => cpu.hex(value, 2)).join(' ');
  const status = text => { $('status').textContent = text; };

  function render() {
    $('pc').textContent = address(machine.pc);
    $('attempts').textContent = String(machine.attempts);
    $('retired').textContent = String(machine.retired);
    $('x1').textContent = address(machine.regs[1]);
    $('x2').textContent = address(machine.regs[2]);
    $('last-jump').textContent = lastJump
      ? lastJump.decoded.op + ' · ' + address(lastJump.pcBefore) + ' → ' + address(lastJump.pcAfter)
      : 'Переходов с JAL или JALR ещё нет';
    $('x5').textContent = address(machine.regs[5]);
    $('x6').textContent = address(machine.regs[6]);
    $('x7').textContent = address(machine.regs[7]);
    $('last-branch').textContent = lastBranch
      ? (lastBranch.branch.taken ? 'Переход' : 'Следующая команда') + ' · ' + address(lastBranch.pcAfter)
      : 'BNE ещё не выполнена';
    $('input-word').textContent = bytes(machine.memory, 0x2000);
    $('output-word').textContent = bytes(machine.memory, 0x2200);
    $('last-store').textContent = lastStore
      ? address(lastStore.address) + ' · ' + lastStore.after.map(value => cpu.hex(value, 2)).join(' ')
      : 'Записей ещё нет';
    const canContinue = machine.status === 'ready' && editor.value === assembled;
    $('step').disabled = !canContinue;
    $('run').disabled = !canContinue;
    $('run-to').disabled = !canContinue;
    updateListingMarker(editor.value === assembled ? listingLines.get(machine.pc) : undefined);
    updateDatapathLink(canContinue);
  }

  function updateListingMarker(line) {
    if (line === currentLine) return;
    currentLine?.removeAttribute('aria-current');
    currentLine = line;
    if (!line) return;

    line.setAttribute('aria-current', 'step');
    const scroll = listing.parentElement;
    const bounds = scroll.getBoundingClientRect();
    const row = line.getBoundingClientRect();
    const bottom = bounds.top + scroll.clientHeight;
    if (row.top < bounds.top) scroll.scrollTop -= bounds.top - row.top;
    else if (row.bottom > bottom) scroll.scrollTop += row.bottom - bottom;
  }

  function load(source) {
    const next = cpu.create(source);
    const rows = cpu.assemble(source);
    const fragment = document.createDocumentFragment();
    listingLines = new Map();
    for (const [index, row] of rows.entries()) {
      if (index > 0) fragment.append('\n');
      const line = document.createElement('span');
      line.textContent = [address(row.address), bytes(next.memory, row.address), row.text.trim()].join('  ');
      listingLines.set(row.address, line);
      fragment.append(line);
    }
    listingWords = new Map(rows.map(row => [row.address, row.word]));
    machine = next;
    lastStore = null;
    lastBranch = null;
    lastJump = null;
    assembled = source;
    listing.replaceChildren(fragment);
    render();
  }

  function updateDatapathLink(canContinue) {
    const link = $('rv32-datapath');
    link.hidden = true;
    link.removeAttribute('href');
    const word = listingWords.get(machine.pc);
    if (!canContinue || word === undefined || cpu.read32(machine.memory, machine.pc) !== word) return;
    const decoded = cpu.decode(word);
    const arithmetic = decoded.op === 'ADDI';
    const snapshot = new URLSearchParams({ pc: cpu.hex(machine.pc), word: cpu.hex(word) });
    const jump = decoded.op === 'JAL' || decoded.op === 'JALR';
    if (jump) {
      const supported = decoded.op === 'JAL' ? decoded.rd === 1
        : decoded.rd === 0 && decoded.rs1 === 1 && decoded.immediate === 0;
      if (!supported) return;
      snapshot.set('x1', cpu.hex(machine.regs[1]));
    } else if (decoded.op === 'BNE') {
      if (decoded.rs1 !== 7 || decoded.rs2 !== 0) return;
      snapshot.set('x7', cpu.hex(machine.regs[7]));
    } else {
      snapshot.set('x6', cpu.hex(machine.regs[6]));
    }
    if (arithmetic) {
      if (decoded.rs1 !== 6 || decoded.rd !== 6) return;
    } else if (!jump && decoded.op !== 'BNE') {
      if (decoded.rs1 !== 5 || !(
        (decoded.op === 'LW' && decoded.rd === 6) || (decoded.op === 'SW' && decoded.rs2 === 6)
      )) return;
      const x5 = machine.regs[5];
      const target = cpu.u32(x5 + decoded.immediate);
      if (target % 4 !== 0 || target > cpu.SIZE - 4) return;
      snapshot.set('x5', cpu.hex(x5));
      snapshot.set('ram', cpu.hex(cpu.read32(machine.memory, target)));
    }
    link.href = 'datapath.html#' + decoded.op.toLowerCase() + '?' + snapshot;
    link.textContent = 'Разобрать ' + decoded.op + ' по адресу ' + address(machine.pc) + ' по тактам';
    link.hidden = false;
  }

  function remember(event) {
    lastStore = event.memory.at(-1) ?? lastStore;
    if (event.branch && event.kind === 'instruction') lastBranch = event;
    if (event.jump && event.kind === 'instruction') lastJump = event;
  }

  function report(event) {
    if (machine.status === 'breakpoint') {
      status('EBREAK по адресу ' + address(machine.pc) + '. Выполнение остановлено.');
    } else if (machine.status === 'trap') {
      status('Ошибка по адресу ' + address(machine.pc) + ' (' + machine.trap.cause + ').');
    } else {
      status('Выполнена ' + event.decoded.op + ' по адресу ' + address(event.pcBefore) + '.');
    }
  }

  function loadExample() {
    const example = window.location.hash;
    const examples = { '#loop': loopSource, '#calls': callsSource, '#byte-order': byteOrderSource };
    editor.value = examples[example] ?? cpu.SOURCE;
    $('loop').hidden = example !== '#loop';
    $('calls').hidden = example !== '#calls';
    $('store-note').hidden = Object.hasOwn(examples, example);
    load(editor.value);
    status('Пример из главы собран.');
  }

  window.M32Appearance?.mount($('studio-theme'), $('warmth'));
  loadExample();
  window.addEventListener('hashchange', loadExample);

  editor.addEventListener('input', () => {
    render();
    status(editor.value === assembled ? 'Открыта последняя сборка.' : 'Соберите изменённый исходный код.');
  });
  $('assemble').addEventListener('click', () => {
    try {
      load(editor.value);
      status('Программа собрана и загружена с адреса ' + address(cpu.ENTRY) + '.');
    } catch (error) {
      status(error.message);
    }
  });
  $('step').addEventListener('click', () => {
    const event = cpu.step(machine);
    remember(event);
    report(event);
    render();
  });
  $('run').addEventListener('click', () => {
    const events = cpu.run(machine, 1000);
    for (const event of events) remember(event);
    report(events.at(-1));
    if (machine.status === 'ready') status('Выполнено 1000 команд. Можно продолжить с текущего адреса.');
    render();
  });
  $('run-to-form').addEventListener('submit', event => {
    event.preventDefault();
    if (machine.status !== 'ready' || editor.value !== assembled) return;

    const text = $('run-to-address').value.trim();
    const target = /^0x[0-9a-f]{1,8}$/i.test(text) ? Number.parseInt(text, 16) : null;
    if (!listingWords.has(target)) {
      status('Укажите адрес команды из текущего листинга.');
      return;
    }

    let lastEvent;
    for (let count = 0; count < 1000 && machine.status === 'ready' && machine.pc !== target; count++) {
      lastEvent = cpu.step(machine);
      remember(lastEvent);
    }
    if (machine.status !== 'ready') {
      report(lastEvent);
    } else if (machine.pc === target) {
      status('Остановка перед командой по адресу ' + address(target) + '.');
    } else {
      status('Адрес не достигнут за 1000 шагов. Можно продолжить с текущего адреса.');
    }
    render();
  });
  $('reset').addEventListener('click', () => {
    load(assembled);
    status('Последняя сборка загружена заново. Редактируемый текст сохранён.');
  });
})();
