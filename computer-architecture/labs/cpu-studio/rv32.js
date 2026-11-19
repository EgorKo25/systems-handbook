(() => {
  'use strict';

  const cpu = window.M32Logic;
  const $ = id => document.getElementById(id);
  const editor = $('rv32-source');
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
  let assembled;
  let machine;
  let listingWords;
  let lastStore;
  let lastBranch;
  let lastJump;

  const address = value => '0x' + cpu.hex(value, 4);
  const bytes = (memory, start) =>
    Array.from(memory.slice(start, start + 4), value => cpu.hex(value, 2)).join(' ');
  const status = text => { $('status').textContent = text; };

  function render() {
    $('pc').textContent = address(machine.pc);
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
    updateDatapathLink(canContinue);
  }

  function load(source) {
    const next = cpu.create(source);
    const rows = cpu.assemble(source);
    const listing = rows.map(row =>
      [address(row.address), bytes(next.memory, row.address), row.text.trim()].join('  '));
    listingWords = new Map(rows.map(row => [row.address, row.word]));
    machine = next;
    lastStore = null;
    lastBranch = null;
    lastJump = null;
    assembled = source;
    $('rv32-listing').textContent = listing.join('\n');
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
    const snapshot = new URLSearchParams({
      pc: cpu.hex(machine.pc), word: cpu.hex(word), x6: cpu.hex(machine.regs[6]),
    });
    if (arithmetic) {
      if (decoded.rs1 !== 6 || decoded.rd !== 6) return;
    } else {
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
    const examples = { '#loop': loopSource, '#calls': callsSource };
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
  $('reset').addEventListener('click', () => {
    load(assembled);
    status('Последняя сборка загружена заново. Редактируемый текст сохранён.');
  });
})();
