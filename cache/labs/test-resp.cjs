'use strict';
const assert = require('node:assert/strict');
const R = require('../sources/resp-lab.js');
let checks = 0;
function check(name, action) { action(); checks++; console.log('PASS', name); }
const bytes = R.requestBytes();
check('exact 26-byte request and length prefixes', () => {
  assert.equal(bytes.length, 26);
  assert.equal(R.REQUEST, '*2\r\n$3\r\nGET\r\n$7\r\nbook:42\r\n');
  assert.deepEqual(R.encodeCommand(['GET', 'book:42']), bytes);
});
check('all 26 incomplete prefixes and complete frame', () => {
  for (let n = 0; n < bytes.length; n++) {
    const parsed = R.parseRequest(bytes.subarray(0, n));
    assert.equal(parsed.status, 'incomplete', 'prefix ' + n);
    assert.equal(parsed.consumed, 0, 'no complete frame at prefix ' + n);
  }
  const parsed = R.parseRequest(bytes);
  assert.equal(parsed.status, 'complete'); assert.equal(parsed.consumed, 26); assert.equal(parsed.nextOffset, 26);
  assert.deepEqual(parsed.args.map(R.decode), ['GET', 'book:42']);
});
check('artificial reads 8 + 13 + 5 preserve exact parser progress', () => {
  const states = R.steps();
  assert.deepEqual(R.READS, [8, 13, 5]);
  assert.deepEqual(states.map(s => s.receivedTotal), [0, 8, 21, 26]);
  assert.deepEqual(states.map(s => s.readyArgs), [0, 0, 1, 2]);
  assert.deepEqual([states[1].current.length, states[1].current.received], [3, 0]);
  assert.deepEqual([states[2].current.length, states[2].current.received], [7, 4]);
  assert.equal(R.decode(states[2].args[0]), 'GET');
});
check('UTF-8 Cyrillic uses encoded byte lengths', () => {
  const command = R.encodeCommand(['GET', 'кот']);
  assert.equal(R.visible(command), '*2\\r\\n$3\\r\\nGET\\r\\n$6\\r\\n\\xD0\\xBA\\xD0\\xBE\\xD1\\x82\\r\\n');
  assert.equal(R.decode(R.parseRequest(command).args[1]), 'кот');
  for (let n = 0; n < command.length; n++) assert.equal(R.parseRequest(command.subarray(0, n)).status, 'incomplete');
});
check('NUL, CRLF and END inside payload stay binary data', () => {
  const value = new Uint8Array([0, 13, 10, 69, 78, 68, 0, 255]);
  const command = R.encodeCommand(['SET', 'binary', value]);
  const parsed = R.parseRequest(command);
  assert.equal(parsed.status, 'complete'); assert.deepEqual(parsed.args[2], value);
  for (let n = 0; n < command.length; n++) assert.equal(R.parseRequest(command.subarray(0, n)).status, 'incomplete');
});
check('two commands glued together have independent consumed byte counts', () => {
  const ping = R.encodeCommand(['PING']), joined = new Uint8Array(bytes.length + ping.length);
  joined.set(bytes); joined.set(ping, bytes.length);
  const first = R.parseRequest(joined), second = R.parseRequest(joined, first.nextOffset);
  assert.equal(first.consumed, 26); assert.equal(first.trailingBytes, 14);
  assert.equal(second.consumed, 14); assert.equal(second.nextOffset, 40);
  assert.deepEqual(second.args.map(R.decode), ['PING']);
});
check('bulk terminator is validated as soon as wrong bytes arrive', () => {
  const broken = bytes.slice(); broken[24] = 10;
  assert.equal(R.parseRequest(broken.subarray(0, 25)).status, 'error');
  assert.equal(R.parseRequest(broken).position, 24);
  const brokenLF = bytes.slice(); brokenLF[25] = 88;
  assert.equal(R.parseRequest(brokenLF).status, 'error');
  assert.equal(R.parseRequest(bytes.subarray(0, 25)).state, 'bulk-terminator');
});
check('wrong UTF-8 length does not silently produce a valid frame', () => {
  assert.equal(R.parseRequest(R.encode('*1\r\n$3\r\nкот\r\n')).status, 'error');
});
check('missing, empty and hello are distinct successful replies', () => {
  const missing = R.parseReply(R.encode(R.REPLIES.missing));
  const empty = R.parseReply(R.encode(R.REPLIES.empty));
  const hello = R.parseReply(R.encode(R.REPLIES.hello));
  assert.equal(missing.kind, 'missing'); assert.equal(missing.value, null); assert.equal(missing.consumed, 5);
  assert.equal(empty.kind, 'value'); assert.equal(empty.value.length, 0); assert.equal(empty.consumed, 6);
  assert.equal(hello.kind, 'value'); assert.equal(R.decode(hello.value), 'hello'); assert.equal(hello.consumed, 11);
});
check('WRONGTYPE is a complete error reply, not a parser error or miss', () => {
  const reply = R.parseReply(R.encode(R.REPLIES.wrongtype));
  assert.equal(reply.status, 'complete'); assert.equal(reply.kind, 'server-error'); assert.equal(reply.code, 'WRONGTYPE');
  assert.equal(reply.consumed, R.encode(R.REPLIES.wrongtype).length);
});
check('all incomplete prefixes of all four replies wait for more bytes', () => {
  for (const wire of Object.values(R.REPLIES)) {
    const data = R.encode(wire);
    for (let n = 0; n < data.length; n++) assert.equal(R.parseReply(data.subarray(0, n)).status, 'incomplete', wire + ' prefix ' + n);
    assert.equal(R.parseReply(data).status, 'complete');
  }
});
check('binary response and concatenated replies consume exactly one frame', () => {
  const binary = new Uint8Array([36, 52, 13, 10, 0, 13, 10, 255, 13, 10]);
  assert.deepEqual(R.parseReply(binary).value, new Uint8Array([0, 13, 10, 255]));
  const joined = R.encode(R.REPLIES.missing + R.REPLIES.empty);
  const first = R.parseReply(joined), second = R.parseReply(joined, first.nextOffset);
  assert.equal(first.consumed, 5); assert.equal(second.consumed, 6); assert.equal(second.nextOffset, 11);
  binary[9] = 0; assert.equal(R.parseReply(binary).kind, 'protocol-error');
});
check('malformed headers and unsupported shapes fail explicitly', () => {
  for (const wire of ['*2\n', '*x\r\n', '*129\r\n', '*1\r\n$-1\r\n', '*1\r\n:5\r\n', '*1\r\n$1048577\r\n']) assert.equal(R.parseRequest(R.encode(wire)).status, 'error', wire);
  assert.equal(R.parseRequest(R.encode('*0\r\n')).status, 'complete');
  assert.equal(R.parseReply(R.encode('$-2\r\n')).status, 'error');
  assert.equal(R.parseReply(R.encode('$0\r\nX')).status, 'error');
  assert.throws(() => R.parseRequest('not bytes'), TypeError);
  assert.throws(() => R.parseRequest(bytes, -1), RangeError);
});
check('UI wiring: three reads, byte hex, reply selector, back and idempotent mount', () => {
  class Element {
    constructor() { this.children = []; this.handlers = {}; this.attrs = {}; this.dataset = {}; this.hidden = false; this.textContent = ''; this.value = 'missing'; this.classList = { toggle() {} }; }
    append(...children) { this.children.push(...children); }
    get firstChild() { return this.children[0]; }
    setAttribute(name, value) { this.attrs[name] = value; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
  }
  const names = ['live', 'prev', 'next', 'step', 'bytes', 'byte-note', 'received', 'args', 'state', 'explanation', 'reply', 'response', 'reply-wire', 'reply-note'];
  const elements = Object.fromEntries(names.map(name => [name, new Element()]));
  const box = new Element();
  box.querySelector = selector => elements[selector.match(/^\[data-resp-(.+)\]$/)[1]];
  const priorDocument = global.document;
  global.document = { createElement: () => new Element() };
  try {
    R.mount(box);
    assert.equal(elements.bytes.children.length, 26);
    assert.equal(elements.prev.disabled, true);
    assert.equal(elements.reply.hidden, true);
    elements.next.handlers.click(); assert.match(elements.received.textContent, /8 \/ 26/); assert.match(elements.args.textContent, /0 \/ 2/);
    elements.next.handlers.click(); assert.match(elements.state.textContent, /4 из 7/); assert.match(elements.args.textContent, /1 \/ 2/);
    elements.next.handlers.click(); assert.match(elements.args.textContent, /2 \/ 2/); assert.equal(elements.reply.hidden, false); assert.equal(elements.next.disabled, true);
    elements.response.value = 'empty'; elements.response.handlers.change(); assert.equal(elements['reply-wire'].textContent, '$0\\r\\n\\r\\n');
    elements.response.value = 'wrongtype'; elements.response.handlers.change(); assert.match(elements['reply-note'].textContent, /ошибку WRONGTYPE/);
    elements.bytes.children[2].handlers.click(); assert.equal(elements.bytes.children[2].firstChild.textContent, '0D');
    elements.prev.handlers.click(); assert.equal(elements.reply.hidden, true); assert.equal(elements.next.disabled, false);
    R.mount(box); assert.equal(elements.bytes.children.length, 26);
  } finally {
    if (priorDocument === undefined) delete global.document;
    else global.document = priorDocument;
  }
});
console.log('RESP model:', checks, 'test groups passed; no Redis process or network required.');
