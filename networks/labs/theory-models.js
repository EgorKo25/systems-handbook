/* Original teaching models. No network access, commands, storage or dependencies. */
(function (root) {
  'use strict';
  function bounded(value, min, max, label) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < min || n > max || String(value).trim() === '')
      throw new Error(label + ': допустимо от ' + min + ' до ' + max + '.');
    return n;
  }
  function capacity(bandwidthMHz, snrDB) {
    const bandwidth = bounded(bandwidthMHz, 0.01, 1000, 'Полоса');
    const snr = bounded(snrDB, -30, 60, 'Отношение сигнала к шуму');
    const ratio = 10 ** (snr / 10);
    return { ratio, mbps: bandwidth * Math.log2(1 + ratio) };
  }
  function remainder(value, polynomial = 0b1011) {
    let v = value;
    const degree = Math.floor(Math.log2(polynomial));
    while (v && Math.floor(Math.log2(v)) >= degree)
      v ^= polynomial << (Math.floor(Math.log2(v)) - degree);
    return v;
  }
  function crc(bits, flip = 0) {
    if (!/^[01]{1,24}$/.test(String(bits)))
      throw new Error('Данные: введите от 1 до 24 символов 0 или 1.');
    const width = bits.length + 3;
    const position = bounded(flip, 0, width, 'Номер бита справа');
    if (!Number.isInteger(position)) throw new Error('Номер бита должен быть целым.');
    const source = parseInt(bits, 2) * 8;
    const code = source ^ remainder(source);
    const received = code ^ (position ? (1 << (position - 1)) : 0);
    return {
      checksum: remainder(source).toString(2).padStart(3, '0'),
      transmitted: code.toString(2).padStart(width, '0'),
      received: received.toString(2).padStart(width, '0'),
      syndrome: remainder(received).toString(2).padStart(3, '0'),
      detected: remainder(received) !== 0
    };
  }
  function burst(inputMbps, outputMbps, durationMs, afterMbps) {
    const input = bounded(inputMbps, 0, 100000, 'Вход');
    const output = bounded(outputMbps, 0.01, 100000, 'Выход');
    const duration = bounded(durationMs, 0, 100000, 'Длительность');
    const after = bounded(afterMbps, 0, 100000, 'Последующий вход');
    const bits = Math.max(0, input - output) * 1000 * duration;
    return { bits, bytes: bits / 8, waitMs: bits / (output * 1000),
      drainMs: !bits ? 0 : after < output ? bits / ((output - after) * 1000) : null,
      growingAfter: after > output };
  }
  function schedule(arrivals, service) {
    if (arrivals.length !== service.length) throw new Error('Разные длины расписаний.');
    let end = 0;
    return arrivals.map((arrival, i) => {
      if (!Number.isFinite(arrival) || arrival < 0 || (i && arrival < arrivals[i-1]) || !Number.isFinite(service[i]) || service[i] < 0)
        throw new Error('Некорректное расписание.');
      const start = Math.max(arrival, end); end = start + service[i];
      return { arrival, start, end, wait: start - arrival, total: end - arrival };
    });
  }
  function pipeline(packetBits, rates) {
    if (!rates.length || rates.some(r => !Number.isFinite(r) || r <= 0) || packetBits.some(b => !Number.isFinite(b) || b <= 0))
      throw new Error('Размеры и скорости должны быть положительными.');
    const available = rates.map(() => 0);
    return packetBits.map(bits => {
      let arrival = 0;
      return rates.map((rate, j) => {
        const start = Math.max(arrival, available[j]);
        arrival = available[j] = start + bits / rate;
        return { start, end: arrival };
      });
    });
  }
  const api = Object.freeze({ capacity, remainder, crc, burst, schedule, pipeline });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (!root.document) return;
  const fmt = n => n.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  for (const container of root.document.querySelectorAll('[data-theory]')) {
    const get = name => container.querySelector('[data-' + name + ']').value;
    const result = container.querySelector('[data-result]');
    function paint() {
      try {
        if (container.dataset.theory === 'capacity') {
          const r = capacity(get('bandwidth'), get('snr'));
          result.textContent = 'S/N = ' + fmt(r.ratio) + '; C = ' + fmt(r.mbps) + ' Мбит/с. Это теоретическая ёмкость модели, не скорость устройства.';
        } else if (container.dataset.theory === 'crc') {
          const r = crc(get('bits'), get('flip'));
          result.textContent = 'CRC: ' + r.checksum + '. Передано: ' + r.transmitted + '. Принято: ' + r.received + '. Остаток: ' + r.syndrome + '. ' + (r.detected ? 'Изменение обнаружено.' : 'Проверка не обнаружила изменения.');
        } else if (container.dataset.theory === 'burst') {
          const r = burst(get('input-rate'), get('output-rate'), get('duration'), get('after-rate'));
          const after = !r.bits && r.growingAfter
            ? 'К концу всплеска очередь пуста; после него вход выше выхода, поэтому начнёт расти новая очередь.'
            : r.drainMs === null ? 'При таком последующем входе очередь не опустеет.' : 'Очередь опустеет через ' + fmt(r.drainMs) + ' мс после всплеска.';
          result.textContent = 'Остаток: ' + fmt(r.bytes) + ' байт. Работа перед последним битом: ' + fmt(r.waitMs) + ' мс. ' + after;
        }
        result.removeAttribute('data-error');
      } catch (error) { result.textContent = error.message; result.setAttribute('data-error', ''); }
    }
    container.addEventListener('input', paint); paint();
  }
})(typeof window === 'undefined' ? globalThis : window);
