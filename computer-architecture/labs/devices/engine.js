/* M32-I/O1: original pure teaching model, NOT a real CPU/NIC/NVMe emulator. */
(function (root) {
'use strict';
const VERSION=1, SIZE=65536, SECTOR=512, INPUT=0x2000, OUTPUT=0x2200;
const CODE=[0xB7,0x22,0,0,0x03,0xA3,0x02,0,0x13,0x03,0x13,0,0x23,0xA0,0x62,0x20,0x73,0,0x10,0];
function copy(x){return JSON.parse(JSON.stringify(x));}
function fail(message){throw new Error(message);}
function integer(x,min,max,name){if(!Number.isInteger(x)||x<min||x>max)fail(name+' вне допустимого диапазона');}
function bytes(x,n,name){if(!Array.isArray(x)||x.length!==n||x.some(v=>!Number.isInteger(v)||v<0||v>255))fail(name+': неверный массив байтов');}
function initial(){
 const ram=Array(SIZE).fill(0);ram.splice(0x1000,CODE.length,...CODE);
 const media=Array(SECTOR).fill(0);media[0]=0x2A;
 return {schema:'M32-I/O1',version:VERSION,ram,media,cache:null,descriptor:null,completion:null,irq:{enabled:true,pending:false,delivered:false,acknowledged:false,vector:0x1800},cpu:{pc:0x1000,resultReady:false,trap:false,mode:'U'},iommu:{enabled:false,device:1,mappings:[{iova:0x4000,pa:INPUT,length:SECTOR,device:1,write:true,read:false},{iova:0x4200,pa:OUTPUT,length:SECTOR,device:1,write:false,read:true}]},published:false,readComplete:false,readObserved:false,outputPrepared:false,writeAccepted:false,writeComplete:false,flushPending:false,flushed:false,powerLosses:0,trace:[]};
}
function validate(s){
 if(!s||s.schema!=='M32-I/O1'||s.version!==VERSION)fail('Неизвестная схема/версия состояния');
 bytes(s.ram,SIZE,'RAM');bytes(s.media,SECTOR,'media');if(s.cache!==null)bytes(s.cache,SECTOR,'cache');
 if(!s.cpu||!s.irq||!s.iommu||!Array.isArray(s.trace))fail('Отсутствует обязательное состояние');
 for(const k of ['published','readComplete','readObserved','outputPrepared','writeAccepted','writeComplete','flushPending','flushed'])if(typeof s[k]!=='boolean')fail('Неверное логическое поле '+k);
 integer(s.cpu.pc,0,0xFFFFFFFF,'PC');integer(s.powerLosses,0,1000000,'powerLosses');
 for(const k of ['resultReady','trap'])if(typeof s.cpu[k]!=='boolean')fail('Неверное CPU поле');
 if(!['U','handler'].includes(s.cpu.mode))fail('Неизвестный CPU mode');
 for(const k of ['enabled','pending','delivered','acknowledged'])if(typeof s.irq[k]!=='boolean')fail('Неверное IRQ поле');
 integer(s.irq.vector,0,65532,'vector');if(s.irq.vector%4)fail('Vector не выровнен');
 if(typeof s.iommu.enabled!=='boolean'||!Array.isArray(s.iommu.mappings))fail('Неверный IOMMU');
 integer(s.iommu.device,0,65535,'device');
 for(const m of s.iommu.mappings){integer(m.iova,0,0xFFFFFFFF,'IOVA');integer(m.pa,0,SIZE-1,'mapping PA');integer(m.length,1,SIZE,'mapping length');integer(m.device,0,65535,'mapping device');if(m.pa+m.length>SIZE)fail('Mapping вне RAM');if(m.iova+m.length>0x100000000)fail('Mapping выходит за32бит IOVA');if(typeof m.read!=='boolean'||typeof m.write!=='boolean')fail('Mapping permissions');}
 if(s.descriptor){const d=s.descriptor;if(!['READ','WRITE'].includes(d.op)||!['host','device','completed'].includes(d.owner))fail('Descriptor op/owner');integer(d.address,0,0xFFFFFFFF,'descriptor address');integer(d.length,1,SECTOR,'descriptor length');integer(d.lba,0,0xFFFFFFFF,'LBA');integer(d.device,0,65535,'requester');}
 if(s.completion){if(!['READ','WRITE','FLUSH'].includes(s.completion.op)||s.completion.status!=='SUCCESS'||s.completion.bytes!==(s.completion.op==='FLUSH'?0:SECTOR))fail('Completion format/bytes');}
 if(s.flushed&&s.cache!==null)fail('Durable state cannot retain dirty cache in this profile');
 if(s.outputPrepared&&!s.cpu.resultReady)fail('Output without CPU result');
 if(s.readObserved&&!s.readComplete)fail('Observed read without completion');
 if(s.published&&(!s.descriptor||s.descriptor.owner!=='device'))fail('Published ownership inconsistent');
 if(s.trace.length>500||s.trace.some(t=>typeof t!=='string'||t.length>1000))fail('Trace format/size');
 if(s.cpu.mode==='handler'){if(!s.irq.delivered||!s.irq.pending||s.irq.acknowledged)fail('Handler/IRQ state inconsistent');integer(s.cpu.savedPC,0,0xFFFFFFFF,'savedPC');}
 else if(s.cpu.savedPC!==undefined)fail('savedPC outside handler');
 if(s.irq.delivered&&!s.irq.acknowledged&&s.cpu.mode!=='handler')fail('Delivered IRQ requires handler/savedPC');
 if(s.irq.acknowledged&&s.irq.pending)fail('ACK cannot retain pending');
 return s;
}
function address(s,d,access){
 integer(d.address,0,0xFFFFFFFF,'DMA address');integer(d.length,1,SECTOR,'DMA length');if(d.address+d.length>0x100000000)fail('DMA range выходит за32бит адреса');
 if(!s.iommu.enabled){if(d.address+d.length>SIZE)fail('PA диапазон вне физической RAM; CPU VA не преобразован');return d.address;}
 const m=s.iommu.mappings.find(m=>m.device===d.device&&d.address>=m.iova&&d.address+d.length<=m.iova+m.length);
 if(!m)fail('IOMMU fault: нет отображения IOVA для данного requester и всего диапазона');
 if(!m[access])fail('IOMMU fault: запрещено направление DMA '+access);
 return m.pa+(d.address-m.iova);
}
function event(s,text){s.trace.push(text);if(s.trace.length>500)s.trace.shift();}
function reduce(s,action,arg){
 if(action==='set-iommu'){if(s.published)fail('Нельзя менять IOMMU во время переданного задания');s.iommu.enabled=!!arg;event(s,'IOMMU '+(arg?'on; IOVA4000→PA2000, IOVA4200→PA2200':'off; DMA uses PA'));return;}
 if(action==='mask'){s.irq.enabled=false;event(s,'IRQ masked: pending/completion не очищаются');return;}
 if(action==='unmask'){s.irq.enabled=true;event(s,'IRQ unmasked: доставка ещё отдельный шаг');return;}
 if(action==='prepare-read'){
  if(s.descriptor||s.readComplete)fail('READ уже подготовлен/завершён; повтор не является reset');
  s.descriptor={op:'READ',address:s.iommu.enabled?0x4000:INPUT,length:SECTOR,lba:7,device:1,owner:'host'};event(s,'HOST prepared READ LBA7 len512; descriptor ещё private to host');return;
 }
 if(action==='edit-address'){
  if(!s.descriptor||s.descriptor.owner!=='host')fail('Редактировать descriptor может только текущий HOST owner');
  integer(arg,0,0xFFFFFFFF,'address');s.descriptor.address=arg;event(s,'HOST changed descriptor address to0x'+arg.toString(16));return;
 }
 if(action==='publish'){
  if(!s.descriptor||s.descriptor.owner!=='host')fail('Нет HOST-owned descriptor');
  if(s.descriptor.op==='WRITE'&&!s.outputPrepared)fail('512B output buffer не подготовлен: CPU SW изменил только4B');
  // Model publication represents required visibility + ownership + doorbell, not a universal CPU fence.
  s.descriptor.owner='device';s.published=true;event(s,'Publication: fields visible, OWN→device, DBELL=1');return;
 }
 if(action==='dma-read'){
  const d=s.descriptor;if(!s.published||!d||d.owner!=='device'||d.op!=='READ')fail('Сначала подготовить/опубликовать READ');
  if(d.lba!==7||d.length!==SECTOR)fail('М32-I/O1 поддерживает только LBA7,512B');
  const pa=address(s,d,'write');if(pa!==INPUT)fail('Сквозной READ должен заполнить PA2000..21FF');
  s.ram.splice(pa,SECTOR,...(s.cache||s.media));event(s,'DMA READ: device→RAM PA2000..21FF; первые bytes2A000000, ещё нет completion');s.readComplete=true;return;
 }
 if(action==='complete-read'){
  if(!s.readComplete||!s.published||!s.descriptor||s.descriptor.op!=='READ')fail('DMA READ ещё не завершён или completion уже принят');
  s.descriptor.owner='completed';s.published=false;s.completion={op:'READ',status:'SUCCESS',bytes:SECTOR};s.irq.pending=true;s.irq.delivered=false;s.irq.acknowledged=false;event(s,'READ completion published after DMA; IRQ pending=1');return;
 }
 if(action==='deliver-irq'){
  if(!s.irq.pending)fail('Нет pending IRQ');if(!s.irq.enabled)fail('IRQ masked: completion остаётся, CPU не перенаправлен');if(s.irq.delivered)fail('Этот IRQ уже доставлен');
  s.irq.delivered=true;s.cpu.savedPC=s.cpu.pc;s.cpu.mode='handler';s.cpu.pc=s.irq.vector;event(s,'IRQ entry: savedPC, PC1800, mode handler; не context switch');return;
 }
 if(action==='observe'){
  if(!s.completion)fail('Completion ещё не виден; polling не ускоряет устройство');
  if(s.completion.op==='READ')s.readObserved=true;event(s,'HOST observed '+s.completion.op+' completion via polling/handler; data visibility assumed by publication contract');return;
 }
 if(action==='ack'){
  if(!s.irq.pending||!s.irq.delivered)fail('Для ACK нужен доставленный pending IRQ');
  s.irq.pending=false;s.irq.acknowledged=true;s.cpu.mode='U';s.cpu.pc=s.cpu.savedPC;delete s.cpu.savedPC;event(s,'IRQ source acknowledged; return to savedPC; no scheduler simulated');return;
 }
 if(action==='cpu-result'){
  if(!s.readObserved)fail('Сначала наблюдать READ completion');if(s.cpu.mode!=='U')fail('Вернуться из handler до отдельного CPU упражнения');if(s.cpu.resultReady)fail('CPU result уже создан');
  let n=(s.ram[INPUT]|s.ram[INPUT+1]<<8|s.ram[INPUT+2]<<16|s.ram[INPUT+3]<<24)>>>0;n=(n+1)>>>0;
  for(let i=0;i<4;i++)s.ram[OUTPUT+i]=(n>>>(8*i))&255;
  s.cpu.pc=0x1010;s.cpu.resultReady=true;s.cpu.trap=true;s.descriptor=null;s.completion=null;
  event(s,'Interface to CPU lesson:42→43; SW only PA2200..2203=2B000000; EBREAK stop-viewer PC1010; не512B prepare');return;
 }
 if(action==='prepare-output'){
  if(!s.cpu.resultReady)fail('Сначала получить4B CPU result');if(s.outputPrepared)fail('Output512 уже подготовлен');
  const result=s.ram.slice(OUTPUT,OUTPUT+4);s.ram.splice(OUTPUT,SECTOR,...s.ram.slice(INPUT,INPUT+SECTOR));s.ram.splice(OUTPUT,4,...result);s.outputPrepared=true;
  event(s,'EXPLICIT prepare512B: preserve input bytes4..511, replace first4 with CPU result; not part of5 instructions');return;
 }
 if(action==='prepare-write'){
  if(!s.cpu.resultReady)fail('Нет CPU результата');if(s.descriptor)fail('Descriptor уже существует');
  s.descriptor={op:'WRITE',address:s.iommu.enabled?0x4200:OUTPUT,length:SECTOR,lba:7,device:1,owner:'host'};event(s,'HOST prepared WRITE LBA7,len512; publish still requires explicit output preparation');return;
 }
 if(action==='accept-write'){
  const d=s.descriptor;if(!s.published||!d||d.op!=='WRITE'||d.owner!=='device')fail('Сначала опубликовать WRITE');
  if(!s.outputPrepared||d.lba!==7||d.length!==SECTOR)fail('Нет корректного output512');
  const pa=address(s,d,'read');if(pa!==OUTPUT)fail('WRITE должен читать PA2200..23FF');
  s.cache=s.ram.slice(pa,pa+SECTOR);s.writeAccepted=true;s.flushed=false;event(s,'Controller accepted DMA WRITE into VOLATILE cache; media unchanged');return;
 }
 if(action==='complete-write'){
  if(!s.writeAccepted||!s.published||s.descriptor.op!=='WRITE')fail('WRITE не принят или уже завершён');
  s.writeComplete=true;s.descriptor.owner='completed';s.published=false;s.completion={op:'WRITE',status:'SUCCESS',bytes:SECTOR};s.irq.pending=true;s.irq.delivered=false;s.irq.acknowledged=false;
  event(s,'WRITE completion success under volatile-cache contract; not durable');return;
 }
 if(action==='flush'){
  if(!s.writeComplete||!s.cache)fail('Нет завершённой volatile WRITE для flush');if(s.flushPending)fail('Flush уже ожидается');s.flushPending=true;event(s,'FLUSH requested; durable completion still absent');return;
 }
 if(action==='complete-flush'){
  if(!s.flushPending||!s.cache)fail('Сначала запросить FLUSH при dirty device cache');
  s.media=s.cache.slice();s.cache=null;s.flushPending=false;s.flushed=true;s.completion={op:'FLUSH',status:'SUCCESS',bytes:0};event(s,'FLUSH complete: media LBA7=2B000000; durable within explicit model contract');return;
 }
 if(action==='power-loss'){
  s.cache=null;s.flushPending=false;s.published=false;s.descriptor=null;s.completion=null;s.irq.pending=false;s.irq.delivered=false;s.irq.acknowledged=false;s.cpu.mode='U';s.cpu.pc=s.cpu.savedPC===undefined?s.cpu.pc:s.cpu.savedPC;delete s.cpu.savedPC;s.writeAccepted=false;s.writeComplete=false;s.powerLosses++;
  event(s,'Device power loss: volatile cache/queues lost; stable media retained; RAM kept ONLY for side-by-side teaching comparison, not real host power-loss');return;
 }
 fail('Неизвестное действие');
}
function step(state,action,arg){
 try{validate(state);const s=copy(state);reduce(s,action,arg);validate(s);return {ok:true,state:s,error:null};}
 catch(e){return {ok:false,state,error:String(e.message)};}
}
// Recommendation for the ordinary reading path; does not execute/reset anything.
function nextNormal(s){
 validate(s);if(s.powerLosses>0||s.flushed)return null;
 const d=s.descriptor;
 if(!d&&!s.cpu.resultReady&&!s.readComplete)return ['prepare-read','Подготовить READ'];
 if(d&&d.owner==='host')return ['publish','Опубликовать '+d.op+' descriptor'];
 if(d&&d.op==='READ'&&s.published)return s.readComplete?['complete-read','Опубликовать READ completion']:['dma-read','Выполнить DMA READ512B'];
 if(s.completion&&s.completion.op==='READ'&&!s.cpu.resultReady){
  if(!s.readObserved){if(!s.irq.enabled)return ['unmask','Разрешить IRQ'];if(!s.irq.delivered)return ['deliver-irq','Доставить pending IRQ'];return ['observe','Наблюдать READ completion'];}
  if(s.cpu.mode==='handler')return ['ack','ACK и возврат к savedPC'];return ['cpu-result','CPU-урок:42→43 и SW только4B'];
 }
 if(s.cpu.resultReady&&!s.outputPrepared)return ['prepare-output','Явно подготовить512B output'];
 if(s.outputPrepared&&!d)return ['prepare-write','Подготовить WRITE'];
 if(d&&d.op==='WRITE'&&s.published)return s.writeAccepted?['complete-write','Опубликовать WRITE completion']:['accept-write','DMA WRITE в volatile cache'];
 if(s.writeComplete&&s.cache)return s.flushPending?['complete-flush','Завершить FLUSH до durable']:['flush','Запросить FLUSH'];
 return null;
}
function importState(text){const s=JSON.parse(text);validate(s);return copy(s);}
function exportState(s){validate(s);return JSON.stringify(s,null,2);}
function hex(b){return b.map(n=>n.toString(16).padStart(2,'0').toUpperCase()).join(' ');}
const API={VERSION,SIZE,SECTOR,INPUT,OUTPUT,initial,validate,step,importState,exportState,hex,nextNormal};
if(typeof module==='object'&&module.exports)module.exports=API;
root.M32Devices=API;
})(typeof globalThis==='object'?globalThis:this);
