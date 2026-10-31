;(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CacheRespLab = api;
  if (typeof document !== 'undefined') {
    const init = () => document.querySelectorAll('[data-resp-lab]').forEach(api.mount);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const LIMITS = Object.freeze({ args: 128, bulk: 1048576, input: 4194304, header: 32, errorLine: 1024 });
  const READS = Object.freeze([8, 13, 5]);
  const REQUEST = '*2\r\n$3\r\nGET\r\n$7\r\nbook:42\r\n';
  const REPLIES = Object.freeze({
    missing: '$-1\r\n', empty: '$0\r\n\r\n', hello: '$5\r\nhello\r\n',
    wrongtype: '-WRONGTYPE Operation against a key holding the wrong kind of value\r\n'
  });
  const encode = text => new TextEncoder().encode(text);
  const decode = bytes => new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  const requestBytes = () => encode(REQUEST);

  function inputBytes(value, offset) {
    if (!(value instanceof Uint8Array)) throw new TypeError('Нужен Uint8Array байтов; текст сначала кодируют в UTF-8.');
    if (!Number.isInteger(offset) || offset < 0 || offset > value.length) throw new RangeError('Некорректный начальный сдвиг.');
    return value;
  }

  // This parser is deliberately a small byte-prefix model, not Redis's querybuf.
  // It reparses the supplied prefix. consumed is zero until a complete frame is
  // available; parsedThrough is only the internal progress cursor in this run.
  function line(bytes, start, maxLength = LIMITS.header, allowUtf8 = false) {
    for (let i = start; i < bytes.length; i++) {
      if (i - start > maxLength) return { error: 'Слишком длинная строка заголовка модели.', position: i };
      if (bytes[i] === 13) {
        if (i + 1 === bytes.length) return { incomplete: true };
        if (bytes[i + 1] !== 10) return { error: 'За CR должен следовать LF.', position: i + 1 };
        const raw = bytes.subarray(start, i);
        let text;
        try { text = decode(raw); } catch (_) { return { error: 'Некорректная кодировка строкового заголовка.', position: start }; }
        return { text, end: i + 2 };
      }
      if (bytes[i] === 10) return { error: 'LF без предшествующего CR.', position: i };
      if (!allowUtf8 && bytes[i] > 127) return { error: 'Длина и тип в заголовке записываются ASCII-байтами.', position: i };
    }
    if (bytes.length - start > maxLength) return { error: 'Слишком длинная строка заголовка модели.', position: bytes.length };
    return { incomplete: true };
  }

  function number(text, limit) {
    if (!/^\d+$/.test(text)) return null;
    const n = Number(text);
    return Number.isSafeInteger(n) && n <= limit ? n : null;
  }

  function terminator(bytes, position) {
    if (position >= bytes.length) return { incomplete: true };
    if (bytes[position] !== 13) return { error: 'После объявленных байтов данных ожидается CR.', position };
    if (position + 1 >= bytes.length) return { incomplete: true };
    if (bytes[position + 1] !== 10) return { error: 'После данных CR должен завершаться байтом LF.', position: position + 1 };
    return { end: position + 2 };
  }

  function parseRequest(value, offset = 0) {
    const bytes = inputBytes(value, offset), args = [];
    let cursor = offset, expectedArgs = null;
    const result = (status, state, extra = {}) => Object.assign({
      status, state, args, expectedArgs, readyArgs: args.length,
      consumed: 0, parsedThrough: cursor, received: bytes.length - offset, current: null
    }, extra);
    const failure = detail => result('error', 'protocol-error', { message: detail.error, position: detail.position });
    if (bytes.length - offset > LIMITS.input) return failure({ error: 'Вход превысил учебный предел 4 MiB.', position: offset });
    if (cursor === bytes.length) return result('incomplete', 'array-header');
    if (bytes[cursor] !== 42) return failure({ error: 'Командная модель ожидает массив с префиксом *.', position: cursor });
    let header = line(bytes, cursor + 1);
    if (header.error) return failure(header);
    if (header.incomplete) return result('incomplete', 'array-header');
    expectedArgs = number(header.text, LIMITS.args);
    if (expectedArgs === null) return failure({ error: 'Нужно число аргументов от 0 до 128.', position: cursor + 1 });
    cursor = header.end;
    while (args.length < expectedArgs) {
      if (cursor === bytes.length) return result('incomplete', 'bulk-header');
      if (bytes[cursor] !== 36) return failure({ error: 'Каждый аргумент этой модели должен быть bulk-строкой с префиксом $.', position: cursor });
      header = line(bytes, cursor + 1);
      if (header.error) return failure(header);
      if (header.incomplete) return result('incomplete', 'bulk-header');
      const length = number(header.text, LIMITS.bulk);
      if (length === null) return failure({ error: 'Нужна длина аргумента от 0 до 1 MiB; null-аргументы модель не поддерживает.', position: cursor + 1 });
      cursor = header.end;
      const current = { index: args.length, start: cursor, length, received: Math.min(bytes.length - cursor, length) };
      if (current.received < length) return result('incomplete', 'bulk-data', { current });
      const end = terminator(bytes, cursor + length);
      if (end.error) return failure(end);
      if (end.incomplete) return result('incomplete', 'bulk-terminator', { current });
      args.push(bytes.slice(cursor, cursor + length));
      cursor = end.end;
    }
    return result('complete', 'ready', { consumed: cursor - offset, nextOffset: cursor, trailingBytes: bytes.length - cursor });
  }

  function parseReply(value, offset = 0) {
    const bytes = inputBytes(value, offset);
    const fail = (message, position = offset) => ({ status: 'error', kind: 'protocol-error', message, position, consumed: 0 });
    const wait = state => ({ status: 'incomplete', state, consumed: 0 });
    if (bytes.length - offset > LIMITS.input) return fail('Вход превысил учебный предел 4 MiB.');
    if (offset === bytes.length) return wait('reply-type');
    if (bytes[offset] === 45) {
      const header = line(bytes, offset + 1, LIMITS.errorLine, true);
      if (header.error) return fail(header.error, header.position);
      if (header.incomplete) return wait('error-line');
      return { status: 'complete', kind: 'server-error', message: header.text, code: header.text.split(' ', 1)[0], consumed: header.end - offset, nextOffset: header.end };
    }
    if (bytes[offset] !== 36) return fail('Ответная модель поддерживает только $, null bulk и простую ошибку -.');
    const header = line(bytes, offset + 1);
    if (header.error) return fail(header.error, header.position);
    if (header.incomplete) return wait('bulk-header');
    if (header.text === '-1') return { status: 'complete', kind: 'missing', value: null, consumed: header.end - offset, nextOffset: header.end };
    const length = number(header.text, LIMITS.bulk);
    if (length === null) return fail('Недопустимая длина bulk-ответа; модель поддерживает -1 либо 0…1 MiB.');
    if (bytes.length - header.end < length) return wait('bulk-data');
    const end = terminator(bytes, header.end + length);
    if (end.error) return fail(end.error, end.position);
    if (end.incomplete) return wait('bulk-terminator');
    return { status: 'complete', kind: 'value', value: bytes.slice(header.end, header.end + length), consumed: end.end - offset, nextOffset: end.end };
  }

  function encodeCommand(args) {
    if (!Array.isArray(args) || args.length > LIMITS.args) throw new RangeError('Нужен массив до 128 аргументов.');
    const payloads = args.map(value => {
      const bytes = typeof value === 'string' ? encode(value) : inputBytes(value, 0);
      if (bytes.length > LIMITS.bulk) throw new RangeError('Аргумент превышает 1 MiB.');
      return bytes;
    });
    const chunks = [encode('*' + payloads.length + '\r\n')];
    payloads.forEach(bytes => chunks.push(encode('$' + bytes.length + '\r\n'), bytes, encode('\r\n')));
    const total = chunks.reduce((sum, bytes) => sum + bytes.length, 0);
    if (total > LIMITS.input) throw new RangeError('Команда превышает 4 MiB.');
    const output = new Uint8Array(total);
    let at = 0;
    chunks.forEach(bytes => { output.set(bytes, at); at += bytes.length; });
    return output;
  }

  function steps() {
    const bytes = requestBytes(), sizes = [0, 8, 21, 26];
    return sizes.map(received => Object.assign({ receivedTotal: received }, parseRequest(bytes.subarray(0, received))));
  }

  function visibleByte(byte) {
    if (byte === 13) return '\\r';
    if (byte === 10) return '\\n';
    if (byte === 0) return '\\0';
    return byte >= 32 && byte < 127 ? String.fromCharCode(byte) : '\\x' + byte.toString(16).padStart(2, '0').toUpperCase();
  }
  const visible = bytes => Array.from(bytes, visibleByte).join('');
  const fields = [
    [0, 4, 'заголовок массива: два аргумента'], [4, 8, 'длина первого аргумента: три байта'],
    [8, 11, 'данные первого аргумента GET'], [11, 13, 'CRLF после первого аргумента'],
    [13, 17, 'длина второго аргумента: семь байт'], [17, 24, 'данные ключа book:42'], [24, 26, 'CRLF после ключа']
  ];
  const fieldAt = offset => fields.find(field => offset >= field[0] && offset < field[1])[2];

  function mount(box) {
    if (box.dataset.respMounted) return;
    box.dataset.respMounted = 'true';
    const find = name => box.querySelector('[data-resp-' + name + ']');
    const allSteps = steps(), bytes = requestBytes();
    let index = 0, selected = null;
    const buttons = Array.from(bytes, (byte, offset) => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'resp-byte';
      const symbol = document.createElement('span'), number = document.createElement('small');
      number.textContent = offset; button.append(symbol, number);
      button.setAttribute('aria-label', 'Сдвиг ' + offset + ': ' + visibleByte(byte) + '; ' + fieldAt(offset));
      button.addEventListener('click', () => { selected = selected === offset ? null : offset; draw(); });
      find('bytes').append(button);
      return button;
    });
    function drawReply() {
      const kind = find('response').value, wire = REPLIES[kind];
      const parsed = parseReply(encode(wire));
      find('reply-wire').textContent = visible(encode(wire));
      const notes = {
        missing: 'Корректный ответ: значения нет. Это промах; null отличается от найденной пустой строки.',
        empty: 'Значение найдено и содержит 0 байт. Первый CRLF завершает заголовок, второй завершает пустой блок данных.',
        hello: 'Значение найдено: после заголовка следуют ровно 5 байт hello, затем CRLF.',
        wrongtype: 'Сервер вернул ошибку WRONGTYPE: ключ существует с другим типом. RESP разобран корректно; ошибка команды не является промахом.'
      };
      find('reply-note').textContent = notes[kind] + ' Длина ответа: ' + parsed.consumed + ' байт.';
    }
    function draw() {
      const state = allSteps[index];
      find('step').textContent = 'Чтение ' + index + ' из 3';
      find('prev').disabled = index === 0;
      find('next').disabled = index === 3;
      find('next').textContent = index < 3 ? 'Принять ' + READS[index] + ' байт →' : 'Все байты приняты';
      find('received').textContent = 'Получено суммарно: ' + state.receivedTotal + ' / 26 байт';
      find('args').textContent = 'Готовых аргументов: ' + state.readyArgs + (state.expectedArgs === null ? ' · число ещё неизвестно' : ' / ' + state.expectedArgs);
      const titles = ['Ждём заголовок массива', 'Ждём 3 байта первого аргумента', 'У ключа пока 4 из 7 байт', 'Оба аргумента завершены'];
      const notes = [
        'Ничего ещё не получено. Байты в таблице пока только ожидаются; выполнять команду нельзя.',
        '*2 объявил массив из двух аргументов, $3 — длину первого. Имя GET ещё не пришло.',
        'GET и его CRLF уже завершены. $7 объявил длину ключа; пришло book, не хватает :42 и завершающего CRLF. Выполнять GET рано.',
        'Получены GET, book:42 и оба окончания. Из потока выделена одна полная команда длиной 26 байт; теперь можно перейти к её проверке и исполнению.'
      ];
      find('state').textContent = titles[index]; find('explanation').textContent = notes[index];
      buttons.forEach((button, offset) => {
        button.classList.toggle('is-received', offset < state.receivedTotal);
        button.classList.toggle('is-new', offset >= (index ? allSteps[index - 1].receivedTotal : 0) && offset < state.receivedTotal);
        button.setAttribute('aria-pressed', String(selected === offset));
        button.setAttribute('aria-label', 'Сдвиг ' + offset + ': ' + visibleByte(bytes[offset]) + ', hex ' + bytes[offset].toString(16).padStart(2, '0').toUpperCase() + '; ' + fieldAt(offset) + (offset < state.receivedTotal ? '; получен' : '; ещё не получен'));
        button.firstChild.textContent = selected === offset ? bytes[offset].toString(16).padStart(2, '0').toUpperCase() : visibleByte(bytes[offset]);
      });
      find('byte-note').textContent = selected === null ? 'Под символом указан номер байта, нумерация с нуля. Нажмите байт для hex — шестнадцатеричного значения.' : 'Байт ' + selected + ': ' + visibleByte(bytes[selected]) + ' = 0x' + bytes[selected].toString(16).padStart(2, '0').toUpperCase() + ' · ' + fieldAt(selected) + (selected < state.receivedTotal ? ' · уже получен.' : ' · ещё не получен.');
      find('reply').hidden = index !== 3;
      drawReply();
    }
    find('prev').addEventListener('click', () => { index = Math.max(0, index - 1); draw(); });
    find('next').addEventListener('click', () => { index = Math.min(3, index + 1); draw(); });
    find('response').addEventListener('change', drawReply);
    find('live').hidden = false;
    draw();
  }
  return { LIMITS, READS, REQUEST, REPLIES, encode, decode, requestBytes, parseRequest, parseReply, encodeCommand, steps, visibleByte, visible, mount };
});
