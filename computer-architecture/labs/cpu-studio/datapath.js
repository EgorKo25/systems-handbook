(function () {
  'use strict';

  const cpu = typeof module === 'object' ? require('../logic/model.js') : window.M32Logic;
  const stages = ['Выборка', 'Декодирование', 'Сложение', 'Запись'];

  function create(value = 42, increment = 1) {
    if (!Number.isInteger(value) || value < 0 || value > 0xffffffff) {
      throw new Error('Начальное x6 должно быть целым числом от 0 до 4294967295.');
    }
    if (!Number.isInteger(increment) || increment < -2048 || increment > 2047) {
      throw new Error('Константа должна быть целым числом от −2048 до 2047.');
    }
    const instruction = cpu.assemble('addi x6, x6, ' + increment)[0].word;
    return { cycle: 0, pc: cpu.ENTRY, x6: value, instruction, ir: null, decoded: null, operand: null, result: null };
  }

  function clock(state) {
    switch (state.cycle) {
      case 0:
        return { ...state, cycle: 1, ir: state.instruction };
      case 1:
        return { ...state, cycle: 2, decoded: cpu.decode(state.ir), operand: state.x6 };
      case 2:
        return { ...state, cycle: 3, result: cpu.u32(state.operand + state.decoded.immediate) };
      case 3:
        return { ...state, cycle: 4, x6: state.result, pc: cpu.u32(state.pc + 4) };
      default:
        return state;
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
    $('word').textContent = hex(state.instruction);
    $('ir').textContent = hex(state.ir);
    $('operand').textContent = state.operand === null ? '—' : state.operand + ' + (' + state.decoded.immediate + ')';
    $('alu').textContent = hex(state.result);
    $('register').textContent = hex(state.x6);
    $('pc').textContent = hex(state.pc);
    $('clock').disabled = state.cycle === stages.length;
    for (let index = 0; index < stages.length; index++) {
      const item = $('stage-' + index);
      if (index + 1 === state.cycle) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    }
    $('status').textContent = state.cycle
      ? 'Такт ' + state.cycle + ' из 4. ' + stages[state.cycle - 1] + '.'
      : 'Исходное состояние. Инструкция ещё в памяти.';
  }

  function reset() {
    try {
      const value = $('initial').value.trim();
      const increment = $('increment').value.trim();
      if (!value || !increment) throw new Error('Заполните начальное значение и константу.');
      state = create(Number(value), Number(increment));
      render();
    } catch (error) {
      $('status').textContent = error.message;
    }
  }

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
