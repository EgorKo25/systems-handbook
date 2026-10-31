'use strict';
// Run after the library build: exercise the JavaScript readers will actually run.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const volumes = ['networks', 'linux', 'bash', 'postgres', 'cache', 'git', 'go', 'jenkins'];
const files = ['index.html', ...volumes.map(name => `${name}/index.html`)];
const names = ['bg', 'paper', 'soft', 'text', 'muted', 'line', 'accent', 'code', 'code-text', 'shadow'];
const themeKey = 'library-theme-v1', appearanceKey = 'library-reader-appearance-v1';
const shell = fs.readFileSync(path.join(root, 'cache/sources/reader-shell.html'), 'utf8');
const declarations = css => Object.fromEntries([...css.matchAll(/--([a-z-]+):([^;]+);/g)].map(match => [match[1], match[2]]));
const light = declarations(shell.match(/:root\{([^}]+)\}/)[1]);
const defaults = {light, dark: {...light, ...declarations(shell.match(/:root\[data-theme=dark\]\{([^}]+)\}/)[1])}};

function boot(source, storage) {
    const values = new Map(), listeners = new Map();
    const document = {
        documentElement: {dataset: {}, style: {setProperty: (key, value) => values.set(key, value)}},
        getElementById: () => null, readyState: 'complete'
    };
    const window = {addEventListener: (event, callback) => listeners.set(event, callback)};
    const localStorage = {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value)};
    vm.runInNewContext(source, {document, window, localStorage}, {timeout: 1000});
    return {api: window.LibraryPreferences, get: name => values.get(`--reader-${name}`), listeners};
}

function luminance(colour) {
    const rgb = colour.startsWith('#')
        ? colour.slice(1, 7).match(/../g).map(part => parseInt(part, 16))
        : colour.match(/[\d.]+/g).slice(0, 3).map(Number);
    return rgb.reduce((sum, channel, index) => {
        const value = channel / 255;
        return sum + (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4) * [0.2126, 0.7152, 0.0722][index];
    }, 0);
}
function contrast(a, b) {
    const [lo, hi] = [luminance(a), luminance(b)].sort((a, b) => a - b);
    return (hi + 0.05) / (lo + 0.05);
}

const notes = new Map(volumes.map(name => [`${name}-book-v1`, JSON.stringify({theme: 'dark', size: 21, notes: {chapter: `Заметка: ${name}`}})]));
const storage = new Map(notes);
for (const file of files) {
    const html = fs.readFileSync(path.join(root, file), 'utf8');
    const matches = [...html.matchAll(/<script\b[^>]*id="library-preferences-bootstrap-v1"[^>]*>([\s\S]*?)<\/script>/g)];
    assert.equal(matches.length, 1, `${file}: one actual preferences bootstrap`);
    const source = matches[0][1], reader = boot(source, storage);
    for (const theme of ['light', 'dark']) {
        reader.api.setTheme(theme);
        for (const warmth of [0, 50, 100]) {
            reader.api.setAppearance({warmth});
            for (const name of names) assert.ok(reader.get(name), `${file}: ${theme}/${warmth} missing ${name}`);
            assert.equal(reader.get('page'), reader.get('bg'), `${file}: background compatibility`);
            for (const surface of ['bg', 'paper', 'soft']) {
                for (const ink of ['text', 'muted']) assert.ok(contrast(reader.get(ink), reader.get(surface)) >= 4.5, `${file}: ${theme}/${warmth} ${ink}/${surface} readability`);
                assert.ok(contrast(reader.get('accent'), reader.get(surface)) >= 3, `${file}: ${theme}/${warmth} accent/${surface} UI contrast`);
            }
            assert.ok(contrast(reader.get('code-text'), reader.get('code')) >= 4.5, `${file}: code readability`);
            if (warmth === 100) for (const name of ['bg', 'paper', 'soft', 'accent']) assert.notEqual(reader.get(name), defaults[theme][name], `${file}: ${name} participates in warmth`);
        }
        // The neutral reference comes from the original CSS, not the generator.
        reader.api.setAppearance({warmth: 0});
        for (const name of names) assert.equal(reader.get(name), defaults[theme][name], `${file}: ${theme} restores neutral ${name} after 100%`);
    }
    reader.api.setAppearance({font: 'palatino', warmth: 75, size: 24});
    reader.api.setTheme('light');
    const reopened = boot(source, storage);
    assert.equal(reopened.api.theme, 'light', `${file}: persisted shared theme`);
    assert.deepEqual(JSON.parse(JSON.stringify(reopened.api.appearance)), {font: 'palatino', warmth: 75, size: 24}, `${file}: persisted appearance`);
    reader.api.setTheme('dark');
    reopened.listeners.get('storage')({key: themeKey, newValue: storage.get(themeKey)});
    assert.equal(reopened.api.theme, 'dark', `${file}: another tab updates theme`);
    reader.api.setAppearance({warmth: 0});
    reopened.listeners.get('storage')({key: appearanceKey, newValue: storage.get(appearanceKey)});
    assert.equal(reopened.api.appearance.warmth, 0, `${file}: another tab updates appearance`);
    for (const [key, value] of notes) assert.equal(storage.get(key), value, `${file}: existing notes and book state remain untouched`);
}
console.log(`Reader palette: PASS (${files.length} pages; light/dark × 0/50/100%; neutral restoration, contrast, shared preferences and notes)`);
