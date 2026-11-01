/* Original finite RV32I-subset teaching engine. One step is NOT one CPU cycle.
   No network, operating system, timing, MMU, interrupts or full ISA emulation. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.M32Logic = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const SIZE=65536, ENTRY=0x1000, TRACE_LIMIT=1000;
  const PROGRAM=Object.freeze([0x000022b7,0x0002a303,0x00130313,0x2062a023,0x00100073]);
  const u32=n=>n>>>0;
  const hex=(n,width=8)=>u32(n).toString(16).toUpperCase().padStart(width,'0');
  const signed=(n,bits)=>{const sign=2**(bits-1);return n>=sign?n-2**bits:n;};
  function checkWord(address){
    if(!Number.isInteger(address)||address<0||address>SIZE-4)throw new Error('address-out-of-range');
    if(address%4)throw new Error('address-misaligned');
  }
  function read32(memory,address){checkWord(address);return u32(memory[address]+memory[address+1]*256+memory[address+2]*65536+memory[address+3]*16777216);}
  function write32(memory,address,value){checkWord(address);for(let i=0;i<4;i++)memory[address+i]=u32(value)>>>8*i&255;}
  function create(){
    const s={version:1,profile:'M32-physical-RV32I-five',pc:ENTRY,regs:new Uint32Array(32),memory:new Uint8Array(SIZE),status:'ready',retired:0,attempts:0,trap:null,trace:[],traceDropped:0};
    PROGRAM.forEach((word,i)=>write32(s.memory,ENTRY+4*i,word));write32(s.memory,0x2000,42);return s;
  }
  function decode(word){
    word=u32(word);const opcode=word&127,rd=word>>>7&31,funct3=word>>>12&7,rs1=word>>>15&31,rs2=word>>>20&31;
    const result={word,opcode,rd,funct3,rs1,rs2};
    if(word===0x00100073)return {...result,op:'EBREAK',format:'SYSTEM',immediate:null};
    if(opcode===0x37)return {word,opcode,rd,op:'LUI',format:'U',immediate:u32(word&0xfffff000),upper:word>>>12};
    if(opcode===0x13&&funct3===0)return {...result,op:'ADDI',format:'I',immediate:signed(word>>>20,12)};
    if(opcode===3&&funct3===2)return {...result,op:'LW',format:'I',immediate:signed(word>>>20,12)};
    if(opcode===0x23&&funct3===2){const imm=(word>>>25)*32+(word>>>7&31);return {...result,op:'SW',format:'S',immediate:signed(imm,12)};}
    throw new Error('unsupported-instruction');
  }
  function record(s,event){s.trace.push(event);if(s.trace.length>TRACE_LIMIT){const count=s.trace.length-TRACE_LIMIT;s.trace.splice(0,count);s.traceDropped+=count;}}
  function stop(s,cause,event){s.status='trap';s.trap={cause,pc:s.pc};event.kind='trap';event.cause=cause;event.pcAfter=s.pc;event.retiredAfter=s.retired;record(s,event);return event;}
  function step(s){
    if(s.status==='trap'||s.status==='breakpoint')return {kind:'viewer-stopped',cause:s.trap.cause,pcBefore:s.pc,pcAfter:s.pc,changed:false};
    s.attempts++;
    const event={kind:'instruction',pcBefore:s.pc,pcAfter:s.pc,retiredBefore:s.retired,registers:[],memory:[],word:null,bytes:[]};
    let d;
    try{event.word=read32(s.memory,s.pc);event.bytes=Array.from(s.memory.slice(s.pc,s.pc+4));d=decode(event.word);event.decoded=d;}
    catch(error){return stop(s,'fetch/decode:'+error.message,event);}
    if(d.op==='EBREAK'){s.status='breakpoint';s.trap={cause:'breakpoint',pc:s.pc};event.kind='trap';event.cause='breakpoint';event.retiredAfter=s.retired;record(s,event);return event;}
    const source=s.regs[d.rs1],second=s.regs[d.rs2];event.operands={rs1:source,rs2:second};
    let value,address;
    try{
      if(d.op==='LUI')value=d.immediate;
      if(d.op==='ADDI')value=u32(source+d.immediate);
      if(d.op==='LW'){address=u32(source+d.immediate);value=read32(s.memory,address);event.read={address,bytes:Array.from(s.memory.slice(address,address+4)),value};}
      if(d.op==='SW'){
        address=u32(source+d.immediate);checkWord(address);
        const before=Array.from(s.memory.slice(address,address+4));write32(s.memory,address,second);
        event.memory.push({address,before,after:Array.from(s.memory.slice(address,address+4)),value:second});
      }else if(d.rd!==0){event.registers.push({register:d.rd,before:s.regs[d.rd],after:u32(value)});s.regs[d.rd]=u32(value);}
      else event.discardedX0=true;
    }catch(error){return stop(s,'data:'+error.message,event);}
    s.regs[0]=0;s.pc=u32(s.pc+4);s.retired++;s.status='ready';event.pcAfter=s.pc;event.retiredAfter=s.retired;record(s,event);return event;
  }
  function run(s,limit=16){if(!Number.isInteger(limit)||limit<1||limit>1000)throw new Error('invalid-step-limit');const events=[];for(let i=0;i<limit&&s.status==='ready';i++)events.push(step(s));return events;}
  function snapshot(s){return {version:s.version,profile:s.profile,pc:s.pc,regs:Array.from(s.regs),memory:Array.from(s.memory),status:s.status,retired:s.retired,attempts:s.attempts,trap:s.trap,trace:s.trace,traceDropped:s.traceDropped};}
  function restore(data){
    if(!data||data.version!==1||data.profile!=='M32-physical-RV32I-five')throw new Error('unsupported-snapshot');
    const valid=(n,max)=>Number.isInteger(n)&&n>=0&&n<=max;
    if(!valid(data.pc,0xffffffff)||!Array.isArray(data.regs)||data.regs.length!==32||!data.regs.every(n=>valid(n,0xffffffff))||data.regs[0]!==0)throw new Error('invalid-registers');
    if(!Array.isArray(data.memory)||data.memory.length!==SIZE||!data.memory.every(n=>valid(n,255)))throw new Error('invalid-memory');
    if(!['ready','trap','breakpoint'].includes(data.status)||!valid(data.retired,1000000)||!valid(data.attempts,1000000)||data.attempts<data.retired)throw new Error('invalid-progress');
    if(data.status!=='ready'&&(!data.trap||typeof data.trap.cause!=='string'||data.trap.pc!==data.pc))throw new Error('invalid-trap');
    if(data.status==='ready'&&data.trap!==null)throw new Error('invalid-ready-trap');
    if(data.status==='breakpoint'&&data.trap.cause!=='breakpoint')throw new Error('invalid-breakpoint');
    // A trace is presentation evidence. Limit its size; never execute its text.
    const bytes=a=>Array.isArray(a)&&a.length===4&&a.every(n=>valid(n,255));
    const event=e=>e&&['instruction','trap'].includes(e.kind)&&valid(e.pcBefore,0xffffffff)&&valid(e.pcAfter,0xffffffff)&&
      (e.word===null||valid(e.word,0xffffffff))&&Array.isArray(e.bytes)&&(e.bytes.length===0||bytes(e.bytes))&&
      Array.isArray(e.registers)&&e.registers.every(r=>r&&valid(r.register,31)&&valid(r.before,0xffffffff)&&valid(r.after,0xffffffff))&&
      Array.isArray(e.memory)&&e.memory.every(m=>m&&valid(m.address,SIZE-4)&&bytes(m.before)&&bytes(m.after))&&
      (!e.read||(valid(e.read.address,SIZE-4)&&bytes(e.read.bytes)&&valid(e.read.value,0xffffffff)))&&
      (!e.cause||typeof e.cause==='string');
    if(!Array.isArray(data.trace)||data.trace.length>TRACE_LIMIT||!data.trace.every(event))throw new Error('invalid-trace');
    const traceDropped=data.traceDropped===undefined?0:data.traceDropped;
    if(!valid(traceDropped,1000000)||traceDropped+data.trace.length>data.attempts)throw new Error('invalid-trace-progress');
    return {...data,traceDropped,regs:Uint32Array.from(data.regs),memory:Uint8Array.from(data.memory),trace:JSON.parse(JSON.stringify(data.trace))};
  }
  function addBits(a,b,width=4){
    if(!Number.isInteger(width)||width<1||width>16||!Number.isInteger(a)||!Number.isInteger(b)||a<0||b<0||a>=2**width||b>=2**width)throw new Error('invalid-adder-input');
    let carry=0;const rows=[];for(let i=0;i<width;i++){const x=a>>>i&1,y=b>>>i&1,sum=x^y^carry,next=(x&y)|(x&carry)|(y&carry);rows.push({bit:i,a:x,b:y,carryIn:carry,sum,carryOut:next});carry=next;}return {rows,result:(a+b)%(2**width),carryOut:carry};
  }
  function float32(value){const buffer=new ArrayBuffer(4),v=new DataView(buffer);v.setFloat32(0,value,false);const word=v.getUint32(0,false);return {word,hex:hex(word),sign:word>>>31,exponent:word>>>23&255,fraction:word&0x7fffff,value:v.getFloat32(0,false)};}
  function cmos(kind,a,b=0){
    if(!['NOT','NAND','NOR'].includes(kind)||![0,1].includes(a)||![0,1].includes(b))throw new Error('invalid-cmos-input');
    const on={P_A:a===0,N_A:a===1};if(kind!=='NOT'){on.P_B=b===0;on.N_B=b===1;}
    const networks=kind==='NOT'?{up:[['P_A']],down:[['N_A']]}:kind==='NAND'?{up:[['P_A'],['P_B']],down:[['N_A','N_B']]}:{up:[['P_A','P_B']],down:[['N_A'],['N_B']]};
    const conducting=paths=>paths.filter(path=>path.every(name=>on[name]));
    const up=conducting(networks.up),down=conducting(networks.down);
    if((up.length>0)===(down.length>0))throw new Error('complementary-network-invariant');
    return {kind,a,b,on,networks,conductingUp:up,conductingDown:down,output:up.length?1:0,analogueTiming:false};
  }
  function rcCharge({resistanceOhm,capacitanceFarad,supplyVolt,timeSecond}){
    if(![resistanceOhm,capacitanceFarad,supplyVolt,timeSecond].every(Number.isFinite)||resistanceOhm<=0||capacitanceFarad<=0||supplyVolt<=0||timeSecond<0)throw new Error('invalid-rc-input');
    const tauSecond=resistanceOhm*capacitanceFarad;
    return {tauSecond,outputVolt:supplyVolt*(1-Math.exp(-timeSecond/tauSecond)),fullCycleSupplyJoule:capacitanceFarad*supplyVolt*supplyVolt,storedAtFullJoule:.5*capacitanceFarad*supplyVolt*supplyVolt};
  }
  return Object.freeze({SIZE,ENTRY,TRACE_LIMIT,PROGRAM,hex,u32,signed,checkWord,read32,write32,create,decode,step,run,snapshot,restore,addBits,float32,cmos,rcCharge});
}));
