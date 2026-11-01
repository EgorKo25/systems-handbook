'use strict';
// Actual enhanced bootstrap + synthetic DOM/URL checks. No browser navigation claim.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..'),fixtures=path.resolve(process.env.HANDBOOK_LAB_LINK_FIXTURES||root);
const rendered=JSON.parse(cp.execFileSync('python3',['-B','-c',String.raw`
from pathlib import Path
import importlib.util,re,json,sys
root,fixtures=map(Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location('candidate_preferences',root/'scripts/reader_preferences.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
shell=(fixtures/'cache/sources/reader-shell.html').read_text()
page=module.enhance(shell);twice=module.enhance(page)
assert page==twice,'enhance must remain idempotent'
pattern=r'<script[^>]*id="library-preferences-bootstrap-v1"[^>]*>([\s\S]*?)</script>'
reader=re.findall(pattern,page);assert len(reader)==1
home=module.enhance('<html><head><meta charset="utf-8"></head><body></body></html>',home=True)
print(json.dumps({'script':reader[0],'homeScript':re.findall(pattern,home)[0],'sourceKey':re.search(r'data-storage-key="([^"]+)"',shell)[1],'idempotent':page==twice}))
`,root,fixtures],{encoding:'utf8'}));
const labHTML=fs.readFileSync(path.join(fixtures,'operating-systems/labs/memory-io/index.html'),'utf8');
const labBootstrap=[...labHTML.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
const BASE='file:///E:/My%20Books/systems-handbook/operating-systems/index.html';
const THEME='library-theme-v1',PRESET='library-reader-preset-v1',APPEARANCE='library-reader-appearance-v1';
const ids=['paper','night','white','black','sepia','graphite','midnight','forest'];let groups=0,urlCases=0;
function test(name,f){f();groups++;console.log('PASS',name);}
function boot({base=BASE,hrefs=[],prefs={},blocked=false,loading=false,home=false,hook=false,observer=true}={}){
 const events=new Map(),domEvents=new Map(),values=new Map(),mutations=[],writes=[],reads=[],anchors=[];let observed=false,observerCallback=null;
 class Node{
  constructor(tag='div',attrs={},children=[]){this.tag=tag;this.attrs=new Map(Object.entries(attrs));this.children=children;this.assignments=0;if(tag==='a')anchors.push(this);}
  getAttribute(name){return this.attrs.get(name)??null;}
  setAttribute(name,value){value=String(value);if(this.getAttribute(name)===value)return;this.attrs.set(name,value);this.assignments++;if(name==='href'&&observed)mutations.push({type:'attributes',target:this,attributeName:'href'});}
  matches(selector){assert.equal(selector,'a[href*="memory-io"]');return this.tag==='a'&&this.attrs.has('href')&&this.attrs.get('href').includes('memory-io');}
  querySelectorAll(selector){const all=[];for(const child of this.children){if(child.matches(selector))all.push(child);all.push(...child.querySelectorAll(selector));}return all;}
  get href(){return new URL(this.getAttribute('href'),base).href;}
 }
 const tree=new Node('html');tree.dataset={};tree.style={setProperty(k,v){values.set(k,v);}};
 for(const href of hrefs)tree.children.push(new Node('a',typeof href==='string'?{href}:href));
 const document={documentElement:tree,readyState:loading?'loading':'complete',getElementById(){return null;},querySelectorAll(selector){return tree.querySelectorAll(selector);},addEventListener(type,callback){domEvents.set(type,callback);}};
 const data=new Map(Object.entries(prefs)),localStorage={getItem(key){reads.push(key);if(blocked)throw Error('read denied');return data.get(key)??null;},setItem(key,value){if(blocked)throw Error('write denied');writes.push([key,value]);data.set(key,value);}};
 const window={location:{href:base},addEventListener(type,callback){events.set(type,callback);}};
 const context={window,document,localStorage,URL,encodeURIComponent,decodeURIComponent};
 if(observer)context.MutationObserver=class{constructor(callback){observerCallback=callback;}observe(target,options){assert.equal(target,tree);assert.deepEqual(JSON.parse(JSON.stringify(options)),{subtree:true,childList:true,attributes:true,attributeFilter:['href']});observed=true;}};
 let source=home?rendered.homeScript:rendered.script;
 if(hook){const at=source.lastIndexOf('\n})();');assert.ok(at>0);source=source.slice(0,at)+'\nwindow.__probeMemoryLabHref=memoryLabHref;'+source.slice(at);}
 vm.runInNewContext(source,context,{timeout:1000});
 return{api:window.LibraryPreferences,helper:window.__probeMemoryLabHref,anchors,tree,data,writes,reads,events,domEvents,values,Node,
  flush(){let rounds=0;while(mutations.length){assert.ok(++rounds<=4,'observer must settle without self-trigger loop');observerCallback(mutations.splice(0));}},
  add(node){tree.children.push(node);if(observed)mutations.push({type:'childList',addedNodes:[node]});},
  observed:()=>observed};
}
function prefs(preset='night',warmth=0){return{[THEME]:['paper','white','sepia'].includes(preset)?'light':'dark',[PRESET]:preset,[APPEARANCE]:JSON.stringify({warmth,font:'palatino',size:25,privateExtra:'DO NOT FORWARD'}),[rendered.sourceKey]:JSON.stringify({notes:{chapter:'PRIVATE NOTE'},history:['PRIVATE HISTORY'],size:23})};}
function checkScalars(href,preset,warmth){const u=new URL(href);assert.deepEqual(u.searchParams.getAll('readerTheme'),[preset]);assert.deepEqual(u.searchParams.getAll('warmth'),[String(warmth)]);return u;}
test('real maintained shell enhancement is idempotent and decorates href before any navigation event',()=>{
 assert.equal(rendered.idempotent,true);
 const t=boot({hrefs:[{href:'labs/memory-io/index.html#translation',target:'_blank',rel:'noopener',class:'lab-link'}],prefs:prefs('forest',73.5)});
 const a=t.anchors[0],u=checkScalars(a.href,'forest',73.5);assert.equal(u.hash,'#translation');assert.equal(a.getAttribute('target'),'_blank');assert.equal(a.getAttribute('rel'),'noopener');assert.equal(a.getAttribute('class'),'lab-link');
 // Mouse, Enter, context-menu/new-tab and copy-link consume this pre-existing href;
 // no click-only handler or prevented default is needed by the adapter.
 assert.ok(!t.events.has('click')&&!t.domEvents.has('click')&&!t.domEvents.has('keydown'));assert.ok(t.observed());
 const before=a.assignments;t.flush();assert.equal(a.assignments,before,'already decorated mutation must be stable');
});
test('pure actual URL function handles file/http/https prefixes and preserves unrelated raw query/fragment',()=>{
 const t=boot({hook:true}),f=t.helper;assert.equal(typeof f,'function');
 for(const base of [BASE,'file:///home/me/Книга/operating-systems/index.html','file://server/share/book/linux/index.html','https://example.test/book/operating-systems/index.html','https://example.test/book/linux/','http://127.0.0.1:8766/books/go/index.html']){
  const href='../operating-systems/labs/memory-io/index.html?x=one%20two&x=three+four&flag&raw=%2f%2F&readerTheme=paper&warmth=1&%72eaderTheme=black#clock%2fphase';
  const next=f(href,base,'midnight',0);assert.ok(next);const u=checkScalars(next,'midnight',0);assert.equal(u.hash,'#clock%2fphase');assert.equal(u.search,'?x=one%20two&x=three+four&flag&raw=%2f%2F&readerTheme=midnight&warmth=0');assert.equal(f(next,base,'midnight',0),next);urlCases++;
 }
 const malformed=f('labs/memory-io/index.html?%ZZ=keep&&blank=&warmth=5#journal',BASE,'white',100);assert.equal(new URL(malformed).search,'?%ZZ=keep&&blank=&readerTheme=white&warmth=100');urlCases++;
});
test('strict destination checks reject unrelated protocols, hosts, prefixes and other laboratories',()=>{
 const f=boot({hook:true}).helper;
 for(const href of ['https://evil.test/operating-systems/labs/memory-io/index.html','http://example.test/book/operating-systems/labs/memory-io/index.html','https://example.test:444/book/operating-systems/labs/memory-io/index.html','https://user:pass@example.test/book/operating-systems/labs/memory-io/index.html','/other/operating-systems/labs/memory-io/index.html','labs/coordination/index.html','labs/memory-io/README.txt','labs/memory-io/index.html.backup','labs/memory-io/','javascript:alert(1)','data:text/html,memory-io','mailto:a@example.test','#translation','../linux/index.html']){
  assert.equal(f(href,'https://example.test/book/operating-systems/index.html','night',55),null,href);urlCases++;
 }
 for(const href of ['file://another/share/book/operating-systems/labs/memory-io/index.html','file:///other/book/operating-systems/labs/memory-io/index.html','file:///D:/My%20Books/systems-handbook/operating-systems/labs/memory-io/index.html']){assert.equal(f(href,BASE,'night',1),null);urlCases++;}
 for(const base of ['not a URL','about:blank','data:text/html,reader'])assert.equal(f('labs/memory-io/index.html',base,'night',1),null);
 for(const preset of [null,undefined,{},['night'],'missing','NIGHT','night&notes=private'])assert.equal(f('labs/memory-io/index.html',BASE,preset,20),null);
 for(const warmth of [NaN,Infinity,-1,101,'20',null,{},undefined])assert.equal(f('labs/memory-io/index.html',BASE,'night',warmth),null);
});
test('all8 theme changes and warmth endpoints update existing href, with no stale duplicate scalars',()=>{
 const t=boot({hrefs:['labs/memory-io/index.html?readerTheme=bad&warmth=bad&warmth=0&keep=yes#buddy'],prefs:prefs()});
 for(const preset of ids)for(const warmth of [0,23.5,100]){t.api.setPreset(preset);t.api.setAppearance({warmth});t.flush();const u=checkScalars(t.anchors[0].href,preset,warmth);assert.equal(u.searchParams.get('keep'),'yes');assert.equal(u.hash,'#buddy');urlCases++;}
 t.api.setAppearance({warmth:NaN});assert.equal(new URL(t.anchors[0].href).searchParams.get('warmth'),'100');
});
test('late chapter content, nested anchors, changed href and pre-DOMContentLoaded content are covered',()=>{
 const t=boot({prefs:prefs('sepia',40)}),a=new t.Node('a',{href:'labs/memory-io/index.html?lesson=3#cow'});t.add(new t.Node('section',{},[new t.Node('p',{},[a])]));t.flush();checkScalars(a.href,'sepia',40);a.setAttribute('href','labs/memory-io/index.html?lesson=4#journal');t.flush();assert.equal(checkScalars(a.href,'sepia',40).searchParams.get('lesson'),'4');
 const external='https://elsewhere.test/book/operating-systems/labs/memory-io/index.html#cow';a.setAttribute('href',external);t.flush();assert.equal(a.getAttribute('href'),external);
 const late=boot({loading:true,prefs:prefs('black',88)}),b=new late.Node('a',{href:'labs/memory-io/index.html#translation'});late.add(b);assert.equal(late.observed(),false);late.domEvents.get('DOMContentLoaded')();checkScalars(b.href,'black',88);assert.equal(late.observed(),true);
});
test('storage/pageshow changes and blocked storage use current in-memory scalars without copying notes or parent query',()=>{
 const initial=prefs('paper',12),t=boot({base:BASE+'?notes=PRIVATE_PARENT#note',hrefs:['labs/memory-io/index.html#clock'],prefs:initial});const beforeNotes=t.data.get(rendered.sourceKey),reads=t.reads.length,writes=t.writes.length;
 t.flush();assert.equal(t.reads.length,reads);assert.equal(t.writes.length,writes,'link decoration itself has no storage writes');assert.ok(!t.anchors[0].href.includes('PRIVATE'));
 t.data.set(PRESET,'midnight');t.data.set(THEME,'dark');t.events.get('storage')({key:PRESET,newValue:'midnight'});checkScalars(t.anchors[0].href,'midnight',12);
 t.data.set(APPEARANCE,JSON.stringify({warmth:66,font:'sans',size:22,notes:'PRIVATE APPEARANCE'}));t.events.get('storage')({key:APPEARANCE,newValue:t.data.get(APPEARANCE)});checkScalars(t.anchors[0].href,'midnight',66);
 t.data.set(PRESET,'forest');t.events.get('pageshow')();checkScalars(t.anchors[0].href,'forest',66);assert.equal(t.data.get(rendered.sourceKey),beforeNotes);assert.ok(!t.anchors[0].href.includes('PRIVATE'));assert.deepEqual([...new URL(t.anchors[0].href).searchParams.keys()],['readerTheme','warmth']);
 const denied=boot({hrefs:['labs/memory-io/index.html#cow'],blocked:true});denied.api.setPreset('white');denied.api.setAppearance({warmth:90});denied.events.get('pageshow')();checkScalars(denied.anchors[0].href,'white',90);assert.equal(denied.writes.length,0);
});
test('home/other labs/external links stay unchanged; old palette-only mocks do not require URL or DOM traversal',()=>{
 const hrefs=['../operating-systems/labs/memory-io/index.html','labs/coordination/index.html','https://external.test/memory-io/index.html'];const home=boot({home:true,hrefs,prefs:prefs()});assert.deepEqual(home.anchors.map(a=>a.getAttribute('href')),hrefs);assert.equal(home.observed(),false);
 const plain=boot({hrefs:hrefs.slice(1),prefs:prefs()});assert.deepEqual(plain.anchors.map(a=>a.getAttribute('href')),hrefs.slice(1));
 const window={addEventListener(){}},document={documentElement:{dataset:{},style:{setProperty(){}}},getElementById(){return null;},readyState:'complete'},localStorage={getItem(){return null;},setItem(){}};vm.runInNewContext(rendered.script,{window,document,localStorage});assert.equal(window.LibraryPreferences.selectedTheme,'night');
});
test('end-to-end scalar URL reaches exact frozen laboratory bootstrap with separate denied storage',()=>{
 for(const preset of ids)for(const warmth of [0,50,100]){const t=boot({hrefs:['labs/memory-io/index.html#translation'],prefs:prefs(preset,warmth)}),u=checkScalars(t.anchors[0].href,preset,warmth);const vars=new Map(),html={dataset:{},style:{setProperty(k,v){vars.set(k,v);}}},window={location:{search:u.search},addEventListener(){}};
  const localStorage={getItem(){throw Error('different file storage denied');},setItem(){throw Error('lab must not write preferences');}};
  vm.runInNewContext(labBootstrap,{window,document:{documentElement:html},localStorage,URLSearchParams});assert.equal(html.dataset.readerTheme,preset);assert.ok(vars.get('--bg'));assert.ok(vars.get('--button-ink'));
 }
});
console.log(JSON.stringify({status:'PASS',groups,urlCases,scope:'actual Python enhancer + shipped bootstrap logic/WHATWG URL/synthetic DOM/observer + lab-bootstrap scalar roundtrip; no actual browser or file navigation'}));
