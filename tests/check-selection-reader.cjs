'use strict';
// Run after refresh/build. Execute the controllers shipped to offline readers;
// this DOM supplies events, ranges and geometry, never lookup logic.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const volumes = JSON.parse(fs.readFileSync(path.join(root, 'published-volumes.json'), 'utf8')).volumes.map(row => row.slug);
const failures = [];
let cases = 0;
function test(label, fn) {
    cases++;
    try { fn(); } catch (error) { failures.push(label + ': ' + error.stack); }
}
function events(target = {}) {
    const listeners = new Map();
    target.addEventListener = (name, listener) => {
        if (!listeners.has(name)) listeners.set(name, []);
        listeners.get(name).push(listener);
    };
    target.emit = (name, properties = {}) => {
        const event = {
            type: name, target, defaultPrevented: false, propagationStopped: false,
            preventDefault() { this.defaultPrevented = true; },
            stopPropagation() { this.propagationStopped = true; },
            ...properties
        };
        for (const callback of [...(listeners.get(name) || [])]) callback(event);
        return event;
    };
    target.listenerCount = name => (listeners.get(name) || []).length;
    return target;
}
function rect(left, top, width, height) {
    return {left, top, width, height, right: left + width, bottom: top + height};
}
class Element {
    constructor(tag, parent = null, attributes = {}) {
        this.nodeType = 1; this.tag = tag; this.parentElement = parent;
        this.attributes = {...attributes}; this.hidden = false;
        this.isConnected = true; this.style = {}; events(this);
    }
    matches(selector) {
        if (selector === 'article.chapter:not([hidden])') {
            return this.tag === 'article' && (this.attributes.class || '').split(/\s+/).includes('chapter') && !this.hidden;
        }
        if (selector === '[contenteditable]:not([contenteditable=false])') {
            return Object.hasOwn(this.attributes, 'contenteditable') && this.attributes.contenteditable !== 'false';
        }
        return this.tag === selector;
    }
    closest(selectors) {
        for (let element = this; element; element = element.parentElement) {
            if (selectors.split(',').some(selector => element.matches(selector))) return element;
        }
        return null;
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getBoundingClientRect() { return this.bounds || rect(0, 0, 0, 0); }
}
function textNode(parent) { return {nodeType: 3, parentElement: parent}; }
function boot(source, options = {}) {
    const window = events(), document = events(), pending = new Map(), searches = [];
    let serial = 0, removedRanges = 0, current = null;
    const button = new Element('button'); button.hidden = true; button.bounds = rect(0, 0, 176, 44);
    const topbar = new Element('header'), toolbar = new Element('nav');
    topbar.bounds = rect(0, 0, 390, 64); toolbar.bounds = rect(10, 750, 370, 64);
    const article = new Element('article', null, {class: 'chapter'}), paragraph = new Element('p', article);
    const secondArticle = new Element('article', null, {class: 'chapter'});
    document.getElementById = id => ({
        'selection-dictionary-action': options.noButton ? null : button,
        'phone-tools': options.noToolbar ? null : toolbar
    }[id] || null);
    document.querySelector = selector => selector === '.topbar' ? topbar : null;
    const viewport = options.noViewport ? null : events({offsetLeft: 0, offsetTop: 0, width: 390, height: 844});
    window.visualViewport = viewport;
    window.getSelection = () => current;
    if (!options.noDictionary) window.LibraryDictionary = {
        searchTerms: (query, origin) => searches.push({query, origin})
    };
    vm.runInNewContext(source, {
        document, window, innerWidth: 390, innerHeight: 844,
        requestAnimationFrame: callback => { pending.set(++serial, callback); return serial; },
        cancelAnimationFrame: id => pending.delete(id),
        addEventListener: window.addEventListener
    }, {timeout: 1000});
    function selection(text = 'WAL', settings = {}) {
        const start = settings.start || textNode(paragraph), end = settings.end || start;
        const range = {startContainer: start, endContainer: end, getBoundingClientRect: () => settings.rect || rect(130, 200, 80, 22)};
        current = {
            isCollapsed: settings.collapsed || false, rangeCount: settings.rangeCount ?? 1,
            getRangeAt: index => { assert.equal(index, 0); return range; },
            toString: () => text,
            removeAllRanges: () => { removedRanges++; current = null; }
        };
        return current;
    }
    function flush() {
        const callbacks = [...pending.values()]; pending.clear();
        callbacks.forEach(callback => callback());
        assert.equal(pending.size, 0, 'one frame settles without a repaint loop');
    }
    function show(text, settings) {
        selection(text, settings);
        assert.equal(document.emit('selectionchange').defaultPrevented, false, 'selectionchange remains native');
        flush(); return button;
    }
    return {
        window, document, button, article, paragraph, secondArticle, topbar, toolbar, viewport,
        searches, selection, show, flush, pending, clear: () => { current = null; },
        get removedRanges() { return removedRanges; }
    };
}
function popupSource(page) {
    const matches = [...page.matchAll(/<script\b[^>]*id="library-selection-controller"[^>]*>([\s\S]*?)<\/script>/g)];
    assert.equal(matches.length, 1, 'exactly one shipped selection controller');
    return matches[0][1];
}
function bridgeSource(page) {
    const matches = [...page.matchAll(/root\.LibraryDictionary = Object\.freeze\(\{searchTerms\(query, element\) \{[\s\S]*?\}\}\);/g)];
    assert.equal(matches.length, 1, 'exactly one shipped dictionary bridge');
    return matches[0][0];
}
for (const volume of volumes) {
    const page = fs.readFileSync(path.join(root, volume, 'index.html'), 'utf8');
    let source, bridge;
    test(volume + ': shipped controllers and accessible action', () => {
        source = popupSource(page); bridge = bridgeSource(page); new vm.Script(source);
        assert.match(page, /<button\b[^>]*id="selection-dictionary-action"[^>]*aria-controls="dictionary"[^>]*hidden>/);
    });
    if (!source || !bridge) continue;
    test(volume + ': exact Latin letters and normalized whitespace', () => {
        const app = boot(source);
        app.show(' \t systemctl   status\nPostgreSQL processes \u00a0');
        assert.equal(app.button.hidden, false);
        assert.equal(app.button.attributes['aria-label'], 'Найти «systemctl status PostgreSQL processes» в словаре');
        app.button.emit('click');
        assert.equal(app.searches.length, 1);
        assert.equal(app.searches[0].query, 'systemctl status PostgreSQL processes');
        assert.equal(app.searches[0].origin, app.article);
    });
    test(volume + ': only nonempty single ranges in one visible chapter', () => {
        const app = boot(source);
        const invalid = [
            ['outside an article', 'ARP', {start: textNode(new Element('p'))}],
            ['cross-chapter', 'ARP', {end: textNode(new Element('p', app.secondArticle))}],
            ['collapsed', 'ARP', {collapsed: true}], ['multiple ranges', 'ARP', {rangeCount: 2}],
            ['no range', 'ARP', {rangeCount: 0}], ['whitespace', ' \n\t ', {}],
            ['overlong selection', 'я'.repeat(161), {}], ['no painted rectangle', 'ARP', {rect: rect(0, 0, 0, 0)}]
        ];
        for (const [label, text, settings] of invalid) {
            app.show('WAL');
            assert.equal(app.button.hidden, false, label + ': begin with an existing action');
            app.show(text, settings); assert.equal(app.button.hidden, true, label);
            app.button.emit('click');
            assert.equal(app.searches.length, 0, label + ': old lookup query cleared');
        }
        app.article.hidden = true; app.show('ARP'); assert.equal(app.button.hidden, true, 'hidden chapter');
        app.article.hidden = false; app.show('я'.repeat(160));
        assert.equal(app.button.hidden, false, '160 characters accepted at the limit');
    });
    test(volume + ': form fields and editable descendants excluded', () => {
        const app = boot(source);
        for (const tag of ['input', 'textarea', 'select']) {
            app.show('ARP', {start: textNode(new Element(tag, app.article))}); assert.equal(app.button.hidden, true, tag);
            app.show('ARP', {end: textNode(new Element(tag, app.article))}); assert.equal(app.button.hidden, true, 'ending in ' + tag);
        }
        const editable = new Element('div', app.article, {contenteditable: ''});
        app.show('ARP', {start: textNode(new Element('span', editable))});
        assert.equal(app.button.hidden, true, 'inherited editable region');
        app.show('ARP', {start: textNode(new Element('span', app.article, {contenteditable: 'false'}))});
        assert.equal(app.button.hidden, false, 'ordinary read-only article content');
    });
    test(volume + ': popup bounds avoid viewport edges and fixed controls', () => {
        const app = boot(source);
        for (const box of [rect(0, 90, 80, 22), rect(360, 700, 30, 24), rect(100, 680, 100, 24)]) {
            app.show('ARP', {rect: box}); assert.equal(app.button.hidden, false);
            const left = parseFloat(app.button.style.left), top = parseFloat(app.button.style.top);
            assert.ok(left >= 12 && left + app.button.bounds.width <= 378, 'horizontal bounds');
            assert.ok(top >= 72 && top + app.button.bounds.height <= 740, 'topbar and phone toolbar excluded');
        }
        app.show('ARP', {rect: rect(40, 0, 80, 20)}); assert.equal(app.button.hidden, true, 'above reading area');
        app.show('ARP', {rect: rect(40, 790, 80, 20)}); assert.equal(app.button.hidden, true, 'below fixed controls');
        Object.assign(app.viewport, {offsetLeft: 30, offsetTop: 100, width: 320, height: 500});
        app.show('ARP', {rect: rect(0, 200, 80, 20)});
        assert.ok(parseFloat(app.button.style.left) >= 42, 'panned visual viewport offset');
        assert.ok(parseFloat(app.button.style.top) >= 120, 'visual viewport top');
        const desktop = boot(source, {noViewport: true, noToolbar: true});
        desktop.show('ARP', {rect: rect(350, 790, 30, 20)}); assert.equal(desktop.button.hidden, false);
        assert.ok(parseFloat(desktop.button.style.left) + desktop.button.bounds.width <= 378, 'innerWidth fallback');
        assert.ok(parseFloat(desktop.button.style.top) + desktop.button.bounds.height <= 832, 'innerHeight fallback');
    });
    test(volume + ': pointerdown preserves original query through selection loss', () => {
        const app = boot(source); app.show('PostgreSQL');
        assert.equal(app.button.emit('pointerdown').defaultPrevented, true, 'lookup button preserves selection');
        app.clear(); app.document.emit('selectionchange'); app.flush();
        assert.equal(app.button.hidden, false, 'armed action survives native selection loss');
        app.button.emit('click');
        assert.equal(app.searches.length, 1); assert.equal(app.searches[0].query, 'PostgreSQL');
        assert.equal(app.searches[0].origin, app.article);
        assert.equal(app.article.tabIndex, -1, 'article can regain focus when reference closes');
        assert.equal(app.button.hidden, true);
        app.button.emit('click'); assert.equal(app.searches.length, 1, 'saved query cannot repeat');
    });
    test(volume + ': completed lookup clears selection once and rejects detached origin', () => {
        const app = boot(source); app.show('NAT'); app.button.emit('click');
        assert.equal(app.removedRanges, 1); assert.equal(app.searches.length, 1);
        app.show('DNS'); app.article.isConnected = false; app.button.emit('click');
        assert.equal(app.searches.length, 1, 'no stale reference from detached origin');
        assert.equal(app.button.hidden, true);
    });
    test(volume + ': cancellation and outside pointerup release saved action', () => {
        const app = boot(source);
        for (const cancel of [() => app.button.emit('pointercancel'), () => app.document.emit('pointerup', {target: app.paragraph})]) {
            app.show('ARP'); app.button.emit('pointerdown'); app.clear(); cancel(); app.flush();
            assert.equal(app.button.hidden, true);
            app.button.emit('click'); assert.equal(app.searches.length, 0);
        }
    });
    test(volume + ': clearing, Escape, route and blur hide and forget', () => {
        const app = boot(source);
        for (const hide of [
            () => { app.clear(); app.document.emit('selectionchange'); app.flush(); },
            () => app.window.emit('keydown', {key: 'Escape'}),
            () => app.window.emit('hashchange'), () => app.window.emit('blur')
        ]) {
            app.show('ARP'); hide(); assert.equal(app.button.hidden, true);
            app.button.emit('click'); assert.equal(app.searches.length, 0, 'hide clears saved lookup text');
        }
        app.show('ARP');
        app.document.emit('scroll'); app.window.emit('resize'); app.viewport.emit('scroll'); app.viewport.emit('resize');
        assert.equal(app.pending.size, 1, 'reading events coalesce into one animation frame'); app.flush();
    });
    test(volume + ': native copy and keyboard shortcuts remain untouched', () => {
        const app = boot(source); app.show('ss -lntp');
        for (const event of ['copy', 'cut', 'contextmenu']) {
            assert.equal(app.document.listenerCount(event) + app.window.listenerCount(event), 0, event + ' not intercepted');
            const native = app.document.emit(event);
            assert.equal(native.defaultPrevented, false); assert.equal(native.propagationStopped, false);
        }
        for (const properties of [{key: 'c', ctrlKey: true}, {key: 'c', metaKey: true}, {key: 'ArrowRight', shiftKey: true}]) {
            const keyboard = app.window.emit('keydown', properties);
            assert.equal(keyboard.defaultPrevented, false); assert.equal(keyboard.propagationStopped, false);
        }
        assert.equal(app.button.hidden, false); assert.equal(app.removedRanges, 0);
        assert.equal(app.searches.length, 0, 'copying never starts lookup');
    });
    test(volume + ': blur and navigation cancel queued repaint without reopening the action', () => {
        for (const event of ['blur', 'hashchange']) {
            const app = boot(source); app.show('ARP');
            app.document.emit('scroll');
            assert.equal(app.pending.size, 1, 'scroll repaint queued before ' + event);
            app.window.emit(event);
            assert.equal(app.button.hidden, true, event + ' hides immediately');
            assert.equal(app.pending.size, 0, event + ' cancels the obsolete frame');
            app.flush();
            assert.equal(app.button.hidden, true, event + ' stays hidden after queued callbacks settle');
            app.button.emit('click'); assert.equal(app.searches.length, 0, 'no stale query after ' + event);
            app.show('DNS');
            assert.equal(app.button.hidden, false, 'fresh selection still works after ' + event);
        }
    });
    test(volume + ': bridge selects all terms and preserves the reading origin', () => {
        const remembered = [], modes = []; let focused = 0;
        const side = {open: true, classList: {remove(name) { assert.equal(name, 'open'); side.open = false; }}};
        const menu = {setAttribute(name, value) { this[name] = value; }};
        const scope = {
            root: {}, navigation: ['old-command'], termLimit: 5, input: {value: ''},
            termScope: {value: 'bash'}, manualTerms: false, drawer: {hidden: true, scrollTop: 923},
            document: {activeElement: {name: 'keyboard-origin'}, getElementById: id => ({'side-nav': side, menu}[id] || null)},
            rememberOrigin: origin => remembered.push(origin),
            setMode: (...args) => modes.push(args), focusReferenceSearch: () => { focused++; }
        };
        vm.runInNewContext(bridge, scope, {timeout: 1000});
        const origin = {name: 'selected-article'};
        scope.root.LibraryDictionary.searchTerms('ss -lntp', origin);
        assert.equal(scope.input.value, 'ss -lntp', 'query treated as data, letters and flags intact');
        assert.equal(scope.termScope.value, 'all'); assert.equal(scope.manualTerms, true);
        assert.deepEqual(Array.from(scope.navigation), []); assert.equal(scope.termLimit, 80);
        assert.deepEqual(modes[0], ['terms', true]); assert.equal(remembered[0], origin);
        assert.equal(side.open, false); assert.equal(menu['aria-expanded'], 'false');
        assert.equal(scope.drawer.hidden, false); assert.equal(scope.drawer.scrollTop, 0); assert.equal(focused, 1);
        scope.root.LibraryDictionary.searchTerms('WAL');
        assert.equal(remembered[1], scope.document.activeElement, 'direct API keyboard fallback');
    });
    test(volume + ': partial enhancement fails closed without global listeners', () => {
        for (const options of [{noDictionary: true}, {noButton: true}]) {
            const app = boot(source, options);
            assert.equal(app.document.listenerCount('selectionchange'), 0);
            assert.equal(app.window.listenerCount('keydown'), 0); assert.equal(app.button.hidden, true);
        }
    });
}
if (failures.length) {
    for (const failure of failures) console.error(failure);
    throw new Error('Selection reader: ' + failures.length + '/' + cases + ' cases failed');
}
console.log('Selection reader: PASS (' + volumes.length + ' shipped readers, ' + cases + ' event/range/geometry/bridge cases; no browser or packages required)');
