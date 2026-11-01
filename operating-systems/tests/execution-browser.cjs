'use strict';
// Functional DOM mock only: catches broken mounting and controls, not CSS/mobile rendering.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
let checks=0;function eq(a,b,msg){assert.deepEqual(a,b,msg);checks++;}function ok(v,msg){assert.ok(v,msg);checks++;}
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.listeners={};this.textContent='';this.disabled=false;this._value=undefined;}
 append(...nodes){this.children.push(...nodes);}
 prepend(...nodes){this.children.unshift(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attributes[k]=v;}
 addEventListener(k,f){(this.listeners[k]||=[]).push(f);}
 fire(k){for(const f of this.listeners[k]||[])f({target:this});}
 get value(){return this._value===undefined?(this.tagName==='select'&&this.children[0]?this.children[0].value:''):this._value;}
 set value(v){this._value=String(v);}
}
function all(n,tag){return [...(n.tagName===tag?[n]:[]),...n.children.flatMap(c=>all(c,tag))];}
function text(n){return n.textContent+' '+n.children.map(text).join(' ');}
const kinds=['boundary','scheduler','smp','lifecycle','service'],containers=kinds.map(k=>{const e=new Element('div');e.dataset.osExecution=k;return e;});
const document={readyState:'loading',createElement:t=>new Element(t),querySelectorAll:selector=>{eq(selector,'[data-os-execution]');return containers;},listeners:{},addEventListener(k,f){this.listeners[k]=f;}};
const context=vm.createContext({document,console});const script=fs.readFileSync(path.join(__dirname,'../labs/execution/models.js'),'utf8');vm.runInContext(script,context);eq(containers[0].children.length,0);document.listeners.DOMContentLoaded();
for(const c of containers){eq(c.dataset.osExecutionMounted,'1');eq(all(c,'button').length,3);ok(all(c,'button').every(b=>b.type==='button'));ok(all(c,'span').some(n=>n.attributes['aria-live']==='polite'));eq(all(c,'button')[0].disabled,true);}
const boundary=containers[0],choose=all(boundary,'select')[0];
for(const scenario of ['cached','blocked','fault','bad-buffer']){
 choose.value=scenario;choose.fire('change');eq(all(boundary,'button')[0].disabled,true);
 let steps=0;while(!all(boundary,'button')[1].disabled){all(boundary,'button')[1].fire('click');steps++;ok(steps<30);}
 const content=text(boundary);if(scenario==='cached'){ok(content.includes('0x00401004'));ok(content.includes('0x8000F00C'));ok(content.includes('04 00 00 00'));}
 if(scenario==='blocked'){ok(content.includes('Прерванное продолжение T2'));ok(content.includes('99 / 0'));}
 if(scenario==='fault')ok(content.includes('42'));
 if(scenario==='bad-buffer'){ok(content.includes('BAD_BUFFER'));ok(content.includes('f2 ff ff ff'));}
 ok(!all(boundary,'pre').length,'raw internal JSON should not occupy the page');all(boundary,'button')[2].fire('click');eq(all(boundary,'button')[0].disabled,true);
}
const scheduler=containers[1],selectors=all(scheduler,'select');eq(selectors.length,3);
const [policy,workload,quantum]=selectors;eq(policy.value,'rr');eq(quantum.value,'2');
quantum.value='1';quantum.fire('change');ok(text(scheduler).includes('первый запуск 0'));
policy.value='fcfs';policy.fire('change');eq(quantum.disabled,true);ok(text(scheduler).includes('очередь 7'));
workload.value='io';workload.fire('change');ok(text(scheduler).includes('внешнее ожидание 3'));
policy.value='rr';policy.fire('change');eq(quantum.disabled,false);
const smp=containers[2],aff=all(smp,'select')[0];aff.value='cpu0';aff.fire('change');ok(text(smp).includes('50%'));
const life=containers[3],lifeChoice=all(life,'select')[0];lifeChoice.value='load';lifeChoice.fire('change');for(let i=0;i<2;i++)all(life,'button')[1].fire('click');ok(text(life).includes('LOAD_FAILED'));eq(all(life,'button')[1].disabled,true);
const service=containers[4],serviceChoice=all(service,'select')[0];serviceChoice.value='forced-stop';serviceChoice.fire('change');while(!all(service,'button')[1].disabled)all(service,'button')[1].fire('click');ok(text(service).includes('FORCED/UNKNOWN'));
const sizes=containers.map(c=>c.children.length);vm.runInContext(script,context);eq(containers.map(c=>c.children.length),sizes,'re-entry must not duplicate controls');
console.log('PASS execution browser logic: '+checks+' assertions; DOM mock, no visual/mobile claim');
