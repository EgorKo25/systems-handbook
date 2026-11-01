'use strict';
// Run after the library build: exercise the JavaScript readers actually receive.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const volumes = JSON.parse(fs.readFileSync(path.join(root, 'published-volumes.json'), 'utf8')).volumes.map(row => row.slug);
const files = ['index.html', ...volumes.map(name => `${name}/index.html`), 'labs-personal/index.html'];
const names = ['bg', 'paper', 'soft', 'text', 'muted', 'line', 'accent', 'code', 'code-text', 'shadow'];
const presetIds = ['paper', 'night', 'white', 'black', 'sepia', 'graphite', 'midnight', 'forest'];
const themeKey = 'library-theme-v1', appearanceKey = 'library-reader-appearance-v1', presetKey = 'library-reader-preset-v1';
const oldHomeKey = 'library-home-theme-v1';
const shell = fs.readFileSync(path.join(root, 'cache/sources/reader-shell.html'), 'utf8');
const declarations = css => Object.fromEntries([...css.matchAll(/--([a-z-]+):([^;]+);/g)].map(match => [match[1], match[2]]));
const light = declarations(shell.match(/:root\{([^}]+)\}/)[1]);
const defaults = {light, dark: {...light, ...declarations(shell.match(/:root\[data-theme=dark\]\{([^}]+)\}/)[1])}};
// Existing 100% warmth endpoints: new presets must not recolour these readers.
const originalWarm = {
    paper: {bg:'#f4ecde',paper:'#fff7e9',soft:'#eee4d0',text:'#302c25',muted:'#70634f',line:'#ddd1bd',accent:'#79603b',code:'#2b2822','code-text':'#f3ead9',shadow:'0 12px 40px #24180e1c'},
    night: {bg:'#24211d',paper:'#2d2923',soft:'#3a332a',text:'#eee7d9',muted:'#c2b8a8',line:'#51483c',accent:'#d8be8b',code:'#191714','code-text':'#ece5d8',shadow:'0 12px 40px #130f092e'}
};
const plain = value => JSON.parse(JSON.stringify(value));

function boot(source, storage = new Map(), blocked = false) {
    const values = new Map(), listeners = new Map();
    const document = {
        documentElement: {dataset: {}, style: {setProperty: (key, value) => values.set(key, value)}},
        getElementById: () => null, readyState: 'complete'
    };
    const window = {addEventListener: (event, callback) => listeners.set(event, callback)};
    const localStorage = {
        getItem: key => {if (blocked) throw new Error('Storage unavailable'); return storage.get(key) ?? null;},
        setItem: (key, value) => {if (blocked) throw new Error('Storage unavailable'); storage.set(key, value);}
    };
    vm.runInNewContext(source, {document, window, localStorage}, {timeout: 1000});
    return {
        api: window.LibraryPreferences,
        get: name => values.get(`--reader-${name}`),
        palette: () => names.map(name => values.get(`--reader-${name}`)),
        event: (key, newValue = storage.get(key) ?? null) => listeners.get('storage')({key, newValue}),
        pageshow: () => listeners.get('pageshow')()
    };
}

function rgb(colour) {
    return colour.startsWith('#')
        ? colour.slice(1, 7).match(/../g).map(part => parseInt(part, 16))
        : colour.match(/[\d.]+/g).slice(0, 3).map(Number);
}
function luminance(colour) {
    return rgb(colour).reduce((sum, channel, index) => {
        const value = channel / 255;
        return sum + (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4) * [0.2126, 0.7152, 0.0722][index];
    }, 0);
}
function contrast(a, b) {
    const [lo, hi] = [luminance(a), luminance(b)].sort((a, b) => a - b);
    return (hi + 0.05) / (lo + 0.05);
}

