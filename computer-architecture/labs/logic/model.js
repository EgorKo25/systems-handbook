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
  const encoding = Object.freeze({ lui: 0x37, addi: 0x13, lw: 0x03, sw: 0x23, branch: 0x63, bne: 1, jal: 0x6f, jalr: 0x67, ebreak: 0x00100073 });
  const wordAccess = 2;
  const SOURCE = [
    'lui x5, 0x2',
    'lw x6, 0(x5)',
    'addi x6, x6, 1',
    'sw x6, 512(x5)',
    'ebreak',
  ].join('\n');
  function register(text) {
    if (!/^x(?:[0-9]|[12][0-9]|3[01])$/i.test(text)) {
      throw new Error('Ожидается регистр x0–x31');
    }
    return Number(text.slice(1));
  }

  function immediate(text, min, max) {
    if (!/^-?(?:0x[0-9a-f]+|[0-9]+)$/i.test(text)) {
      throw new Error('Ожидается целая константа');
    }
    const value = text.startsWith('-') ? -Number(text.slice(1)) : Number(text);
    if (!Number.isSafeInteger(value) || value < min || value > max) {
      throw new Error('Константа выходит за границы поля');
    }
    return value;
  }

  function relativeOffset(operand, pc, labels, min, max) {
    if (/^[a-z_][a-z0-9_]*$/i.test(operand) && !labels.has(operand)) {
      throw new Error('Метка не найдена: ' + operand);
    }
    const offset = labels.has(operand) ? labels.get(operand) - pc : immediate(operand, min, max);
    if (offset < min || offset > max || offset % 2 !== 0) {
      throw new Error('Смещение должно быть чётным числом от ' + min + ' до ' + max);
    }
    return offset;
  }

  function assembleLine(line, pc, labels) {
    const source = line.replace(/#.*/, '').trim();
    if (!source) return null;
    const [name, operands = ''] = /^([^\s]+)(?:\s+(.*))?$/.exec(source).slice(1);
    const args = operands.split(',').map(arg => arg.trim());
    const op = name.toLowerCase();
    if (op === 'ebreak' && !operands) return encoding.ebreak;
    if (op === 'lui' && args.length === 2) {
      const upper = immediate(args[1], 0, 0xfffff);
      return ((upper << 12) | (register(args[0]) << 7) | encoding.lui) >>> 0;
    }
    if (op === 'addi' && args.length === 3) {
      const imm = immediate(args[2], -2048, 2047) & 0xfff;
      return ((imm << 20) | (register(args[1]) << 15) | (register(args[0]) << 7) | encoding.addi) >>> 0;
    }
    if (op === 'bne' && args.length === 3) {
      const imm = relativeOffset(args[2], pc, labels, -4096, 4094) & 0x1fff;
      return (((imm >>> 12) << 31) | (((imm >>> 5) & 63) << 25) | (register(args[1]) << 20)
        | (register(args[0]) << 15) | (encoding.bne << 12) | (((imm >>> 1) & 15) << 8)
        | (((imm >>> 11) & 1) << 7) | encoding.branch) >>> 0;
    }
    if (op === 'jal' && args.length === 2) {
      const imm = relativeOffset(args[1], pc, labels, -1048576, 1048574) & 0x1fffff;
      return (((imm >>> 20) << 31) | (((imm >>> 1) & 1023) << 21) | (((imm >>> 11) & 1) << 20)
        | (((imm >>> 12) & 255) << 12) | (register(args[0]) << 7) | encoding.jal) >>> 0;
    }
    if ((op === 'lw' || op === 'sw' || op === 'jalr') && args.length === 2) {
      const address = /^([^()]+)\(\s*(x[0-9]+)\s*\)$/i.exec(args[1]);
      if (!address) throw new Error('Ожидается смещение(регистр)');
      const imm = immediate(address[1].trim(), -2048, 2047) & 0xfff;
      const base = register(address[2]) << 15;
      const reg = register(args[0]);
      if (op === 'jalr') return ((imm << 20) | base | (reg << 7) | encoding.jalr) >>> 0;
      if (op === 'lw') return ((imm << 20) | base | (wordAccess << 12) | (reg << 7) | encoding.lw) >>> 0;
      return (((imm >>> 5) << 25) | (reg << 20) | base | (wordAccess << 12) | ((imm & 31) << 7) | encoding.sw) >>> 0;
    }
    throw new Error('Команда или форма операндов вне учебного профиля');
  }

  function assemble(source) {
    const labels = new Map();
    const instructions = [];
    for (const [index, original] of source.split(/\r?\n/).entries()) {
      let text = original.replace(/#.*/, '').trim();
      const line = index + 1;
      const address = ENTRY + 4 * instructions.length;
      const label = /^([a-z_][a-z0-9_]*):/i.exec(text);
      if (label) {
        if (labels.has(label[1])) throw new Error('Строка ' + line + '. Метка уже задана');
        labels.set(label[1], address);
        text = text.slice(label[0].length).trim();
      }
      if (!text) continue;
      if (address >= 0x2000) throw new Error('Строка ' + line + '. Код не помещается до входных данных');
      instructions.push({ address, text, line });
    }
    const listing = instructions.map(row => {
      try {
        return { ...row, word: assembleLine(row.text, row.address, labels) };
      } catch (error) {
        throw new Error('Строка ' + row.line + '. ' + error.message);
      }
    });
    if (!listing.length) throw new Error('Введите хотя бы одну команду');
    return listing;
  }

  const PROGRAM = Object.freeze(assemble(SOURCE).map(row => row.word));
  const u32=n=>n>>>0;
  const hex=(n,width=8)=>u32(n).toString(16).toUpperCase().padStart(width,'0');
  const signed=(n,bits)=>{const sign=2**(bits-1);return n>=sign?n-2**bits:n;};
  function checkWord(address){
    if(!Number.isInteger(address)||address<0||address>SIZE-4)throw new Error('address-out-of-range');
    if(address%4)throw new Error('address-misaligned');
  }
  function read32(memory,address){checkWord(address);return u32(memory[address]+memory[address+1]*256+memory[address+2]*65536+memory[address+3]*16777216);}
  function write32(memory,address,value){checkWord(address);for(let i=0;i<4;i++)memory[address+i]=u32(value)>>>8*i&255;}
  function create(source = SOURCE){
    const listing = assemble(source);
    const s={version:1,profile:'M32-physical-RV32I-five',pc:ENTRY,regs:new Uint32Array(32),memory:new Uint8Array(SIZE),status:'ready',retired:0,attempts:0,trap:null,trace:[],traceDropped:0};
    for (const { word, address } of listing) write32(s.memory,address,word);
    write32(s.memory,0x2000,42);return s;
  }
  function decode(word){
    word=u32(word);const opcode=word&127,rd=word>>>7&31,funct3=word>>>12&7,rs1=word>>>15&31,rs2=word>>>20&31;
    const result={word,opcode,rd,funct3,rs1,rs2};
    if(word===encoding.ebreak)return {...result,op:'EBREAK',format:'SYSTEM',immediate:null};
    if(opcode===encoding.lui)return {word,opcode,rd,op:'LUI',format:'U',immediate:u32(word&0xfffff000),upper:word>>>12};
    if(opcode===encoding.addi&&funct3===0)return {...result,op:'ADDI',format:'I',immediate:signed(word>>>20,12)};
    if(opcode===encoding.lw&&funct3===wordAccess)return {...result,op:'LW',format:'I',immediate:signed(word>>>20,12)};
    if(opcode===encoding.sw&&funct3===wordAccess){const imm=(word>>>25)*32+(word>>>7&31);return {...result,op:'SW',format:'S',immediate:signed(imm,12)};}
    if (opcode === encoding.jal) {
      const imm = ((word >>> 31) << 20) | (((word >>> 12) & 255) << 12)
        | (((word >>> 20) & 1) << 11) | (((word >>> 21) & 1023) << 1);
      return { word, opcode, rd, op: 'JAL', format: 'J', immediate: signed(imm, 21) };
    }
    if (opcode === encoding.jalr && funct3 === 0) {
      return { ...result, op: 'JALR', format: 'I', immediate: signed(word >>> 20, 12) };
    }
    if (opcode === encoding.branch && funct3 === encoding.bne) {
      const imm = ((word >>> 31) << 12) | (((word >>> 7) & 1) << 11)
        | (((word >>> 25) & 63) << 5) | (((word >>> 8) & 15) << 1);
      return { word, opcode, funct3, rs1, rs2, op: 'BNE', format: 'B', immediate: signed(imm, 13) };
    }
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
    let nextPC = u32(s.pc + 4);
    try{
      if(d.op==='LUI')value=d.immediate;
      if(d.op==='ADDI')value=u32(source+d.immediate);
      if(d.op==='LW'){address=u32(source+d.immediate);value=read32(s.memory,address);event.read={address,bytes:Array.from(s.memory.slice(address,address+4)),value};}
      if (d.op === 'JAL' || d.op === 'JALR') {
        const target = d.op === 'JAL' ? u32(s.pc + d.immediate) : u32((source + d.immediate) & ~1);
        if (target % 4 !== 0) return stop(s, 'instruction-address-misaligned', event);
        value = nextPC;
        nextPC = target;
        event.jump = { target, link: value, register: d.rd };
      }
      if (d.op === 'BNE') {
        const taken = source !== second;
        const target = u32(s.pc + d.immediate);
        event.branch = { taken, target };
        if (taken) {
          if (target % 4 !== 0) return stop(s, 'instruction-address-misaligned', event);
          nextPC = target;
        }
      } else if(d.op==='SW'){
        address=u32(source+d.immediate);checkWord(address);
        const before=Array.from(s.memory.slice(address,address+4));write32(s.memory,address,second);
        event.memory.push({address,before,after:Array.from(s.memory.slice(address,address+4)),value:second});
      }else if(d.rd!==0){event.registers.push({register:d.rd,before:s.regs[d.rd],after:u32(value)});s.regs[d.rd]=u32(value);}
      else event.discardedX0=true;
    }catch(error){return stop(s,'data:'+error.message,event);}
    s.regs[0]=0;s.pc=nextPC;s.retired++;s.status='ready';event.pcAfter=s.pc;event.retiredAfter=s.retired;record(s,event);return event;
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
  return Object.freeze({SIZE,ENTRY,TRACE_LIMIT,PROGRAM,SOURCE,assemble,hex,u32,signed,checkWord,read32,write32,create,decode,step,run,snapshot,restore,addBits,float32,cmos,rcCharge});
}));
