(() => {
  'use strict';

  const cpu = window.M32Logic;
  const $ = id => document.getElementById(id);
  const editor = $('rv32-source');
  const initial = cpu.SOURCE;
  let assembled = initial;
  let machine;
  let lastStore;

  const address = value => '0x' + cpu.hex(value, 4);
  const bytes = (memory, start) =>
    Array.from(memory.slice(start, start + 4), value => cpu.hex(value, 2)).join(' ');
  const status = text => { $('status').textContent = text; };

  function render() {
    $('pc').textContent = address(machine.pc);
    $('x5').textContent = address(machine.regs[5]);
    $('x6').textContent = address(machine.regs[6]);
    $('input-word').textContent = bytes(machine.memory, 0x2000);
    $('output-word').textContent = bytes(machine.memory, 0x2200);
    $('last-store').textContent = lastStore
      ? address(lastStore.address) + ' · ' + lastStore.after.map(value => cpu.hex(value, 2)).join(' ')
      : 'Записей ещё нет';
    const canContinue = machine.status === 'ready' && editor.value === assembled;
    $('step').disabled = !canContinue;
    $('run').disabled = !canContinue;
  }

  function load(source) {
    const next = cpu.create(source);
    const listing = cpu.assemble(source).map(row =>
      [address(row.address), bytes(next.memory, row.address), row.text.trim()].join('  '));
    machine = next;
    lastStore = null;
    assembled = source;
    $('rv32-listing').textContent = listing.join('\n');
    render();
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

  editor.value = initial;
  window.M32Appearance?.mount($('studio-theme'), $('warmth'));
  load(initial);
  status('Пример из главы собран.');

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
    lastStore = event.memory.at(-1) ?? lastStore;
    report(event);
    render();
  });
  $('run').addEventListener('click', () => {
    const events = cpu.run(machine, 1000);
    for (const event of events) lastStore = event.memory.at(-1) ?? lastStore;
    report(events.at(-1));
    if (machine.status === 'ready') status('Выполнено 1000 команд. Можно продолжить с текущего адреса.');
    render();
  });
  $('reset').addEventListener('click', () => {
    load(assembled);
    status('Последняя сборка загружена заново. Редактируемый текст сохранён.');
  });
})();
