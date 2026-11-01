/* Execute the shipped view with a minimal DOM adapter; not a browser/visual test. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const M=require('../labs/memory/model.js'),source=fs.readFileSync(require('node:path').join(__dirname,'../labs/memory/view.js'),'utf8');
class Element{constructor(tag='div'){this.tagName=tag;this.children=[];this.disabled=false;this.hidden=false;this.value='';this.style={};this.textContent='';}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;}click(){if(!this.disabled&&this.onclick)this.onclick();}}
function open(storage=new Map()) {const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};const document={getElementById:get,createElement:t=>new Element(t),createTextNode:t=>({textContent:t})};const localStorage={getItem:k=>storage.has(k)?storage.get(k):null,setItem:(k,v)=>storage.set(k,v)};const context={window:{MemoryLab:M,M32Appearance:{mount(){}},print(){}},document,localStorage,confirm:()=>true,URL,Blob,setTimeout};vm.runInNewContext(source,context,{filename:'shipped-memory-view.js'});return {get,storage,choose(scene){get('scene').value=scene;get('scene').onchange();},buttons:()=>get('actions').children,button(label){const b=get('actions').children.find(b=>b.textContent===label);assert(b,'missing button: '+label);return b;}};}
let groups=0;
{
 const ui=open();ui.choose('numa');assert.equal(ui.button('Следующий переход').disabled,true);ui.button('Запрос к удалённому узлу 1').click();assert.equal(ui.button('Следующий переход').disabled,false);for(let i=0;i<6;i++)ui.button('Следующий переход').click();const before=ui.storage.get('handbook-ca-memory-v1'),s=JSON.parse(before);assert.equal(s.numa.phase,'idle');assert.equal(s.numa.last.value,42);assert.equal(ui.button('Следующий переход').disabled,true);ui.button('Следующий переход').click();assert.equal(ui.storage.get('handbook-ca-memory-v1'),before);assert(!ui.get('message').textContent.includes('no NUMA request'));const resumed=open(ui.storage);assert.equal(resumed.button('Следующий переход').disabled,true);groups++;
}
{
 const ui=open();for(const scene of ['bytes','cache','dram','mesi','order','counter','sv32','numa','performance']){ui.choose(scene);assert(ui.get('title').textContent.length>4);assert(ui.buttons().length>0);}ui.choose('performance');const label=ui.buttons().find(e=>e.children.some(c=>c.type==='number'));const input=label.children[0],before=JSON.parse(ui.storage.get('handbook-ca-memory-v1')).performance.input.hitNs;input.value='-1';input.onchange();assert.equal(JSON.parse(ui.storage.get('handbook-ca-memory-v1')).performance.input.hitNs,before);assert.match(ui.get('message').textContent,/Отказ/);groups++;
}
{
 const original='{broken JSON',storage=new Map([['handbook-ca-memory-v1',original]]),ui=open(storage);assert.equal(ui.get('raw').hidden,false);assert(ui.buttons().every(b=>b.disabled));ui.choose('numa');assert(ui.buttons().every(b=>b.disabled));assert.equal(storage.get('handbook-ca-memory-v1'),original);groups++;
}
console.log(JSON.stringify({kind:'shipped view execution with minimal DOM adapter, not browser',groups,passed:true,regression:'NUMA Next disabled after completion and reload'}));
