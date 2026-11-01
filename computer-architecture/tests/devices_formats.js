'use strict';const assert=require('node:assert/strict'),F=require('../labs/devices/formats.js');let count=0;function eq(a,b){assert.deepEqual(a,b);count++;}function bad(f,pattern){assert.throws(f,pattern);count++;}
eq(F.hex(F.readHeader(0x2000,512)),'00 00 00 80 01 00 5A FF 00 00 20 00');
eq(F.readHeader(0x2000,4)[7],15);eq(F.readHeader(0x2000,4096).slice(0,4),[0,0,0,0]);
const c=F.completions(0x2000,512);eq(c.length,8);eq(F.hex(c[0].header),'4A 00 00 10 00 00 02 00 01 00 5A 00');eq(c.map(x=>x.byteCount),[512,448,384,320,256,192,128,64]);eq(c.map(x=>x.lowerAddress),[0,64,0,64,0,64,0,64]);eq(c.reduce((a,x)=>a+x.bytes,0),512);
eq(F.hex(F.rxOwned(0x6000,512)),'00 82 00 00 00 60 00 00 00 00 00 00 00 00 00 00');eq(F.rxReturnedWord({used:128,frameLength:128,first:true,last:true}),0xC0800080);
bad(()=>F.readHeader(0x2F00,512),/4KiB/);bad(()=>F.readHeader(0x2001,512),/aligned/);bad(()=>F.readHeader(0xFFFFFFFC,8),/overflow/);bad(()=>F.readHeader(0x2000,0),/positive/);bad(()=>F.completions(0x2000,512,256),/Finite/);bad(()=>F.rxOwned(0xFFFFFF00,512),/overflow/);bad(()=>F.rxOwned(0x6000,16384),/width/);bad(()=>F.rxReturnedWord({used:128,frameLength:64,first:true,last:true}),/exceeds/);bad(()=>F.rxReturnedWord({used:128,frameLength:128,first:true,last:true,extension:true}),/extension/);
console.log('DEVICES-FORMATS1: '+count+' checks PASS; encodings only, no hardware I/O');
