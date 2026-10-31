'use strict';
// Exercise the actual shipped search code, not a duplicate implementation.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const page=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
const scripts=[...page.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const bundle=scripts.find(s=>s.includes('root.CommandReferenceSearch = search;'));
assert(bundle,'command search script exists');
const begin=bundle.lastIndexOf('(function (root) {',bundle.indexOf('function normalizeText'));
const endMarker="})(typeof globalThis !== 'undefined' ? globalThis : this);";
const end=bundle.indexOf(endMarker,begin);
assert(begin>=0&&end>begin);
const source=bundle.slice(begin,end+endMarker.length);
const scope={module:{exports:{}},console}; vm.runInNewContext(source,scope);
const search=scope.module.exports;
const commands=JSON.parse(fs.readFileSync(path.join(__dirname,'../commands.json'),'utf8'));
let count=0;
for(const [query,name,flag] of [
 ['git diff --cached','git diff','--cached'],
 ['git reset --soft HEAD~1','git reset','--soft'],
 ['git status --short','git status','--short'],
 ['git push --force-with-lease','git push','--force-with-lease'],
 ['git fetch --prune','git fetch','--prune'],
 ['grep -nE error access.log','grep','-n'],
]){
 const results=search.searchCommands(commands,query);assert.equal(results.length,1,query);count++;
 const r=results[0];assert.equal(r.command.name,name,query);count++;
 assert(r.analysis.explicit,query);count++;
 assert(r.analysis.matchedIndices.some(i=>r.command.flags[i].flag.includes(flag)),query+' finds '+flag);count++;
}
for(const c of commands.filter(c=>c.volume==='git')){
 const results=search.searchCommands(commands,c.name);assert.equal(results.length,1,c.name);assert.equal(results[0].command.name,c.name);count+=2;
 for(const flag of c.flags)for(const key of ['flag','action','when','example','result'])assert.equal(typeof flag[key],'string');
}
// Every interactive step references real participants and edges; no undefined states.
const seen=new Set();let steps=0;
for(const raw of page.matchAll(/<script type="application\/json" class="ds-data">([\s\S]*?)<\/script>/g)){
 const d=JSON.parse(raw[1]);assert(!seen.has(d.id));seen.add(d.id);
 const nodes=new Set(d.nodes.map(n=>n.id)),edges=new Set(d.edges.map(e=>e.id));
 assert(nodes.size===d.nodes.length);assert(edges.size===d.edges.length);
 for(const e of d.edges){assert(nodes.has(e.from));assert(nodes.has(e.to));}
 for(const s of d.steps){steps++;for(const x of s.focus)assert(nodes.has(x));for(const x of s.active)assert(edges.has(x));for(const x of Object.keys(s.states))assert(nodes.has(x));assert(s.fields.length>0);assert(s.bands.length>0);}
}
assert.equal(seen.size,6);assert(steps>=40);
console.log(JSON.stringify({ok:true,commandAssertions:count,diagrams:seen.size,steps}));
