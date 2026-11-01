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
    // Commas separate aliases only before another option and outside operand
    // notation. A comma in <key,value>, N[SUFFIX], or a literal value survives.
    // Slash-separated entries remain independent: kill's -l [NUMBER] / -L do
    // not share arity. Comma aliases can share a trailing operand declaration.
    const text = String(label), groups = [[]], brackets = [];
    const closing = {'<':'>','[':']','(':')','{':'}'};
    let start = 0, quote = null;
    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        if (char === '\\') { i++; continue; }
        if (quote) { if (char === quote) quote = null; continue; }
        if (char === '"' || char === "'") { quote = char; continue; }
        if (closing[char]) { brackets.push(closing[char]); continue; }
        if (brackets.length && char === brackets[brackets.length - 1]) { brackets.pop(); continue; }
        if (brackets.length) continue;
        const comma = char === ',' && /^\s*[+-]{1,2}(?:[A-Za-z0-9_]|[%+])/.test(text.slice(i + 1));
        const slash = char === '/' && /\s/.test(text[i - 1] || '') && /\s/.test(text[i + 1] || '');
        if (!comma && !slash) continue;
        groups[groups.length - 1].push(text.slice(start,i)); start = i + 1;
        if (slash) groups.push([]);
    }
    groups[groups.length - 1].push(text.slice(start));
    const forms = [];
    for (const alternatives of groups) {
        const group = [];
        for (const alternative of alternatives) {
            const expression = /(?:^|\s)([+-]{1,2}(?:[A-Za-z0-9_][A-Za-z0-9_-]*|[%+]))(?:=([^\s]+))?/g;
            const match = expression.exec(alternative);
            if (!match) continue;
            const tail = alternative.slice(expression.lastIndex).trim().split(/\s+/)[0] || '';
            const operand = match[2] !== undefined ? match[2] : tail;
            const expectsValue = match[2] !== undefined || (!!tail && !/^[+-]/.test(tail));
            const qualifier = match[2] === undefined && /^[a-z][a-z0-9_-]*$/.test(operand) ? operand : null;
            group.push({name:match[1],expectsValue,qualifier});
        }
        // -f, --values <FILE> declares one operand for both spellings. Preserve
        // explicit fixed variants such as -o yaml, -o json rather than replacing
        // their qualifiers with a single flat specification.
        const shared = group.find(form => form.expectsValue);
        for (const form of group) forms.push(shared && !form.expectsValue
            ? {...form,expectsValue:true,qualifier:shared.qualifier} : form);
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
// CPython 3.12 interface lexer only: never executes code or expands shell text.
// -c/-m consume one argument and end interpreter option parsing; a filename,
// directory/zip, '-' or '--' also separates the program's argv.
function pythonInterface(tokens) {
    if (tokens[0] !== 'python3') return null;
    const options = [], noValue = 'bBdEhiIOPqRsStuvVx?';
    let version = false;
    const finish = (mode,start,target=null,targetIndex=null) => ({
        mode:version && mode !== 'invalid' ? 'version' : mode,
        options, start, target, targetIndex, args:tokens.slice(start)
    });
    for (let i=1;i<tokens.length;i++) {
        const token=tokens[i];
        if (token==='--') {
            if(i+1===tokens.length)return finish('stdin',i+1);
            return finish(tokens[i+1]==='-'?'stdin':'script',i+2,tokens[i+1],i+1);
        }
        if (token==='-' || !token.startsWith('-') || token==='')
            return finish(token==='-'?'stdin':'script',i+1,token,i);
        if(token.startsWith('--')) {
            const option={name:token,hasValue:false};options.push(option);
            if(['--help','--help-env','--help-xoptions','--help-all'].includes(token))return finish('help',i+1);
            if(token==='--version'){version=true;continue;}
            if(token==='--check-hash-based-pycs' && i+1<tokens.length) {
                option.value=tokens[++i];option.hasValue=true;
                if(['always','default','never'].includes(option.value))continue;
            }
            return finish('invalid',i+1);
        }
        for(let j=1;j<token.length;j++) {
            const name='-'+token[j], option={name,hasValue:false};options.push(option);
            if('cmWX'.includes(token[j])) {
                const attached=token.slice(j+1), targetIndex=attached?i:i+1;
                if(attached){option.value=attached;option.hasValue=true;option.attached=true;}
                else if(i+1<tokens.length){option.value=tokens[++i];option.hasValue=true;}
                else return finish('invalid',i+1);
                if(name==='-c' || name==='-m')return finish(name==='-c'?'command':'module',i+1,option.value,targetIndex);
                break;
            }
            if(!noValue.includes(token[j]))return finish('invalid',i+1);
            if(name==='-h' || name==='-?')return finish('help',i+1);
            if(name==='-V')version=true;
        }
    }
    return finish('stdin',tokens.length);
}
function commandMatch(command, tokens) {
    const python=pythonInterface(tokens), canonical=tokenizeQuery(command.name);
    if(python && canonical[0]==='python3' && canonical.length>1) {
        if(canonical[1]==='-m') {
            if(python.mode!=='module' || python.target!==canonical[2])return {prefix:0,depth:0,indices:[],segments:[]};
            // Named module cards already contain the selector; module options
            // start after its operand, even with -Bm or -munittest spelling.
            let cursor=python.start;
            for(const word of canonical.slice(3))if(tokens[cursor++]!==word)return {prefix:0,depth:0,indices:[],segments:[]};
            return {prefix:cursor,depth:canonical.length,indices:[0],segments:[],python};
        }
        // A named script/helper card cannot be selected from -c/-m program argv.
        const scripts=[command.name,...(command.aliases || [])].map(tokenizeQuery)
            .filter(parts=>parts[0]==='python3' && parts[1] && !isOption(parts[1])).map(parts=>parts[1]);
        if(scripts.length && (python.mode!=='script' || !scripts.includes(python.target)))
            return {prefix:0,depth:0,indices:[],segments:[]};
    }
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
    const python=explicit && tokens[0]==='python3' && (command.name==='python3' || match.python) ? pythonInterface(tokens) : null;
    if (sharedParsed) parsed=sharedParsed;
    else if(python) {
        const root=command.name==='python3';
        const interpreter=python.options.filter(option=>root || option.name!=='-m');
        for(const option of interpreter)optionScopes.set(option,optionSpecifications(command,'python3'));
        const local=root ? {options:[],words:python.targetIndex!==null && ['script','stdin'].includes(python.mode)
            ? [python.target,...python.args] : python.args}
            : parseOptions(tokens.slice(match.prefix),specifications);
        parsed={options:[...interpreter,...local.options],words:local.words};
    }
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
    return {explicit,options:parsed.options,words:parsed.words,matchedIndices:[...matched].sort((a,b)=>a-b),unmatched,wordsMatch,...(python?{interfaceMode:python.mode,programArgs:python.args}: {})};
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
