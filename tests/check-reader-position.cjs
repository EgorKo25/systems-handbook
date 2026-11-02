'use strict';
// Execute exact shipped select() with a deterministic minimal DOM.
// This does not test browser layout, CSS smooth scrolling or pointer hover.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const slugs=JSON.parse(fs.readFileSync(path.join(root,'published-volumes.json'))).volumes.map(x=>x.slug);
function source(page){const start=page.indexOf('function select(hash,restore=false)');assert(start>=0);const end=page.indexOf("window.addEventListener('hashchange'",start);assert(end>start);return page.slice(start,end);}
function run(code){
 const state={current:'physical',scroll:{physical:4200,dns:900},notes:{physical:'keep note'},read:{physical:true},theme:'dark',size:21},frames=[],writes=[],scrolls=[],nodes={};
 for(const id of ['physical','dns']){nodes[id]={id,hidden:true,closest(s){return s==='.chapter'?this:null;}};nodes['#nav-'+id]={setAttribute(k,v){this[k]=v;}};}
 nodes['#top-title']={textContent:''};nodes['#side-nav']={classList:{remove(){}}};nodes['#menu']={setAttribute(){}};
 nodes['dns-field']={closest(s){return s==='.chapter'?nodes.dns:null;},scrollIntoView(o){scrolls.push({target:'dns-field',...o});}};
 const ctx={state,data:[{id:'physical',title:'Physical'},{id:'dns',title:'DNS'}],chapters:[nodes.physical,nodes.dns],document:{getElementById:id=>nodes[id]||null},$:q=>nodes[q],scrollY:0,save(){writes.push(structuredClone(state));},requestAnimationFrame:f=>frames.push(f),scrollTo(o){scrolls.push(o);ctx.scrollY=o.top;},updateProgress(){}};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 return {state,nodes,writes,scrolls,ctx,select:(h,r=false)=>ctx.select(h,r),flush:()=>{while(frames.length)frames.shift()();}};
}
let cases=0;
for(const slug of slugs){const code=source(fs.readFileSync(path.join(root,slug,'index.html'),'utf8'));
 let x=run(code);x.select('#dns',true);x.flush();assert.equal(x.state.scroll.physical,4200,slug+': initial cross-chapter hash must preserve previous bookmark');assert.equal(x.ctx.scrollY,900);assert.deepEqual(x.state.notes,{physical:'keep note'});assert.deepEqual(x.state.read,{physical:true});cases++;
 x=run(code);x.select('',true);x.flush();assert.equal(x.ctx.scrollY,4200);assert.equal(x.state.current,'physical');cases++;
 x=run(code);x.select('#physical',true);x.flush();x.ctx.scrollY=6100;x.select('#dns');x.flush();assert.equal(x.state.scroll.physical,6100);assert.equal(x.ctx.scrollY,0);assert.equal(x.nodes['#top-title'].textContent,'DNS');assert.equal(x.nodes['#nav-dns']['aria-current'],'page');assert.equal(x.nodes['#nav-physical']['aria-current'],'false');assert.equal(x.nodes.dns.hidden,false);cases++;
 x=run(code);x.select('#dns-field',true);x.flush();assert.equal(x.scrolls.at(-1).target,'dns-field');assert.equal(x.state.scroll.physical,4200);cases++;
 x=run(code);x.select('#physical',true);x.select('#dns');x.flush();assert.equal(x.state.current,'dns');assert.equal(x.nodes['#top-title'].textContent,'DNS');assert.equal(x.nodes['#nav-dns']['aria-current'],'page');assert.equal(x.ctx.scrollY,0);cases++;
}
console.log(JSON.stringify({status:'PASS',readers:slugs.length,cases,scope:'actual select() under a minimal synchronous DOM/scroll model; no real browser/CSS/hover/RAF scheduling proof'}));
