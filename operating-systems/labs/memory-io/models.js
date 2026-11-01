(function (root) {
  'use strict';
  const PAGE = 4096;
  function integer(value, min, max, label) {
    if (typeof value === 'string') {
      if (!/^(?:0x[0-9a-f]+|[0-9]+)$/i.test(value.trim())) throw new Error(label + ': требуется целое число');
      value = Number(value.trim());
    }
    if (!Number.isSafeInteger(value) || value < min || value > max) throw new Error(label + ': вне диапазона');
    return value;
  }
  function real(value, label) {
    if (typeof value === 'string' && !value.trim()) throw new Error(label + ': число не задано');
    value = Number(value);
    if (!Number.isFinite(value) || value < 0) throw new Error(label + ': требуется неотрицательное конечное число');
    return value;
  }
  function decode(bytes) {
    if (!Array.isArray(bytes) || bytes.length !== 4) throw new Error('Для uint32 нужны ровно четыре байта');
    return bytes.reduce((sum, byte, index) => sum + integer(byte, 0, 255, 'байт') * 256 ** index, 0);
  }
  function encode(value) {
    value = integer(value, 0, 0xffffffff, 'uint32');
    return Array.from({length:4}, (_, i) => Math.floor(value / 256 ** i) % 256);
  }
  function translate(address, frame, rootBase = 0x8000, tableBase = 0x9000) {
    address = integer(address, 0, 0xffffffff, 'виртуальный адрес');
    frame = integer(frame, 0, 0xfffff, 'номер кадра');
    for (const base of [rootBase,tableBase]) if (!Number.isSafeInteger(base) || base < 0 || base > 0xfffff000 || base % PAGE) throw new Error('Таблица требует выровненную базу');
    const outer = Math.floor(address / 2 ** 22), inner = Math.floor(address / PAGE) % 1024, offset = address % PAGE;
    return {address,outer,inner,offset,vpn:Math.floor(address/PAGE),rootEntry:rootBase+outer*4,
      tableEntry:tableBase+inner*4,frame,frameBase:frame*PAGE,physical:frame*PAGE+offset,
      assumption:'Модель 32 бита, уровни 10/10/12: заданные записи существуют, разрешают доступ и указывают на выбранные таблицу/кадр.'};
  }
  function range(address, length) {
    address = integer(address,0,0xffffffff,'начало');length = integer(length,1,0x100000000,'длина');
    if (address + length > 0x100000000) throw new Error('Диапазон вышел за 32 бита');
    const first = Math.floor(address/PAGE), last = Math.floor((address+length-1)/PAGE);
    return {first,last,pages:last-first+1,crosses:first!==last};
  }
  // M32-2L-v1 is our specified educational format, not an x86/Arm PTE.
  const BITS={P:1,W:2,U:4,X:8,A:16,D:32,C:64};
  function entry(frame,flags) {frame=integer(frame,0,0xfffff,'PFN');flags=integer(flags,0,127,'признаки');return frame*PAGE+flags;}
  function inspectEntry(word,directory=false) {
    word=integer(word,0,0xffffffff,'запись');
    const present=!!(word&BITS.P);
    if(word&0xf80 || directory&&(word&(BITS.D|BITS.C)) || !present&&word!==0) throw new Error('Malformed: зарезервированное поле M32-2L-v1');
    return {word,bytes:encode(word),present,frame:word>>>12,flags:Object.fromEntries(Object.entries(BITS).map(([name,mask])=>[name,!!(word&mask)]))};
  }
  function rawWalk(address,directoryWord,leafWord,operation='read',user=true) {
    if(!['read','write','execute'].includes(operation))throw new Error('Неизвестная операция');
    address=integer(address,0,0xffffffff,'адрес');let d,l;
    try {d=inspectEntry(directoryWord,true);}catch(e){return {fault:'malformed-directory',reason:e.message};}
    if(!d.present)return {fault:'not-present-directory'};
    try {l=inspectEntry(leafWord);}catch(e){return {fault:'malformed-leaf',reason:e.message};}
    const path=translate(address,l.frame,0x8000,d.frame*PAGE);
    if(!l.present)return {fault:'not-present-leaf',path};
    const effective={user:d.flags.U&&l.flags.U,write:d.flags.W&&l.flags.W,execute:d.flags.X&&l.flags.X};
    if(user&&!effective.user || operation==='write'&&!effective.write || operation==='execute'&&!effective.execute)
      return {fault:'protection',path,effective,directory:d,leaf:l,cowCandidate:operation==='write'&&l.flags.C};
    return {fault:null,path,effective,directory:d,leaf:l,directoryAfter:(directoryWord|BITS.A)>>>0,
      leafAfter:(leafWord|BITS.A|(operation==='write'?BITS.D:0))>>>0};
  }
  class Shootdown {
    constructor(){this.mapping=true;this.published=false;this.references=1;this.dmaPins=0;this.cpus={CPU0:{valid:true,ack:false},CPU1:{valid:true,ack:false}};this.reused=false;}
    revoke(){if(!this.mapping)throw new Error('Запись уже снята');this.mapping=false;this.published=true;return this.state();}
    ack(cpu){if(!this.published||!this.cpus[cpu])throw new Error('Нет опубликованного запроса этому CPU');this.cpus[cpu]={valid:false,ack:true};return this.state();}
    releaseReference(){if(this.mapping||this.references!==1)throw new Error('Сначала снять отображение');this.references=0;return this.state();}
    reuse(){if(this.mapping||this.references||this.dmaPins||Object.values(this.cpus).some(c=>!c.ack))throw new Error('Раннее reuse: остались ссылки/переводы/устройство');this.reused=true;return this.state();}
    state(){return {mapping:this.mapping,references:this.references,dmaPins:this.dmaPins,cpus:JSON.parse(JSON.stringify(this.cpus)),reused:this.reused,assumption:'Модель ack включает завершение архитектурно необходимой инвалидации и старых доступов; не инструкция для настоящего драйвера.'};}
  }
  class Cow {
    constructor() {this.frames=new Map([[0x12a,new Uint8Array(PAGE)]]);this.frames.get(0x12a).set(encode(42),0x124);this.owners={P:0x12a};this.permissions={P:{W:true,C:false,D:false}};this.copies=0;this.nextFrame=0x12b;this.lastTrace=[];}
    fork() {if ('Q' in this.owners) throw new Error('Q уже создан; состояние не сброшено');this.owners.Q=this.owners.P;this.permissions.P.W=false;this.permissions.P.C=true;this.permissions.Q={W:false,C:true,D:false};this.lastTrace=['Удержать изменение отображения','PTE P:W0/C1, PTE Q:W0/C1','Инвалидировать прежние переводы TLB с правом записи и дождаться подтверждений','Разрешить исполнение Q'];return this.state();}
    write(owner,value) {
      if (!(owner in this.owners)) throw new Error('Неизвестный владелец');
      const bytes=encode(value),old=this.owners[owner],writable=this.permissions[owner].W;
      if(!writable&&!this.permissions[owner].C)throw new Error('Нет права записи и отметки COW');
      this.lastTrace=[];
      if(!writable){
        this.lastTrace.push('Защитный fault; проверить программное отображение: частная запись допустима');
        if (Object.values(this.owners).filter(frame=>frame===old).length>1) {
          const fresh=this.nextFrame++,prior=decode(Array.from(this.frames.get(old).slice(0x124,0x128)));
          this.frames.set(fresh,this.frames.get(old).slice());this.owners[owner]=fresh;this.copies++;
          this.lastTrace.push('Ядро копирует 4096 байт в новый кадр; число пока '+prior);
        }else this.lastTrace.push('Кадр уже имеет одного владельца; копирование не требуется');
        this.permissions[owner]={W:true,C:false,D:false};
        this.lastTrace.push('Установить частный доступный записи PTE и согласовать TLB','Повторить остановленную инструкцию записи; установить D');
      }else this.lastTrace.push('W=1: CPU записывает четыре байта в существующий кадр; установить D');
      this.frames.get(this.owners[owner]).set(bytes,0x124);this.permissions[owner].D=true;return this.state();
    }
    state() {return {virtual:0x00403124,copies:this.copies,copiedBytes:this.copies*PAGE,
      lastTrace:[...this.lastTrace],owners:Object.fromEntries(Object.entries(this.owners).map(([name,frame])=>[name,{frame,value:decode(Array.from(this.frames.get(frame).slice(0x124,0x128))),shared:Object.values(this.owners).filter(f=>f===frame).length>1,
        permissions:{...this.permissions[name]},pte:entry(frame,BITS.P|BITS.U|BITS.A|(this.permissions[name].W?BITS.W:0)|(this.permissions[name].C?BITS.C:0)|(this.permissions[name].D?BITS.D:0))}]))};}
  }
  class Descriptors {
    constructor() {this.bytes=encode(42);this.fds=new Map();this.opens=new Map();this.next=1;}
    nextFd() {let fd=3;while(this.fds.has(fd)) fd++;return fd;}
    description(fd) {if (!this.fds.has(fd)) throw new Error('EBADF: дескриптор закрыт или отсутствует');return this.opens.get(this.fds.get(fd));}
    open() {const fd=this.nextFd(),id='O'+this.next++;this.opens.set(id,{id,offset:0});this.fds.set(fd,id);return fd;}
    dup(fd) {this.description(fd);const next=this.nextFd();this.fds.set(next,this.fds.get(fd));return next;}
    read(fd,count) {count=integer(count,0,64,'длина');const d=this.description(fd),bytes=this.bytes.slice(d.offset,d.offset+count);d.offset+=bytes.length;return bytes;}
    pwrite(fd,bytes,offset) {
      this.description(fd);offset=integer(offset,0,64,'смещение');
      if (!Array.isArray(bytes) || bytes.length+offset>64) throw new Error('Размер модельного файла ограничен 64 байтами');
      bytes=bytes.map(b=>integer(b,0,255,'байт'));if(bytes.length===0)return 0;while(this.bytes.length<offset+bytes.length)this.bytes.push(0);
      this.bytes.splice(offset,bytes.length,...bytes);return bytes.length;
    }
    write(fd,bytes) {const d=this.description(fd),count=this.pwrite(fd,bytes,d.offset);d.offset+=count;return count;}
    close(fd) {this.description(fd);const id=this.fds.get(fd);this.fds.delete(fd);if(!Array.from(this.fds.values()).includes(id))this.opens.delete(id);}
    state() {return {bytes:[...this.bytes],fds:Object.fromEntries(this.fds),openings:Array.from(this.opens.values(),o=>({...o}))};}
  }
  function pressure(production,service,budget,initial=0) {
    production=real(production,'производство');service=real(service,'сохранение');budget=real(budget,'бюджет');initial=real(initial,'начальный объём');
    if (initial>budget) throw new Error('Начальный объём превышает бюджет');const net=production-service;
    return {production,service,budget,initial,net,fillSeconds:net>0?(budget-initial)/net:null,drainSeconds:net<0?initial/-net:null,units:'MiB, MiB/s, seconds; постоянные скорости без объединения перезаписей'};
  }
  class Durability {
    constructor() {this.stage=0;}
    advance() {if(this.stage===4) throw new Error('Все этапы завершены; сброс возможен только явно');this.stage++;return this.state();}
    state() {
      return {stage:this.stage,visible:this.stage>=3?43:42,temp:this.stage>=1?43:null,tempDurable:this.stage>=2,
        directoryDurable:this.stage>=4,crashAllowed:this.stage===3?[42,43]:[this.stage>=4?43:42],
        names:['Исходная42 устойчива','Новый файл записан в буферы','fsync нового файла','rename опубликовал43','fsync каталога'][this.stage],
        assumption:'Идеализированное локальное ФС/устройство честно исполняет sync. До sync каталога показан ограниченный набор возможных исходов; это не симуляция всех аварий реальной ФС.'};
    }
  }
  // One 32-frame arena. This is an original buddy model, not Linux allocator code.
  class Slots64 {
    constructor(base=0x500000){this.base=integer(base,0,0xfffff000,'база');if(this.base%4096)throw new Error('Нужна выровненная страница');this.bitmap=0n;this.live=0;}
    allocate(bytes){integer(bytes,1,64,'размер');let i=0;while(i<64&&(this.bitmap&(1n<<BigInt(i))))i++;if(i===64)throw new Error('Страница заполнена');this.bitmap|=1n<<BigInt(i);this.live++;return this.base+64*i;}
    release(address){address=integer(address,this.base,this.base+4095,'адрес');const offset=address-this.base;if(offset%64)throw new Error('Адрес не начала слота');const bit=1n<<BigInt(offset/64);if(!(this.bitmap&bit))throw new Error('Слот уже свободен');this.bitmap&=~bit;this.live--;}
    state(){return {base:this.base,bitmap:'0x'+this.bitmap.toString(16).padStart(16,'0'),live:this.live,returnable:this.live===0};}
  }
  class Buddy {
    constructor(){this.free=Array.from({length:6},()=>new Set());this.free[5].add(0);this.allocated=new Map();}
    allocate(order){
      order=integer(order,0,5,'порядок');let found=order;while(found<=5&&!this.free[found].size)found++;
      if(found>5)throw new Error('Нет подходящего выровненного блока');
      const base=Math.min(...this.free[found]);this.free[found].delete(base);const trace=[];
      while(found>order){found--;const right=base+2**found;this.free[found].add(right);trace.push({order:found,left:base,right});}
      this.allocated.set(base,order);this.check();return {base,order,frames:2**order,trace};
    }
    release(base){
      base=integer(base,0,31,'начало');if(!this.allocated.has(base))throw new Error('Неизвестный либо уже освобождённый блок');
      let order=this.allocated.get(base);this.allocated.delete(base);const trace=[];
      while(order<5){const buddy=base^(2**order);if(!this.free[order].has(buddy))break;this.free[order].delete(buddy);trace.push({order,left:Math.min(base,buddy),right:Math.max(base,buddy)});base=Math.min(base,buddy);order++;}
      this.free[order].add(base);this.check();return {base,order,trace};
    }
    check(){const occupied=Array(32).fill(0);let total=0;const mark=(base,order)=>{if(base%2**order)throw new Error('Нарушено выравнивание');for(let i=base;i<base+2**order;i++){if(i>=32||occupied[i]++)throw new Error('Перекрытие блоков');total++;}};this.free.forEach((set,order)=>set.forEach(base=>mark(base,order)));this.allocated.forEach((order,base)=>mark(base,order));if(total!==32)throw new Error('Потерян кадр');return true;}
    state(){return {free:this.free.map(set=>Array.from(set).sort((a,b)=>a-b)),allocated:Array.from(this.allocated,([base,order])=>({base,order})),freeFrames:this.free.reduce((n,set,order)=>n+set.size*2**order,0)};}
  }
  // Deliberately finite CLOCK: one entry per resident frame; writes are separate events.
  class Clock {
    constructor(pages){
      if(!Array.isArray(pages)||!pages.length||pages.length>64)throw new Error('Нужны 1–64 страницы');
      this.pages=pages.map((p,i)=>({id:String(p.id??i),ref:!!p.ref,dirty:!!p.dirty,pinned:!!p.pinned,backing:p.backing??'file',writeback:false,resident:true,generation:0,submittedGeneration:null}));
      if(new Set(this.pages.map(p=>p.id)).size!==pages.length||this.pages.some(p=>!['file','swap','none'].includes(p.backing)))throw new Error('Неоднозначная страница или backing');this.hand=0;
    }
    step(){const p=this.pages[this.hand];this.hand=(this.hand+1)%this.pages.length;let action;
      if(!p.resident)action='already-free';else if(p.pinned)action='pinned';else if(p.writeback)action='writeback-pending';else if(p.ref){p.ref=false;action='second-chance';}
      else if(p.backing==='none')action='no-backing';else if(p.dirty){p.writeback=true;p.submittedGeneration=p.generation;action='start-writeback';}else {p.resident=false;action='evicted';}
      return {id:p.id,action,hand:this.hand};
    }
    touch(id,write=false){const p=this.pages.find(p=>p.id===id);if(!p||!p.resident)throw new Error('Для отсутствующей страницы сначала нужен fault');p.ref=true;if(write){p.dirty=true;p.generation++;}}
    complete(id,success=true){const p=this.pages.find(p=>p.id===id);if(!p||!p.writeback)throw new Error('Нет ожидаемой записи');p.writeback=false;if(success&&p.submittedGeneration===p.generation)p.dirty=false;p.submittedGeneration=null;return {...p};}
    state(){return {hand:this.hand,pages:this.pages.map(p=>({...p}))};}
  }
  // OSJ1: an original fixed-record, single-block-per-transaction teaching journal.
  function checksum(bytes){let hash=0x811c9dc5;for(const byte of bytes)hash=Math.imul(hash^byte,0x01000193)>>>0;return hash;}
  function journalRecord(kind,sequence,target=0,value=0){
    if(![1,2].includes(kind))throw new Error('kind: 1 DATA либо 2 COMMIT');sequence=integer(sequence,1,0xffffffff,'sequence');target=integer(target,0,0xffffffff,'block');value=integer(value,0,0xffffffff,'value');
    if(kind===2&&(target||value))throw new Error('COMMIT не содержит target/value');
    const raw=[0x4f,0x53,0x4a,0x31,kind,0,kind===1?4:0,0,...encode(sequence),...encode(target),...encode(value)];return [...raw,...encode(checksum(raw))];
  }
  function parseRecord(raw){
    if(!Array.isArray(raw)||raw.length!==24)throw new Error('Запись OSJ1 должна содержать 24 байта');raw=raw.map(v=>integer(v,0,255,'байт'));
    if(raw.slice(0,4).some((v,i)=>v!==[0x4f,0x53,0x4a,0x31][i]))throw new Error('Неизвестный magic/version');
    if(checksum(raw.slice(0,20))!==decode(raw.slice(20)))throw new Error('Checksum mismatch');
    const kind=raw[4],sequence=decode(raw.slice(8,12)),target=decode(raw.slice(12,16)),value=decode(raw.slice(16,20));
    if(![1,2].includes(kind)||raw[5]||raw[6]!== (kind===1?4:0)||raw[7]||!sequence||kind===2&&(target||value))throw new Error('Некорректные поля записи');
    return {kind,sequence,target,value};
  }
  function recoverJournal(home,records,checkpoint=0){
    checkpoint=integer(checkpoint,0,0xffffffff,'checkpoint');const blocks={...home};for(const [key,value]of Object.entries(blocks)){integer(key,0,0xffffffff,'home block');integer(value,0,0xffffffff,'home value');}
    if(!Array.isArray(records)||records.length>4096)throw new Error('Слишком большой журнал');let pending=null,last=checkpoint;const applied=[];let stop='end';
    for(const raw of records){let r;try{r=parseRecord(raw);}catch(e){stop=e.message;break;}
      if(r.kind===1){if(pending||r.sequence<=last){stop='Нарушен порядок DATA';break;}pending=r;}
      else {if(!pending||pending.sequence!==r.sequence){stop='COMMIT без соответствующей DATA';break;}blocks[pending.target]=pending.value;last=r.sequence;applied.push(last);pending=null;}
    }
    if(pending&&stop==='end')stop='Неполная транзакция без COMMIT';return {blocks,last,applied,stop};
  }
  const api={PAGE,BITS,integer,encode,decode,translate,range,entry,inspectEntry,rawWalk,Shootdown,Cow,Descriptors,pressure,Durability,Slots64,Buddy,Clock,checksum,journalRecord,parseRecord,recoverJournal};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.MemoryIOModels=api;
})(typeof globalThis==='object'?globalThis:this);
