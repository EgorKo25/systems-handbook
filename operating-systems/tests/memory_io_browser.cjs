'use strict';
// DOM binding harness for actual shipped inline scripts. Not a browser/render test.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../labs/memory-io/index.html'),'utf8');
const models=fs.readFileSync(path.join(__dirname,'../labs/memory-io/models.js'),'utf8');
const inline=Array.from(html.matchAll(/<script>([\s\S]*?)<\/script>/g),m=>m[1]).join('\n');
const KEY='os-memory-io-lab-v1',THEME='library-theme-v1',PRESET='library-reader-preset-v1',APPEARANCE='library-reader-appearance-v1';
const READ_KEYS=new Set([KEY,THEME,PRESET,APPEARANCE]);let checks=0;
class Element {
 constructor(attrs={}){Object.assign(this,attrs);this.value=attrs.value??'';this.textContent='';this.children=[];this.events={};this.elements={};this.dataset={};}
 append(x){this.children.push(x);if(this.tag==='select'&&this.children.length===1)this.value=String(x.value);}
 replaceChildren(){this.children=[];if(this.tag==='select')this.value='';}
 addEventListener(name,fn){this.events[name]=fn;}
 fire(name){assert.equal(typeof this.events[name],'function','bound '+name);this.events[name]({preventDefault(){}});}
}
function attrs(source){return Object.fromEntries(Array.from(source.matchAll(/([\w-]+)="([^"]*)"/g),m=>[m[1],m[2]]));}
function boot(stored=null,blocked=false,preferences={},search=''){
 const ids={},buttons=[];for(const match of html.matchAll(/<(\w+)\b([^>]*)>/g)){const a=attrs(match[2]),e=new Element({...a,tag:match[1]});if(a.id)ids[a.id]=e;if(a['data-action']){e.dataset.action=a['data-action'];buttons.push(e);}}
 for(const match of html.matchAll(/<form\b([^>]*)>([\s\S]*?)<\/form>/g)){
 const a=attrs(match[1]),form=ids[a.id];
 for(const input of match[2].matchAll(/<(input)\b([^>]*)>|<(select)\b([^>]*)>([\s\S]*?)<\/select>/g)){
 const tag=input[1]??input[3],x=attrs(input[2]??input[4]),e=x.id?ids[x.id]:new Element({...x,tag});
 if(tag==='select'){const options=Array.from(input[5].matchAll(/<option([^>]*)>(.*?)<\/option>/g));const picked=options.find(o=>o[1].includes('selected'))??options[0];if(picked)e.value=attrs(picked[1]).value??picked[2];}
 form.elements[x.name]=e;
 }}
 ids.release.elements.base=ids['release-base'];
 const data=new Map(Object.entries(preferences)),access=[],style=new Map(),windowEvents={};if(stored!==null)data.set(KEY,stored);
 const root={dataset:{},style:{setProperty(key,value){style.set(key,value);}}};
 const context={document:{documentElement:root,getElementById(id){assert.ok(ids[id],'actual HTML id '+id);return ids[id];},querySelectorAll(selector){assert.equal(selector,'[data-action]');return buttons;},createElement(tag){return new Element({tag});}},localStorage:{getItem(key){assert.ok(READ_KEYS.has(key),'only model or shared scalar read: '+key);access.push(['get',key]);if(blocked)throw Error('blocked');return data.get(key)??null;},setItem(key,value){assert.equal(key,KEY,'only own model storage may be written');access.push(['set',key]);if(blocked)throw Error('blocked');data.set(key,value);}},window:{location:{search},addEventListener(name,fn){windowEvents[name]=fn;}},URLSearchParams,console};
 vm.createContext(context);vm.runInContext(models,context);vm.runInContext(inline,context);
 return{ids,data,access,style,root,windowEvents,action(name){const button=buttons.find(b=>b.dataset.action===name);assert.ok(button,'actual action '+name);button.fire('click');}};
}
function test(name,fn){fn();checks++;console.log('PASS',name);}
function luminance(hex){const rgb=hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];}
function contrast(a,b){const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
test('actual document bindings render initial translation/queue and all extra outputs',()=>{const b=boot();assert.match(b.ids['walk-out'].textContent,/PA=0x0012a124/);assert.match(b.ids['budget-out'].textContent,/10 с/);assert.match(b.ids['buddy-out'].textContent,/32 \/32/);assert.match(b.ids['journal-out'].textContent,/block200=42/);});
test('actual forms preserve global permission rejection; bad input replaces local old success',()=>{
 const b=boot();b.ids.walk.elements.operation.value='write';b.ids.walk.elements.directory.value='0x900d';b.ids.walk.fire('submit');assert.match(b.ids['walk-out'].textContent,/FAULT: protection/);
 b.ids.walk.elements.directory.value='0x900f';b.ids.walk.fire('submit');assert.match(b.ids['walk-out'].textContent,/PA=0x0012a124/);
 // A nonempty text input passes native required validation; stale output was a real UI defect.
 b.ids.walk.elements.va.value='not-an-address';b.ids.walk.fire('submit');assert.match(b.ids['walk-out'].textContent,/Результат не вычислен: адрес: требуется целое число/);assert.doesNotMatch(b.ids['walk-out'].textContent,/PA=|После доступа PDE=/);assert.equal(b.ids['walk-out'].role,'status');
 b.ids.walk.elements.va.value='0x00403124';b.ids.walk.fire('submit');assert.match(b.ids['walk-out'].textContent,/PA=0x0012a124/);assert.equal(b.ids.error.textContent,'');
 // Native number validation can intercept empty input; this checks the handler's own fallback only.
 b.ids.budget.elements.production.value='';b.ids.budget.fire('submit');assert.match(b.ids['budget-out'].textContent,/Результат не вычислен:.*не задано/);assert.doesNotMatch(b.ids['budget-out'].textContent,/10 с/);
});
test('range at page boundary is shown without inventing next-page mapping',()=>{const b=boot();b.ids.walk.elements.va.value='0x00403ffe';b.ids.walk.fire('submit');assert.match(b.ids['walk-out'].textContent,/нужна следующая PTE/);assert.match(b.ids['walk-out'].textContent,/0x00000403 … 0x00000404/);});
test('button path persists COW and restores it without resetting',()=>{const b=boot();b.action('fork');b.action('P');assert.equal(b.ids['cow-rows'].children[0].children[4].textContent,43);assert.equal(b.ids['cow-rows'].children[1].children[4].textContent,42);const saved=b.data.get(KEY),next=boot(saved);assert.equal(next.ids['cow-rows'].children[0].children[4].textContent,43);assert.equal(next.data.get(KEY),saved);assert.deepEqual(new Set(b.access.map(x=>x[1])),READ_KEYS);assert.ok(b.access.filter(x=>x[0]==='set').every(x=>x[1]===KEY));});
test('actual P43 then fork Q44 shows ordinary write first and copies current 43',()=>{
 const b=boot();b.action('P');assert.match(b.ids['cow-out'].textContent,/W=1: CPU записывает/);assert.doesNotMatch(b.ids['cow-out'].textContent,/fault|PTE|TLB|Повторить/);assert.equal(b.ids['cow-rows'].children[0].children[4].textContent,43);
 b.action('fork');assert.equal(b.ids['cow-rows'].children[1].children[4].textContent,43);b.action('Q');assert.match(b.ids['cow-out'].textContent,/Защитный fault/);assert.match(b.ids['cow-out'].textContent,/число пока 43/);assert.doesNotMatch(b.ids['cow-out'].textContent,/число пока 42/);assert.equal(b.ids['cow-rows'].children[0].children[4].textContent,43);assert.equal(b.ids['cow-rows'].children[1].children[4].textContent,44);
 const next=boot(b.data.get(KEY));assert.equal(next.ids['cow-out'].textContent,b.ids['cow-out'].textContent);
});
test('allocator form/order and selected release use actual listeners',()=>{const b=boot();b.ids.allocate.fire('submit');assert.match(b.ids['buddy-out'].textContent,/24 \/32/);assert.equal(b.ids['release-button'].disabled,false);b.ids.release.fire('submit');assert.match(b.ids['buddy-out'].textContent,/32 \/32/);assert.equal(b.ids['release-button'].disabled,true);});
test('CLOCK UI retains new dirty generation across older success',()=>{const b=boot();b.action('clock-step');b.action('clock-step');b.action('clock-write-B');b.action('clock-ok-B');assert.match(b.ids['clock-out'].textContent,/B: resident=1 ref=1 dirty=1 pin=0 writeback=0 version=1/);const next=boot(b.data.get(KEY));assert.equal(next.ids['clock-out'].textContent,b.ids['clock-out'].textContent);});
test('journal UI reveals incomplete tail, committed value, and corrupted copy',()=>{const b=boot();b.action('journal-data');assert.match(b.ids['journal-out'].textContent,/block200=42/);b.action('journal-commit');assert.match(b.ids['journal-out'].textContent,/block200=43/);const saved=b.data.get(KEY);b.ids['journal-corrupt'].checked=true;b.ids['journal-corrupt'].fire('change');assert.match(b.ids['journal-out'].textContent,/Checksum mismatch/);assert.match(b.ids['journal-out'].textContent,/block200=42/);assert.equal(b.data.get(KEY),saved);});
test('corrupt/future/oversized or blocked storage is preserved; reset is scoped',()=>{
 const foreign={'some-reader-notes':'PRIVATE NOTE', [PRESET]:'white',[THEME]:'light',[APPEARANCE]:'{"warmth":30}'};
 for(const raw of ['{broken',JSON.stringify({version:2,events:[]}), 'x'.repeat(8193)]){const b=boot(raw,false,foreign);b.action('fork');assert.equal(b.data.get(KEY),raw);assert.match(b.ids.saved.textContent,/не перезаписана/);b.ids.reset.fire('click');assert.deepEqual(JSON.parse(b.data.get(KEY)),{version:1,events:[]});for(const [key,value]of Object.entries(foreign))assert.equal(b.data.get(key),value);}
 const c=boot(null,true);c.action('fork');assert.equal(c.data.size,0);assert.match(c.ids.saved.textContent,/не загружена/);
});
test('all 8 real presets at warmth 0/50/100 have >=4.5 button/body/link contrast',()=>{
 let minimum=Infinity;
 for(const preset of ['paper','night','white','black','sepia','graphite','midnight','forest'])for(const warmth of [0,50,100]){
  const b=boot(null,false,{},'?readerTheme='+preset+'&warmth='+warmth);assert.equal(b.root.dataset.readerTheme,preset);
  const vars=name=>b.style.get('--'+name);for(const [fg,bg]of [['button-ink','accent'],['fg','panel'],['fg','bg'],['accent','panel'],['muted','panel'],['danger','panel']]){
   const ratio=contrast(vars(fg),vars(bg));assert.ok(ratio>=4.5,`${preset}/${warmth} ${fg}/${bg}: ${ratio}`);if(fg==='button-ink')minimum=Math.min(minimum,ratio);
  }
 }
 assert.match(html,/button\{background:var\(--accent\);color:var\(--button-ink\)/);assert.match(html,/\.secondary\{background:var\(--panel\);color:var\(--fg\)/);
 console.log('MIN_BUTTON_CONTRAST',minimum);
});
test('read-only prefs obey mode, query override and invalid finite-scalar fallback',()=>{
 const prefs={[THEME]:'light',[PRESET]:'sepia',[APPEARANCE]:'{"warmth":100,"size":999}',notes:'untouched'};
 const b=boot(null,false,prefs);assert.equal(b.root.dataset.readerTheme,'sepia');const warmbg=b.style.get('--bg');assert.equal(warmbg,'#eddfc0');
 const explicit=boot(null,false,prefs,'?readerTheme=night&warmth=0');assert.equal(explicit.root.dataset.readerTheme,'night');assert.equal(explicit.style.get('--bg'),'#142027');
 for(const query of ['?readerTheme=%3Cscript%3E&warmth=NaN','?readerTheme=bad&warmth=Infinity','?readerTheme=bad&warmth=-1','?warmth=101','?warmth=']){const x=boot(null,false,prefs,query);assert.equal(x.root.dataset.readerTheme,'sepia');assert.equal(x.style.get('--bg'),warmbg);assert.equal(x.data.size,Object.keys(prefs).length);}
 const mismatch=boot(null,false,{[THEME]:'light',[PRESET]:'forest',[APPEARANCE]:'{bad'});assert.equal(mismatch.root.dataset.readerTheme,'paper');
 const denied=boot(null,true,{},'?readerTheme=black&warmth=100');assert.equal(denied.root.dataset.readerTheme,'black');assert.equal(denied.style.get('--bg'),'#100d08');
 assert.equal(b.data.size,Object.keys(prefs).length);for(const [key,value]of Object.entries(prefs))assert.equal(b.data.get(key),value);assert.ok(!b.access.some(([kind])=>kind==='set'));
 b.data.set(PRESET,'white');b.windowEvents.storage({key:PRESET});assert.equal(b.root.dataset.readerTheme,'white');b.data.set(APPEARANCE,'{"warmth":0}');b.windowEvents.pageshow();assert.equal(b.style.get('--bg'),'#ffffff');
});
console.log(JSON.stringify({result:'PASS',checks,scope:'actual inline scripts + source-derived element bindings and declared-colour contrast; no browser layout/DOM conformance claim'}));