const notes = new Map(volumes.map(name => [`${name === 'networks' ? 'network' : name}-book-v1`, JSON.stringify({theme: 'dark', size: 21, notes: {chapter: `Заметка: ${name}`}})]));
const sharedStorage = new Map(notes);
sharedStorage.set(themeKey, 'light');
sharedStorage.set(presetKey, 'sepia');
for (const file of files) {
    const html = fs.readFileSync(path.join(root, file), 'utf8');
    const matches = [...html.matchAll(/<script\b[^>]*id="library-preferences-bootstrap-v1"[^>]*>([\s\S]*?)<\/script>/g)];
    assert.equal(matches.length, 1, `${file}: one actual preferences bootstrap`);
    const source = matches[0][1], reader = boot(source, sharedStorage);
    assert.equal(reader.api.selectedTheme, 'sepia', `${file}: preset inherited from another volume`);
    assert.deepEqual(plain(reader.api.themes.map(item => item.id)), presetIds, `${file}: complete preset catalogue`);
    for (const preset of reader.api.themes) {
        assert.ok(preset.name && preset.description, `${file}: ${preset.id} has a readable label and description`);
        assert.ok(['light', 'dark'].includes(preset.mode), `${file}: ${preset.id} exposes its mode`);
        assert.equal(preset.supportsWarmth, true, `${file}: ${preset.id} supports warmth`);
        reader.api.setPreset(preset.id);
        assert.equal(reader.api.selectedTheme, preset.id);
        assert.equal(reader.api.theme, preset.mode);
        let neutral;
        for (const warmth of Array.from({length: 21}, (_, index) => index * 5)) {
            const label = `${file}: ${preset.id}/${warmth}`;
            reader.api.setAppearance({warmth});
            for (const name of names) assert.ok(reader.get(name), `${label} missing ${name}`);
            assert.equal(reader.get('page'), reader.get('bg'), `${label} background compatibility`);
            for (const surface of ['bg', 'paper', 'soft']) {
                for (const ink of ['text', 'muted']) assert.ok(contrast(reader.get(ink), reader.get(surface)) >= 4.5, `${label} ${ink}/${surface} readability`);
                assert.ok(contrast(reader.get('accent'), reader.get(surface)) >= 4.5, `${label} accent/${surface} link readability`);
            }
            assert.ok(contrast(reader.get('code-text'), reader.get('code')) >= 4.5, `${label} code readability`);
            if (warmth === 0) {
                neutral = reader.palette();
                for (const name of ['bg', 'paper', 'text', 'accent']) assert.equal(reader.get(name), preset.preview[name], `${label} preview matches actual palette`);
            }
            if (warmth === 100) for (const name of ['bg', 'paper', 'soft', 'accent']) assert.notEqual(reader.get(name), neutral[names.indexOf(name)], `${label} ${name} participates in warmth`);
            if (warmth === 100 && originalWarm[preset.id]) for (const name of names) assert.equal(reader.get(name), originalWarm[preset.id][name], `${label} original warmth endpoint retained`);
            if (warmth === 0 && ['white', 'black'].includes(preset.id)) {
                const dark = preset.id === 'black';
                for (const name of ['bg', 'paper']) assert.deepEqual(rgb(reader.get(name)), dark ? [0, 0, 0] : [255, 255, 255], `${label} exact ${name}`);
                assert.deepEqual(rgb(reader.get('text')), dark ? [255, 255, 255] : [0, 0, 0], `${label} exact text`);
                for (const name of names.filter(name => name !== 'shadow')) assert.equal(new Set(rgb(reader.get(name))).size, 1, `${label} ${name} has no colour cast`);
            }
        }
        reader.api.setAppearance({warmth: 0});
        assert.deepEqual(reader.palette(), neutral, `${file}: ${preset.id} restores its neutral palette`);
        if (['paper', 'night'].includes(preset.id)) for (const name of names) assert.equal(reader.get(name), defaults[preset.mode][name], `${file}: original ${preset.mode} ${name} retained`);
    }
    reader.api.setAppearance({font: 'palatino', warmth: 75, size: 24});
    reader.api.setPreset('sepia');
    const reopened = boot(source, sharedStorage);
    assert.equal(reopened.api.selectedTheme, 'sepia', `${file}: shared preset persists across pages`);
    assert.deepEqual(plain(reopened.api.appearance), {font: 'palatino', warmth: 75, size: 24}, `${file}: appearance survives preset selection`);
    for (const invalid of ['missing', '', null, undefined, {}, ['paper']]) {
        const before = reopened.palette();
        reopened.api.setPreset(invalid);
        assert.equal(reopened.api.selectedTheme, 'sepia', `${file}: invalid preset ignored`);
        assert.deepEqual(reopened.palette(), before, `${file}: invalid preset does not repaint`);
    }
    for (const order of [[presetKey, themeKey], [themeKey, presetKey]]) {
        reader.api.setPreset('night');
        reopened.event(presetKey);
        reopened.event(themeKey);
        reader.api.setPreset('sepia');
        for (const key of order) reopened.event(key);
        assert.equal(reopened.api.selectedTheme, 'sepia', `${file}: both cross-tab event orders converge`);
        assert.equal(reopened.api.theme, 'light');
    }
    reader.api.setAppearance({warmth: 0});
    reopened.event(appearanceKey);
    assert.equal(reopened.api.appearance.warmth, 0, `${file}: cross-tab appearance updates`);
    for (const mode of ['light', 'dark']) {
        const expected = mode === 'light' ? 'paper' : 'night';
        assert.equal(boot(source, new Map([[themeKey, mode]])).api.selectedTheme, expected, `${file}: legacy shared theme migration`);
        assert.equal(boot(source, new Map([[oldHomeKey, mode]])).api.selectedTheme, expected, `${file}: legacy home theme migration`);
        const bookKey = ['index.html', 'labs-personal/index.html'].includes(file) ? null : `${file.startsWith('networks/') ? 'network' : file.split('/')[0]}-book-v1`;
        if (bookKey) assert.equal(boot(source, new Map([[bookKey, JSON.stringify({theme: mode, notes: {saved: 'Keep me'}})]])).api.selectedTheme, expected, `${file}: legacy book theme migration`);
        assert.equal(boot(source, new Map([[presetKey, mode === 'light' ? 'night' : 'paper'], [themeKey, mode]])).api.selectedTheme, expected, `${file}: existing binary preference wins incompatible preset`);
        reopened.api.setTheme(mode);
        assert.equal(reopened.api.selectedTheme, expected, `${file}: legacy toggle remains usable`);
    }
    const damaged = boot(source, new Map([[presetKey, '{bad'], [appearanceKey, '{bad'], [themeKey, 'unknown'], [oldHomeKey, 'unknown']]));
    assert.equal(damaged.api.selectedTheme, 'night', `${file}: corrupt storage uses safe default`);
    assert.deepEqual(plain(damaged.api.appearance), {font: 'book', warmth: 0, size: null});
    const unavailable = boot(source, new Map(), true);
    unavailable.api.setPreset('white');
    unavailable.api.setAppearance({warmth: 85, size: 23});
    assert.equal(unavailable.api.selectedTheme, 'white', `${file}: in-memory settings without storage`);
    assert.equal(unavailable.api.appearance.warmth, 85);
    unavailable.pageshow();
    assert.equal(unavailable.api.selectedTheme, 'white', `${file}: restored tab retains in-memory preset without storage`);
    assert.equal(unavailable.api.appearance.warmth, 85);
    for (const [key, value] of notes) assert.equal(sharedStorage.get(key), value, `${file}: existing notes and book state untouched`);
    reader.api.setPreset('sepia');
}
console.log(`Reader palette: PASS (${files.length} pages; 8 presets × all 21 warmth steps; contrast, monochrome, restoration, migration, shared storage and notes)`);
