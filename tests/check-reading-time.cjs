#!/usr/bin/env node
'use strict';
/* Test the exact self-contained shipped estimator, not a duplicate model. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const cp=require('node:child_process');
const root=path.resolve(__dirname,'..');
const sourceOnly=process.argv.includes('--source-only');
let checks=0;
function ok(value,message){checks++;assert.ok(value,message);}
function eq(actual,expected,message){checks++;assert.deepEqual(actual,expected,message);}
const bundle=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json
from scripts.reader_reading_time import SCRIPT,STYLE_ID,SCRIPT_ID,enhance
fixture='''<html><head></head><body><script id="book-data" type="application/json">[]</script><div class="meta">Введение · 2 070 слов · 14 мин чтения без опытов</div><script>localStorage.getItem("notes-do-not-change");</script></body></html>'''
a=enhance(fixture)
assert a==enhance(a), 'enhancer must be byte-idempotent'
assert '14 мин чтения без опытов' not in a
assert 'Введение · 2 070 слов</div>' in a
assert 'notes-do-not-change' in a
assert a.count('id="'+STYLE_ID+'"')==a.count('id="'+SCRIPT_ID+'"')==1
assert enhance('<html><head></head><body>Library</body></html>')=='<html><head></head><body>Library</body></html>'
print(json.dumps(dict(script=SCRIPT,id=SCRIPT_ID)))
`],{cwd:root,encoding:'utf8'}));
checks+=6;
function load(script){const context={module:{exports:{}},console};vm.runInNewContext(script,context,{timeout:1000});return context.module.exports;}
const model=load(bundle.script);
function sample(key,wpm=180,at=1){return {key,words:600,activeMs:600*60000/wpm,chapterWords:1800,steps:12,at};}
function plain(value){return JSON.parse(JSON.stringify(value));}
eq(model.DEFAULT_WPM,180,'documented initial pace');
eq(model.rate([]),180,'no personal observation yet');
eq(model.rate([sample('a',300),sample('b',300)]),180,'two chapters cannot change prior');
eq(model.rate([sample('a',200),sample('b',210),sample('c',220)]),210,'three independent eligible chapters adapt');
eq(model.rate([sample('a',180),sample('b',180),sample('c',190),sample('d',420)]),180,'MAD excludes a fast outlier');
eq(model.rate([sample('a',80),sample('b',180),sample('c',190),sample('d',200),sample('e',420)]),190,'median resists both tails');
eq(model.rate([sample('a',200),sample('a',300,2),sample('a',400,3)]),180,'one reread chapter cannot supply three observations');
const many=Array.from({length:40},(_,i)=>sample('chapter-'+i,180,i));
eq(model.clean(many).length,15,'storage bounded to fifteen distinct chapters');
eq(model.clean(many)[0].key,'chapter-25','oldest observations removed');
eq(model.clean([sample('a',180,9),sample('a',210,3)])[0].at,9,'newest duplicate survives');
eq(model.clean([sample('a',180,1),sample('a',210,2)])[0].activeMs,600*60000/210,'reread updates rather than duplicates');
for(const invalid of [null,{},sample('',180),sample('a',79),sample('a',421),{...sample('a'),words:349},{...sample('a'),activeMs:Infinity},{...sample('a'),steps:4},{...sample('a'),steps:5.5},{...sample('a'),chapterWords:500},{...sample('a'),words:700,chapterWords:600},{...sample('a'),at:-1},{...sample('a'),chapterWords:10000}])eq(model.clean([invalid]).length,0,'bad/insufficient observations rejected');
for(const text of ['',null,'oops','[]','{"version":2,"samples":[]}',JSON.stringify({version:1,samples:new Array(257).fill(null)}),' '.repeat(65537)])eq(model.decode(text),null,'corrupt/oversize/version-mismatched storage ignored');
eq(plain(model.decode(model.encode(many))),plain(model.clean(many)),'versioned history round trip');
eq(Object.keys(model.clean([{...sample('a'),privateNote:'never store'}])[0]).sort(),['activeMs','at','chapterWords','key','steps','words'].sort(),'do not retain unrelated source properties');
eq(model.minutes(1800),10,'total text estimate ceiling with units');
eq(model.minutes(1801),11,'partial minute rounds up');
eq(model.remaining(1800,.3),'Осталось примерно 7 мин','in chapter remaining label');
eq(model.remaining(1800,.95),'До конца текста меньше минуты','no false completed-reading claim at end');
function observation(now,position,extra={}){return {now,position,viewportWords:150,visible:true,focused:true,blocked:false,...extra};}
function advance(s,startMs,startWord,seconds,wpm=180,{interruptAt,excluded}={}){
  for(let i=0;i<=seconds;i++){
    const now=startMs+i*1000;
    if(i%20===0)s.activity(now);
    const extra=excluded?.(i)||{};
    if(interruptAt===i)s.interrupt(now,1000);
    s.observe(observation(now,(startWord+i*wpm/60)/s.words,extra));
  }
}
const reading=new model.Session('volume:chapter',1800);
advance(reading,0,0,240);
const good=reading.sample(1000);
ok(good,'sustained four-minute normal reading provides sufficient observation');
ok(Math.abs(good.words*60000/good.activeMs-180)<.00001,'observed rate has dimensional units words/minute');
ok(good.words>=700&&good.steps>=40,'only traversed unique words counted');
const idle=new model.Session('idle',1800);
idle.activity(0);idle.observe(observation(0,0));
for(let t=1000;t<=5*3600*1000;t+=1000)idle.observe(observation(t,0));
idle.activity(5*3600*1000);idle.observe(observation(5*3600*1000,.1));
eq(idle.sample(999),null,'five hours on an unmoving page cannot produce a slow personal pace');
eq(idle.activeMs,0,'idle pending time is not credited on next scroll');
for(const [name,extra]of [['hidden',{visible:false}],['blurred',{focused:false}],['form/terminal',{blocked:true}]]){
 const s=new model.Session(name,1800);advance(s,0,0,240,180,{excluded:()=>extra});
 eq(s.sample(1),null,name+' time never creates an observation');eq(s.activeMs,0,name+' contributes no active time');
}
const paused=new model.Session('paused',2400);
advance(paused,0,0,120);
const first=paused.activeMs;
for(let i=1;i<=240;i++){paused.activity(120000+i*1000);paused.observe(observation(120000+i*1000,.15,{blocked:true}));}
eq(paused.activeMs,first,'four minutes of active exercise do not accrue');
advance(paused,361000,360,120);
const p=paused.sample(9);
ok(p&&Math.abs(p.words*60000/p.activeMs-180)<.001,'reading before and after an exercise retains its rate');
const jumper=new model.Session('jump',1800);
jumper.activity(0);jumper.observe(observation(0,0));jumper.observe(observation(1000,.8));
eq(jumper.activeMs,0,'large scroll jump not counted as text traversal');
jumper.observe(observation(4000,.81));jumper.observe(observation(5000,.82));
eq(jumper.sample(1),null,'jump cannot manufacture adequate chapter coverage');
const fast=new model.Session('fast',1800);advance(fast,0,0,60,1200);
eq(fast.sample(1),null,'rapid scrolling rejected');
const gap=new model.Session('clockgap',1800);
gap.activity(0);gap.observe(observation(0,0));gap.activity(30000);gap.observe(observation(30000,.05));
eq(gap.activeMs,0,'timer suspension resets baseline rather than charging an interval');
const layout=new model.Session('details-collapse',1800);advance(layout,0,0,120);
const prior=layout.activeMs;layout.interrupt(120000,1000);layout.observe(observation(121000,.8));
eq(layout.activeMs,prior,'geometry interrupt baseline does not count collapsed text');
const reread=new model.Session('reread',1800);advance(reread,0,0,240);
const unique=reread.intervals.reduce((n,[a,b])=>n+b-a,0),time=reread.activeMs;
reread.interrupt(240000);advance(reread,241000,0,240);
ok(Math.abs(reread.intervals.reduce((n,[a,b])=>n+b-a,0)-unique)<.001,'repeated reading cannot manufacture distinct chapter coverage');
ok(Math.abs(reread.activeMs-time)<.001,'reread time is not charged against old unique words');
// Malformed access must be harmless even if browser storage itself throws.
function browserStorage(value,blocked=false){return {getItem(){if(blocked)throw Error('blocked');return value;},setItem(){if(blocked)throw Error('blocked');}};}
for(const storage of [browserStorage('{bad'),browserStorage(null,true)]){
 let restored=[];try{restored=model.decode(storage.getItem(model.KEY))||[];}catch(_){}
 eq(restored.length,0,'corrupt or blocked local storage preserves initial default');
}
// Minimal deterministic DOM fixture executes the browser adapter itself. It
// models a plain (legacy networks) header and a large closed transcript.
function browserFixture({storageBlocked=false}={}){
 let clock=0,scroll=0;const events=new Map(),docEvents=new Map(),raf=[],writes=[];
 const registry=new Map();let rootWindow;
 class Element{
  constructor(tag='div',id='',classes=''){this.tagName=tag.toUpperCase();this.id=id;this.className=classes;this.dataset={};this.children=[];this.parentElement=null;this.hidden=false;this.nodeType=1;this.value='';this.rect={top:0,height:100};this.classList={contains:c=>this.className.split(/\s+/).includes(c)};if(id)registry.set(id,this);}
  appendChild(child){child.parentElement=this;this.children.push(child);return child;}
  remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(x=>x!==this);}
  set textContent(text){this.value=String(text);this.children=[];}
  get textContent(){return this.value+this.children.map(x=>x.textContent).join('');}
  matches(selector){
   if(selector==='[hidden]')return this.hidden;
   if(selector==='[contenteditable="true"]')return false;
   if(selector==='dialog[open]')return false;
   if(selector.endsWith(':not([hidden])'))return !this.hidden&&this.matches(selector.slice(0,-14));
   const data=selector.match(/^\[data-([\w-]+)\]$/);if(data)return data[1].replace(/-([a-z])/g,(_,c)=>c.toUpperCase()) in this.dataset;
   if(selector.startsWith('.'))return selector.slice(1).split('.').every(c=>this.classList.contains(c));
   if(selector.includes('.')){const [tag,cl]=selector.split('.');return this.tagName===tag.toUpperCase()&&this.classList.contains(cl);}
   return this.tagName===selector.toUpperCase();
  }
  closest(selectors){for(let e=this;e;e=e.parentElement)if(selectors.split(',').some(s=>e.matches(s)))return e;return null;}
  querySelectorAll(selectors){const result=[];const walk=e=>{for(const c of e.children){if(selectors.split(',').some(s=>c.matches(s)))result.push(c);walk(c);}};walk(this);return result;}
  querySelector(selectors){return this.querySelectorAll(selectors)[0]||null;}
  getClientRects(){for(let e=this;e;e=e.parentElement)if(e.hidden)return [];return [this.getBoundingClientRect()];}
  getBoundingClientRect(){return {...this.rect,top:this.rect.top-scroll,bottom:this.rect.top-scroll+this.rect.height};}
 }
 const body=new Element('body');body.dataset.volume='test';
 const title=body.appendChild(new Element('span','top-title','topbar-title'));title.textContent='Title';
 const nav=body.appendChild(new Element('a','nav-c1'));nav.appendChild(new Element('span'));nav.appendChild(new Element('span'));
 const article=body.appendChild(new Element('article','c1','chapter'));article.rect={top:400,height:2400};
 const header=article.appendChild(new Element('header'));header.rect={top:400,height:100};
 const paragraphs=[];article._texts=[];
 for(let i=0;i<4;i++){
  const p=article.appendChild(new Element('p'));p.rect={top:500+i*400,height:400};p.hidden=i===1;
  const words=i===1?1200:400;p.value=new Array(words).fill('слово').join(' ');
  article._texts.push({parentElement:p,textContent:p.value});paragraphs.push(p);
 }
 const data=new Element('script','book-data');data.textContent=JSON.stringify([{id:'c1',words:2400}]);
 const drawer=body.appendChild(new Element('aside','dictionary','drawer'));drawer.hidden=true;
 const doc={body,hidden:false,activeElement:body,getElementById:id=>registry.get(id)||null,createElement:tag=>new Element(tag),querySelector:s=>body.querySelector(s),hasFocus:()=>doc.focused,focused:true,createTreeWalker:element=>{let i=0;return {nextNode:()=>element._texts[i++]||null};},addEventListener:(name,fn)=>{if(!docEvents.has(name))docEvents.set(name,[]);docEvents.get(name).push(fn);}};
 rootWindow={document:doc,location:{hash:'#c1'},innerHeight:800,NodeFilter:{SHOW_TEXT:4},performance:{now:()=>clock},localStorage:{getItem(){if(storageBlocked)throw Error('blocked');return null;},setItem(k,v){if(storageBlocked)throw Error('blocked');writes.push([k,v]);}},requestAnimationFrame:fn=>raf.push(fn),addEventListener:(name,fn)=>{if(!events.has(name))events.set(name,[]);events.get(name).push(fn);},setInterval:fn=>{rootWindow.tick=fn;},MutationObserver:class{constructor(fn){this.fn=fn;}observe(){}}};
 vm.runInNewContext(bundle.script,{window:rootWindow,module:{exports:{}}},{timeout:1000});
 const flush=()=>{while(raf.length)raf.shift()();};
 const emit=(name,event={},documentEvent=false)=>{for(const fn of (documentEvent?docEvents:events).get(name)||[])fn({type:name,target:body,isTrusted:true,...event});flush();};
 return {window:rootWindow,doc,title,nav,article,header,drawer,paragraphs,writes,emit,flush,setClock:v=>clock=v,setScroll:v=>scroll=v,advance:()=>rootWindow.tick(),label:()=>title.querySelector('[data-reading-current]')?.textContent};
}
const browser=browserFixture();
eq(browser.nav.querySelector('[data-reading-total]').textContent,'≈ 14 мин','sidebar keeps full-text estimate');
ok(browser.header.querySelector('[data-reading-status]'),'plain legacy header receives total estimate');
const initialLabel=browser.label();
eq(initialLabel,'Осталось примерно 7 мин','closed transcript is excluded from remaining route');
browser.setScroll(2400);browser.setClock(1000);browser.emit('scroll');
eq(browser.label(),'До конца текста меньше минуты','footer has less than a minute even with closed transcript');
const footerLabel=browser.label();browser.paragraphs[1].hidden=false;browser.emit('toggle',{},true);browser.setClock(3000);browser.advance();
eq(browser.label(),footerLabel,'opening transcript does not alone change remaining');
browser.setScroll(0);browser.emit('wheel',{},true);browser.advance();
eq(browser.label(),'Осталось примерно 14 мин','real movement resumes new expanded route');
browser.title.textContent='Core selected chapter';browser.advance();
ok(browser.title.querySelector('[data-reading-current]'),'core title replacement is repaired without navigation change');
browser.window.location.hash='#volume';browser.emit('hashchange');
eq(browser.label(),undefined,'volume landing has no current chapter reading status');
const noStorage=browserFixture({storageBlocked:true});
eq(noStorage.window.LibraryReadingTime.rate(),180,'actual adapter works with browser storage blocked');
ok(noStorage.writes.length===0,'no preferences or notes are written on load');
function readFixture(fixture,eventTarget){
 fixture.setScroll(220);fixture.emit('wheel',eventTarget?{target:eventTarget}:{},true);
 for(let t=1;t<=125;t++){
  fixture.setClock(t*1000);fixture.setScroll(220+3*t);
  if(t%20===0)fixture.emit('wheel',eventTarget?{target:eventTarget}:{},true);else fixture.advance();
 }
 fixture.emit('pagehide');
}
const normalBrowser=browserFixture();readFixture(normalBrowser);
eq(normalBrowser.writes.length,1,'actual adapter saves sufficient sustained normal traversal');
eq(normalBrowser.writes[0][0],model.KEY,'actual adapter writes only its own history key');
const openDrawer=browserFixture();openDrawer.drawer.hidden=false;readFixture(openDrawer);
eq(openDrawer.writes.length,0,'open drawer with no .open class cannot train text pace');
const inputBrowser=browserFixture();inputBrowser.doc.activeElement=inputBrowser.doc.createElement('textarea');readFixture(inputBrowser);
eq(inputBrowser.writes.length,0,'active form prevents actual adapter from collecting a pace sample');
const sketchBrowser=browserFixture();const sketch=sketchBrowser.doc.createElement('section');sketch.className='deep-sketch';const sketchButton=sketch.appendChild(sketchBrowser.doc.createElement('button'));sketchBrowser.doc.activeElement=sketchButton;readFixture(sketchBrowser,sketchButton);
eq(sketchBrowser.writes.length,0,'focus in interactive sketch stays blocked past 1500 milliseconds');
const resumedSketch=browserFixture();const lastSketch=resumedSketch.doc.createElement('section');lastSketch.className='deep-sketch';const lastButton=lastSketch.appendChild(resumedSketch.doc.createElement('button'));resumedSketch.doc.activeElement=lastButton;readFixture(resumedSketch);
eq(resumedSketch.writes.length,1,'explicit scroll over text resumes learning without forcing focus away from old sketch');
const hiddenBrowser=browserFixture();hiddenBrowser.doc.hidden=true;readFixture(hiddenBrowser);
eq(hiddenBrowser.writes.length,0,'actual hidden tab cannot train');
const blurredBrowser=browserFixture();blurredBrowser.doc.focused=false;readFixture(blurredBrowser);
eq(blurredBrowser.writes.length,0,'actual unfocused tab cannot train');
const volumes=JSON.parse(fs.readFileSync(path.join(root,'published-volumes.json'),'utf8')).volumes.map(row=>row.slug);
if(!sourceOnly)for(const volume of volumes){
 const html=fs.readFileSync(path.join(root,volume,'index.html'),'utf8');
 const escaped=bundle.id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const scripts=[...html.matchAll(new RegExp('<script id="'+escaped+'">([\\s\\S]*?)<\\/script>','g'))];
 eq(scripts.length,1,volume+': one reading-time adapter');
 eq(scripts[0][1].replace(/\r\n/g,'\n'),bundle.script.replace(/\r\n/g,'\n'),volume+': shipped script matches tested implementation');
 eq(load(scripts[0][1]).remaining(1800,.3),'Осталось примерно 7 мин',volume+': actual shipped algorithm executes');
 ok(!/<div class="meta">[^<]*\d+\s+мин чтения без опытов/.test(html),volume+': old fixed estimate removed');
}
console.log('PASS reading-time: '+checks+' assertions'+(sourceOnly?' (source only; run again after reader refresh)':' including all '+volumes.length+' shipped readers'));
