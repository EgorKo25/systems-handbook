// Pure reference-query parser. It never executes or expands shell input.
function tokenizeQuery(value) {
    const tokens = [];
    let token = '', started = false, quote = null;
    const text = String(value);
    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        // Bash removes an escaped line ending before splitting words, including
        // inside double quotes. Single quotes retain both bytes literally.
        if (char === '\\' && quote !== "'") {
            if (text[i + 1] === '\n') { i++; continue; }
            if (text[i + 1] === '\r' && text[i + 2] === '\n') { i += 2; continue; }
        }
        if (quote) {
            if (char === quote) quote = null;
            else if (char === '\\' && quote === '"' && i + 1 < text.length && /["\\$`]/.test(text[i + 1])) token += text[++i];
            else token += char;
        } else if (char === '"' || char === "'") {
            quote = char; started = true;
        } else if (/\s/.test(char)) {
            if (started) tokens.push(token);
            token = ''; started = false;
        } else if (char === '\\' && i + 1 < text.length) {
            token += text[++i]; started = true;
        } else { token += char; started = true; }
    }
    if (started) tokens.push(token);
    return tokens;
}
function flagForms(label) {
    const forms = [];
    for (const alternative of String(label).split(/\s+\/\s+/)) {
        const expression = /(?:^|\s)([+-]{1,2}(?:[A-Za-z0-9_][A-Za-z0-9_-]*|[%+]))(?:=([^\s]+))?/g;
        const match = expression.exec(alternative);
        if (match) {
            const tail = alternative.slice(expression.lastIndex).trim().split(/\s+/)[0] || '';
            const operand = match[2] !== undefined ? match[2] : tail;
            const expectsValue = match[2] !== undefined || (!!tail && !/^[+-]/.test(tail));
            const qualifier = match[2] === undefined && /^[a-z][a-z0-9_-]*$/.test(operand) ? operand : null;
            forms.push({name: match[1], expectsValue, qualifier});
        }
    }
    return forms;
}
function optionSpecifications(command, scope = command.name) {
    const flags = command.flags || [], specifications = new Map();
    const scoped = Array.isArray(command.flagScopes) && command.flagScopes.length === flags.length;
    let owners;
    if (scoped) {
        owners = [...new Set(command.flagScopes.filter(owner => owner === scope ||
            !(command.parentOptions === 'prefix-only' && scope === command.name) &&
            (command.persistentScopes || []).includes(owner) && String(scope).startsWith(owner + ' ')))];
        owners.sort((a,b) => a.split(' ').length - b.split(' ').length);
    } else owners = [scope];
    for (const owner of owners) {
        const local = new Map();
        flags.forEach((flag, index) => {
            if (scoped ? command.flagScopes[index] !== owner : scope !== command.name && !(command.prefixFlags?.[scope] || []).includes(flag.flag)) return;
            for (const form of flagForms(flag.flag)) {
                const specification = local.get(form.name) || {expectsValue:false, forms:[]};
                specification.expectsValue ||= form.expectsValue;
                specification.forms.push({...form,index});
                local.set(form.name,specification);
            }
        });
        // Only occurrences within one scope share arity. A child can shadow a
        // parent's short name while the parent's other long spelling survives.
        for (const [name,specification] of local) specifications.set(name,specification);
    }
    return specifications;
}
function isOption(token) { return /^[+-][^\s]/.test(token) && token !== '--'; }
function matchesCommand(command, name) {
    return [command.name,...(command.aliases || [])].some(value => normalizeText(value) === normalizeText(name));
}
function prefixOptionSpan(tokens, start, specifications) {
    const token = tokens[start] || '';
    if (!isOption(token)) return 0;
    const equals = token.indexOf('='), name = equals > 0 ? token.slice(0,equals) : token;
    const direct = specifications.get(name);
    const operand = () => start + 1 < tokens.length && tokens[start + 1] !== '--' ? 2 : 0;
    if (direct) return equals > 0 || !direct.expectsValue ? 1 : operand();
    if (token.startsWith('--') || token.length < 3) return 0;
    for (let i = 1; i < token.length; i++) {
        const specification = specifications.get(token[0] + token[i]);
        if (!specification) return 0;
        if (specification.expectsValue) return i + 1 < token.length ? 1 : operand();
    }
    return 1;
}
function prefixScope(command, parts, count) {
    const actual = parts.slice(0,count).join(' ');
    if (Object.prototype.hasOwnProperty.call(command.prefixFlags || {},actual)) return actual;
    // An alias can change the executable spelling or add a namespace word.
    // Fall back only to declared canonical parent scopes, never to local flags.
    const canonical = tokenizeQuery(command.name);
    for (let n = Math.min(count,canonical.length - 1); n > 0; n--) {
        const parent = canonical.slice(0,n).join(' ');
        if (Object.prototype.hasOwnProperty.call(command.prefixFlags || {},parent)) return parent;
    }
    return actual;
}
function commandMatch(command, tokens) {
    let best = {prefix:0, depth:0, indices:[], segments:[]};
    for (const name of [command.name,...(command.aliases || [])]) {
        const parts = tokenizeQuery(name);
        if (!parts.length || normalizeText(parts[0]) !== normalizeText(tokens[0] || '')) continue;
        let cursor = 0, valid = true;
        const indices = [], segments = [];
        for (let part = 0; part < parts.length; part++) {
            const scope = prefixScope(command,parts,part);
            const specifications = optionSpecifications(command,scope);
            while (part && !isOption(parts[part - 1]) && normalizeText(tokens[cursor] || '') !== normalizeText(parts[part])) {
                const span = prefixOptionSpan(tokens,cursor,specifications);
                if (!span) { valid = false; break; }
                segments.push({start:cursor,span,scope}); cursor += span;
            }
            if (!valid || normalizeText(tokens[cursor] || '') !== normalizeText(parts[part])) { valid = false; break; }
            indices.push(cursor++);
        }
        if (valid && (parts.length > best.depth || parts.length === best.depth && cursor > best.prefix)) best = {prefix:cursor,depth:parts.length,indices,segments};
    }
    return best;
}
function commandPrefix(command,tokens) { return commandMatch(command,tokens).prefix; }
function parseOptions(tokens, specifications, settings = {}) {
    const options = [], words = [];
    const hasSingleDashLongNames = !settings.allowClusters && [...specifications.keys()].some(name => /^-[^-].{1,}$/.test(name));
    for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        if (token === '--') { words.push(...tokens.slice(i + 1)); break; }
        if (!isOption(token)) {
            if (settings.stopAtOperand) { words.push(...tokens.slice(i)); break; }
            words.push(token); continue;
        }
        const equals = token.indexOf('='), wholeName = equals > 0 ? token.slice(0,equals) : token;
        const direct = specifications.get(wholeName);
        if (token.startsWith('--') || direct || hasSingleDashLongNames || token.length === 2) {
            let value, hasValue = equals > 0;
            if (hasValue) value = token.slice(equals + 1);
            else if (direct?.expectsValue && i + 1 < tokens.length && (!settings.rejectOptionValues || !isOption(tokens[i + 1]))) { value = tokens[++i]; hasValue = true; }
            options.push({name:wholeName,value,hasValue,equals:equals > 0}); continue;
        }
        for (let j = 1; j < token.length; j++) {
            const name = token[0] + token[j], suffix = token.slice(j + 1);
            let value, hasValue = false;
            const suffixIsFlags = settings.preferKnownFlags && suffix && [...suffix].every(char => specifications.has(token[0] + char));
            if (specifications.get(name)?.expectsValue && !suffixIsFlags) {
                if (j + 1 < token.length) { value = token.slice(j + 1); hasValue = true; }
                else if (i + 1 < tokens.length && (!settings.rejectOptionValues || !isOption(tokens[i + 1]))) { value = tokens[++i]; hasValue = true; }
                options.push({name,value,hasValue,attached:j + 1 < token.length}); break;
            }
            options.push({name,value,hasValue});
        }
    }
    return {options,words};
}
function fixedForm(label) {
    const first = String(label).split(/\s+\/\s+/)[0];
    if (/^[+%-]|^\[/.test(first)) return [];
    const result=[];
    for (const word of tokenizeQuery(first)) { if (!/^[a-z][a-z0-9_-]*$/.test(word)) break; result.push(word); }
    return result;
}
function analyzeQuery(command, query, sharedParsed = null) {
    const tokens = tokenizeQuery(query), match = commandMatch(command,tokens), explicit = match.prefix > 0;
    const specifications = optionSpecifications(command), optionScopes = new Map();
    let parsed;
    if (sharedParsed) parsed=sharedParsed;
    else {
        parsed={options:[],words:[]};
        if (explicit) for (const segment of match.segments) {
            const scope = optionSpecifications(command,segment.scope);
            const prefix = parseOptions(tokens.slice(segment.start,segment.start + segment.span),scope);
            for (const option of prefix.options) optionScopes.set(option,scope);
            parsed.options.push(...prefix.options);
        }
        const local=parseOptions(explicit ? tokens.slice(match.prefix) : tokens,specifications,
                                {stopAtOperand:command.optionBoundary === 'first-operand'});
        parsed.options.push(...local.options); parsed.words=local.words;
    }
    const matched=new Set(), unmatched=[];
    for (const option of parsed.options) {
        const specification=(optionScopes.get(option) || specifications).get(option.name);
        const forms=(sharedParsed && option.hasValue && !specification?.expectsValue ? [] : specification?.forms || [])
            .filter(form => !form.qualifier || !option.hasValue || option.value === form.qualifier);
        if (!forms.length) unmatched.push(option);
        for (const form of forms) matched.add(form.index);
    }
    command.flags.forEach((flag,index) => { const words=fixedForm(flag.flag); if (words.length && words.every((word,i) => parsed.words[i] === word)) matched.add(index); });
    const searchable=normalizeText([command.name,...(command.aliases || []),command.purpose,command.syntax,
                                   ...command.flags.flatMap(flag => [flag.flag,flag.action,flag.when])].join(' '));
    const wordsMatch=parsed.words.every(word => searchable.includes(normalizeText(word)));
    return {explicit,options:parsed.options,words:parsed.words,matchedIndices:[...matched].sort((a,b)=>a-b),unmatched,wordsMatch};
}
function searchCommands(commands, query) {
    const tokens=tokenizeQuery(query);
    const candidates=commands.map(command => ({command,match:commandMatch(command,tokens)})).filter(item => item.match.prefix);
    candidates.sort((a,b)=>b.match.depth-a.match.depth || b.match.prefix-a.match.prefix);
    const exact=candidates[0]?.command || null;
    let sharedParsed=null;
    if (!exact) {
        const union=new Map();
        for (const command of commands) for (const [name,specification] of optionSpecifications(command)) {
            const existing=union.get(name) || {expectsValue:false};
            existing.expectsValue ||= specification.expectsValue; union.set(name,existing);
        }
        sharedParsed=parseOptions(tokens,union,{allowClusters:true,preferKnownFlags:true,rejectOptionValues:true});
    }
    return (exact ? [exact] : commands).map(command => ({command,analysis:analyzeQuery(command,query,sharedParsed)}))
        .filter(result => exact || !result.analysis.unmatched.length && result.analysis.wordsMatch);
}
function optionText(option) {
    const value=!option.hasValue ? '' : option.value === '' ? "''" : /\s/.test(option.value) ? JSON.stringify(option.value) : option.value;
    return option.name+(option.hasValue ? (option.equals || option.name.startsWith('--') ? '=' : option.attached ? '' : ' ')+value : '');
}
function queryForCommand(command, query) {
    const analysis=analyzeQuery(command,query);
    if (analysis.explicit) return String(query).trim();
    const form=analysis.matchedIndices.map(index=>fixedForm(command.flags[index].flag)).filter(words=>words.length).sort((a,b)=>b.length-a.length)[0] || [];
    return command.name+(form.length ? ' '+form.join(' ') : '')+(analysis.options.length ? ' '+analysis.options.map(optionText).join(' ') : '');
}
function queryFromCode(command, followingText) {
    const text=String(followingText).slice(0,4096);
    let quote=null, escaped=false, end=text.length;
    for (let i=0;i<text.length;i++) {
        const c=text[i];
        if (escaped) { escaped=false; continue; }
        if (c==='\\' && quote!=="'") {
            if (text[i+1]==='\r' && text[i+2]==='\n') { i+=2; continue; }
            escaped=true; continue;
        }
        if (quote) { if(c===quote)quote=null; continue; }
        if (c==='"' || c==="'") { quote=c; continue; }
        if ('\r\n|;&'.includes(c)) { end=i; break; }
    }
    return (command.name+' '+text.slice(0,end)).trimEnd();
}
