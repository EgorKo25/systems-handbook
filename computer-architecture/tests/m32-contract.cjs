/* Byte/data contract checks. This runs in Node, not on a native RISC-V CPU. */
'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),C=require('../labs/m32/contract.js');let checks=0;
function check(name,fn){fn();checks++;}
check('script and JSON data agree',()=>assert.deepEqual(C.data,JSON.parse(fs.readFileSync(path.join(root,'labs/m32/contract.json'),'utf8'))));
check('all instruction words have exact little-endian bytes',()=>{for(const i of C.data.physical.instructions){const b=Buffer.alloc(4);b.writeUInt32LE(i.word);assert.deepEqual(i.bytes,Array.from(b));}});
check('instruction fields match independent arithmetic encoding',()=>assert.deepEqual(C.data.physical.instructions.map(x=>x.word),[2*4096+5*128+0x37,5*32768+2*4096+6*128+3,2**20+6*32768+6*128+0x13,16*2**25+6*2**20+5*32768+2*4096+0x23,0x100073]));
check('physical image has separate input/output',()=>{const r=C.image();assert.equal(r.length,65536);assert.equal(C.wordLE(r.slice(0x2000,0x2004)),42);assert.equal(C.wordLE(r.slice(0x2200,0x2204)),0);});
check('virtual image explicitly changes first instruction and adds tables',()=>{const r=C.image('sv32');assert.deepEqual(Array.from(r.slice(0x1000,0x1004)),[0xb7,0x22,0x40,0]);for(const p of C.data.sv32.ptes)assert.equal(C.wordLE(r.slice(p.address,p.address+4)),p.word);});
check('Sv32 complete table arithmetic',()=>{const r=C.image('sv32'),read=a=>C.wordLE(r.slice(a,a+4));for(const m of C.data.sv32.mappings){const v1=Math.floor(m.va/2**22)%1024,v0=Math.floor(m.va/4096)%1024,off=m.va%4096;const p=read(0x8000+v1*4);assert.equal(p&0x3ff,1);const lower=Math.floor(p/1024)*4096,leaf=read(lower+v0*4);assert.equal(Math.floor(leaf/1024)*4096+off,m.pa);}});
check('cache geometry calculation',()=>{for(const f of C.data.cache.fixtures){assert.equal(f.address%16,f.offset);assert.equal(Math.floor(f.address/16)%4,f.set);assert.equal(Math.floor(f.address/64),f.tag);}});
check('OS is a different model with exact offsets',()=>{const o=C.data.os_bridge;assert.equal(o.ram_image_continuation,false);assert(o.user_pa>=65536);assert.equal(o.vpn*4096+o.offset,o.user_va);assert.equal(o.pfn*4096+o.offset,o.user_pa);assert.equal(Math.floor(o.vpn/1024),o.directory_index);assert.equal(o.vpn%1024,o.table_index);});
check('input validation rejects width/length mistakes',()=>{for(const n of [-1,1.5,2**32,NaN])assert.throws(()=>C.bytesLE(n));for(const b of [[1,2,3],[0,0,0,256]])assert.throws(()=>C.wordLE(b));assert.throws(()=>C.image('pretend-full-machine'));});
console.log(JSON.stringify({kind:'pure shared-data model; no native CPU',checks,passed:true}));
