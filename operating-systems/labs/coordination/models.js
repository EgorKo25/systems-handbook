/* Original finite teaching models. No OS API, network, timer, or storage access. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.OSCoordination=factory();})(typeof globalThis==='object'?globalThis:this,function(){
'use strict';
const TRACE=Object.freeze({file:'counter.bin',virtualAddress:'0x00403124',physicalAddress:'0x0012A124',initial:42,next:43,bytes:Object.freeze([42,0,0,0])});
function uint32(n){if(!Number.isInteger(n)||n<0||n>4294967295)throw new RangeError('Нужно целое uint32');return n;}
function encode(n){uint32(n);return [n&255,(n>>>8)&255,(n>>>16)&255,(n>>>24)&255];}
function decode(a){if(!Array.isArray(a)||a.length!==4||a.some(x=>!Number.isInteger(x)||x<0||x>255))throw new RangeError('Нужны ровно четыре байта');return a[0]+a[1]*256+a[2]*65536+a[3]*16777216;}
function increment(n){uint32(n);if(n===4294967295)throw new RangeError('Переполнение: изменение отвергнуто');return n+1;}
function interleavings(n=3,m=3){if(!Number.isInteger(n)||!Number.isInteger(m)||n<0||m<0||n+m>12)throw new RangeError('Размер конечной модели');const out=[];function walk(a,b,s){if(!a&&!b){out.push(s);return;}if(a)walk(a-1,b,s.concat('A'));if(b)walk(a,b-1,s.concat('B'));}walk(n,m,[]);return out;}
function raceTrace(schedule){if(!Array.isArray(schedule)||schedule.length!==6||schedule.filter(x=>x==='A').length!==3||schedule.filter(x=>x==='B').length!==3)throw new RangeError('Три шага каждого участника');let shared=42;const pc={A:0,B:0},local={A:null,B:null};const rows=[{actor:'Начало',action:'Два запроса ещё не выполнили +1',shared,local:{...local}}];for(const actor of schedule){const step=pc[actor]++;let action;if(step===0){local[actor]=shared;action='читает общий счётчик';}else if(step===1){local[actor]=increment(local[actor]);action='вычисляет личное значение +1';}else{shared=local[actor];action='записывает личное значение';}rows.push({actor,action,shared,local:{...local}});}return rows;}
function atomicTrace(){return [{actor:'Начало',action:'Ожидаются две неделимые прибавки',shared:42},{actor:'A',action:'fetch_add: прежнее42 → общее43',shared:43},{actor:'B',action:'fetch_add: прежнее43 → общее44',shared:44}];}
function casAttempt(shared,expected,desired,{weak=false,spurious=false}={}){[shared,expected,desired].forEach(uint32);if(spurious&&!weak)throw new Error('Сильный CAS не имеет ложного отказа');const success=shared===expected&&!spurious;return {shared:success?desired:shared,expected:success?expected:shared,desired,success};}
function casTrace(spurious=false){let shared=42;const rows=[{actor:'Начало',action:'A/B ожидают42 и подготовили43',shared,expected:42,desired:43,success:'ещё нет попытки'}];if(spurious){const a=casAttempt(shared,42,43,{weak:true,spurious:true});rows.push({actor:'A',action:'Weak отказ без чужого изменения',...a});}let a=casAttempt(shared,42,43);shared=a.shared;rows.push({actor:'A',action:'Сравнение совпало, A закончил',...a});let b=casAttempt(shared,42,43);shared=b.shared;rows.push({actor:'B',action:'Старое expected не совпало; записи нет',...b});rows.push({actor:'B',action:'Пересчитать desired из нового expected',shared,expected:b.expected,desired:b.expected+1,success:'ещё не CAS'});b=casAttempt(shared,b.expected,b.expected+1);rows.push({actor:'B',action:'Повтор успешно даёт44',...b});return rows;}
function abaOutcome(tagged){const expected={address:'0x7000',generation:7},current={address:'0x7000',generation:10};return {expected,current,success:expected.address===current.address&&(!tagged||expected.generation===current.generation)};}
function publicationAllowed(contract,flag,value){if(!['relaxed','release-acquire'].includes(contract)||![0,1].includes(flag)||![42,43].includes(value))throw new RangeError('Вне конечного договора');return !(contract==='release-acquire'&&flag===1&&value===42);}
function wakeTrace(protectedWait){if(protectedWait)return [
{actor:'Начало',action:'Очередь пуста; предикат ложен',queue:[],waiting:false,consumer:'проверяет'},
{actor:'Потребитель',action:'Под mutex проверяет пустоту',queue:[],waiting:false,consumer:'в критической области'},
{actor:'Механизм ожидания',action:'Согласованно регистрирует сон и отпускает mutex',queue:[],waiting:true,consumer:'ждёт'},
{actor:'Производитель',action:'Под тем же mutex публикует43 и уведомляет',queue:[43],waiting:false,consumer:'готов, ещё не исполняется'},
{actor:'Потребитель',action:'Получает mutex, заново проверяет предикат и забирает43',queue:[],waiting:false,consumer:'получил43'}];return [
{actor:'Начало',action:'Очередь пуста',queue:[],waiting:false,consumer:'исполняется'},
{actor:'Потребитель',action:'Проверил пустоту без согласования постановки на сон',queue:[],waiting:false,consumer:'решил ждать'},
{actor:'Производитель',action:'Положил43; уведомлять пока некого',queue:[43],waiting:false,consumer:'ещё не зарегистрирован'},
{actor:'Потребитель',action:'Теперь зарегистрировал сон; нового события нет',queue:[43],waiting:true,consumer:'спит при непустой очереди'}];}
function findCycle(graph){const active=new Set(),done=new Set(),path=[];function visit(v){if(active.has(v))return path.slice(path.indexOf(v)).concat(v);if(done.has(v))return null;active.add(v);path.push(v);for(const w of graph[v]||[]){const r=visit(w);if(r)return r;}path.pop();active.delete(v);done.add(v);return null;}for(const v of Object.keys(graph)){const r=visit(v);if(r)return r;}return [];}
class RecordQueue{constructor(capacity=1){if(!Number.isInteger(capacity)||capacity<1||capacity>1000)throw new RangeError('Ёмкость в записях');this.capacity=capacity;this.queue=[];this.closed=false;this.accepted=0;this.completed=0;}send(bytes){decode(bytes);if(this.closed)return 'closed';if(this.queue.length===this.capacity)return 'would-block';this.queue.push(bytes.slice());this.accepted++;return 'accepted';}receive(){if(this.queue.length){this.completed++;return {status:'value',bytes:this.queue.shift()};}return {status:this.closed?'eof':'would-block'};}close(){this.closed=true;}}
/* Own coalescing notice, not an implementation of any OS signal queue. */
class SignalNotice{constructor(masked=true){if(typeof masked!=='boolean')throw new TypeError('Маска — логическое значение');this.masked=masked;this.pending=false;this.generated=0;this.delivered=0;}notify(){this.generated++;this.pending=true;}setMask(masked){if(typeof masked!=='boolean')throw new TypeError('Маска — логическое значение');this.masked=masked;}deliver(){if(this.masked||!this.pending)return false;this.pending=false;this.delivered++;return true;}}
/* One fixed-length record; temporary absence preserves the already filled prefix. */
class RecordAssembler{constructor(){this.bytes=[];this.phase='collecting';}accept(result){if(this.phase!=='collecting')throw new Error('Запись уже завершена');if(!result||!['value','would-block','eof','error'].includes(result.status))throw new Error('Неизвестный исход');if(result.status==='value'){const a=result.bytes;if(!Array.isArray(a)||!a.length||a.length>4-this.bytes.length||a.some(x=>!Number.isInteger(x)||x<0||x>255))throw new RangeError('Непустой префикс в оставшееся место');this.bytes.push(...a);if(this.bytes.length===4)this.phase='complete';}else if(result.status==='eof')this.phase=this.bytes.length?'truncated':'eof';else if(result.status==='error')this.phase='error';return {phase:this.phase,filled:this.bytes.length,value:this.phase==='complete'?decode(this.bytes):null};}}
/* Finite resource-count calculation: callers must supply all completion needs. */
function safeSequence(available,rows){const valid=v=>Array.isArray(v)&&v.length===available.length&&v.every(x=>Number.isSafeInteger(x)&&x>=0);if(!valid(available)||!Array.isArray(rows)||rows.some(r=>!r||typeof r.id!=='string'||!valid(r.held)||!valid(r.need))||new Set(rows.map(r=>r.id)).size!==rows.length)throw new RangeError('Количество ресурсов и уникальные участники');const work=available.slice(),pending=rows.slice(),sequence=[];for(;;){const i=pending.findIndex(r=>r.need.every((n,j)=>n<=work[j]));if(i<0)break;const r=pending.splice(i,1)[0];r.held.forEach((n,j)=>work[j]+=n);sequence.push(r.id);}return {sequence,remaining:pending.map(r=>r.id),available:work,safe:pending.length===0};}
class ByteStream{constructor(bytes=[]){if(!Array.isArray(bytes)||bytes.some(x=>!Number.isInteger(x)||x<0||x>255))throw new RangeError('Байты');this.bytes=bytes.slice();this.closed=false;}ready(){return this.bytes.length>0||this.closed;}read(n){if(!Number.isInteger(n)||n<1)throw new RangeError('Размер чтения');if(this.bytes.length)return {status:'value',bytes:this.bytes.splice(0,n)};return {status:this.closed?'eof':'would-block'};}close(){this.closed=true;}}
class CompletionBuffer{constructor(){this.phase='idle';this.request=null;this.result=null;}submit(id){if(this.phase!=='idle')throw new Error('Буфер уже принадлежит операции');if(typeof id!=='string'||!id)throw new Error('Нужен идентификатор');this.phase='pending';this.request=id;this.result=null;}cancel(){if(this.phase!=='pending')throw new Error('Нет ожидающей операции');this.phase='cancel-requested';}reuse(){if(this.phase==='pending'||this.phase==='cancel-requested')throw new Error('Нет конечного завершения: буфер занят');this.phase='idle';this.request=null;this.result=null;}complete(id,bytes,cancelled=false){if(!['pending','cancel-requested'].includes(this.phase)||id!==this.request)throw new Error('Чужое или повторное завершение');if(!Array.isArray(bytes)||bytes.length>4||bytes.some(x=>!Number.isInteger(x)||x<0||x>255))throw new RangeError('Префикс до четырёх байтов');this.phase=cancelled?'cancelled':'completed';this.result={id,count:bytes.length,bytes:bytes.slice(),cancelled};return this.result;}}
/* Own finite PI scheduler model: larger numbers mean higher urgency here.
   No real scheduler, OS priority, futex, timeout clock or thread is invoked. */
class PriorityWorld{
 constructor(tasks,mutexes,inherit=true){
  const id=x=>typeof x==='string'&&/^[A-Za-z][A-Za-z0-9]*$/.test(x);
  if(typeof inherit!=='boolean'||!Array.isArray(tasks)||!tasks.length||tasks.length>16||!Array.isArray(mutexes)||mutexes.length>16||tasks.some(t=>!t||!id(t.id)||!Number.isInteger(t.base)||t.base<1||t.base>99)||new Set(tasks.map(t=>t.id)).size!==tasks.length||mutexes.some(x=>!id(x))||new Set(mutexes).size!==mutexes.length)throw new RangeError('Уникальные задачи/блокировки и приоритеты 1..99');
  this.inherit=inherit;this.tasks=new Map(tasks.map((t,i)=>[t.id,{id:t.id,base:t.base,effective:t.base,state:'ready',waits:null,held:new Set(),order:i}]));this.mutexes=new Map(mutexes.map(id=>[id,{id,owner:null,waiters:[]}]));this.serial=0;
 }
 task(id){const t=this.tasks.get(id);if(!t)throw new Error('Неизвестная задача');return t;}
 mutex(id){const m=this.mutexes.get(id);if(!m)throw new Error('Неизвестная блокировка');return m;}
 recompute(){
  for(const t of this.tasks.values())t.effective=t.base;
  if(!this.inherit)return;
  for(let pass=0;pass<this.tasks.size;pass++){
   let changed=false;
   for(const m of this.mutexes.values())if(m.owner!==null){const owner=this.task(m.owner);for(const w of m.waiters){const priority=this.task(w.id).effective;if(priority>owner.effective){owner.effective=priority;changed=true;}}}
   if(!changed)return;
  }
 }
 acquire(id,lock){const t=this.task(id),m=this.mutex(lock);if(t.state!=='ready')throw new Error('Задача не готова к новому действию');if(m.owner===id)throw new Error('Повторное владение не поддержано');if(m.owner===null){m.owner=id;t.held.add(lock);}else{m.waiters.push({id,order:this.serial++});t.waits=lock;t.state='blocked';}this.recompute();return t.state;}
 release(id,lock){const t=this.task(id),m=this.mutex(lock);if(t.state!=='ready'||m.owner!==id)throw new Error('Освобождает только готовый владелец');t.held.delete(lock);m.owner=null;let granted=null;if(m.waiters.length){m.waiters.sort((a,b)=>this.task(b.id).effective-this.task(a.id).effective||a.order-b.order);granted=m.waiters.shift().id;const next=this.task(granted);next.waits=null;next.state='ready';next.held.add(lock);m.owner=granted;}this.recompute();return granted;}
 cancelWait(id){const t=this.task(id);if(t.state!=='blocked'||t.waits===null)throw new Error('Задача уже не ожидает: проверить итог получения');const m=this.mutex(t.waits),i=m.waiters.findIndex(w=>w.id===id);if(i<0)throw new Error('Нарушена очередь');m.waiters.splice(i,1);t.waits=null;t.state='ready';this.recompute();return 'cancelled';}
 defer(id){const t=this.task(id);if(t.state!=='ready'||t.held.size)throw new Error('Отложить можно только ещё не начатую задачу');t.state='inactive';}
 activate(id){const t=this.task(id);if(t.state!=='inactive')throw new Error('Задача уже поступила');t.state='ready';}
 finish(id){const t=this.task(id);if(t.state!=='ready'||t.waits!==null||t.held.size)throw new Error('Завершение требует освободить ресурсы');t.state='finished';this.recompute();}
 pick(){const ready=[...this.tasks.values()].filter(t=>t.state==='ready').sort((a,b)=>b.effective-a.effective||a.order-b.order);return ready[0]?.id??null;}
 snapshot(){return {tasks:Object.fromEntries([...this.tasks].map(([id,t])=>[id,{base:t.base,effective:t.effective,state:t.state,waits:t.waits,held:[...t.held]}])),mutexes:Object.fromEntries([...this.mutexes].map(([id,m])=>[id,{owner:m.owner,waiters:m.waiters.map(w=>w.id)}])),next:this.pick()};}
}
function priorityTrace(kind='direct',inherit=true){
 if(!['direct','nested','remaining','cycle'].includes(kind)||(!inherit&&kind!=='direct'))throw new Error('Неизвестный опыт PI');
 const w=new PriorityWorld([{id:'L',base:10},{id:'M',base:50},{id:'H',base:90},{id:'V',base:5},{id:'R',base:70}],['A','B'],inherit),rows=[];
 // Unused tasks finish before the recorded experiment, so they cannot win CPU.
 for(const id of (kind==='direct'?['V','R']:kind==='remaining'?['V']:['R']))w.finish(id);
 for(const id of ['M','H',...(kind==='remaining'?['R']:[])])w.defer(id);
 const take=(title,explanation)=>rows.push({title,explanation,...w.snapshot()});
 if(kind==='direct'){
  w.acquire('L','A');w.activate('M');w.activate('H');take('L уже владеет A','Исходное владение получено до прихода H; M готов и не просит A.');
  w.acquire('H','A');take('H ждёт владельца',inherit?'L получил 90; из готовых выбирается L.':'L остался 10; из готовых выбирается M.');
  if(!inherit){w.finish('M');take('M закончил свои 10 мс','Время условно задано текстом, а не измерено браузером; теперь из готовых выбирается L.');}
  w.release('L','A');take('L передал A ожидающему H','H стал готовым владельцем; L вернулся к 10. Готовность ещё не означает выполненное действие H.');
 }else if(kind==='nested'){
  w.acquire('V','B');w.acquire('L','A');take('Два исходных владельца','L владеет A; V владеет B. M пока не мешал этой подготовке.');
  w.acquire('L','B');take('L ждёт B','L сохраняет A и ждёт V; V получает эффективный приоритет 10.');
  w.activate('M');w.activate('H');w.acquire('H','A');take('H замкнул цепочку ожидания','L получает 90 от H; V получает 90 от ожидающего L. Из готовых выбирается V.');
  w.release('V','B');take('V передал B','V вернулся к 5; L теперь готов с A и B, оставаясь 90 из-за H.');
  w.release('L','B');take('L освободил B','Освобождение B не снимает повышение от H на A. L по-прежнему 90.');
  w.release('L','A');take('L передал A','H готов с A; L вернулся к 10, V остался 5.');
 }else if(kind==='remaining'){
  w.acquire('L','A');w.acquire('L','B');w.activate('M');w.activate('R');w.acquire('R','B');w.activate('H');w.acquire('H','A');take('У L два источника повышения','H(90) ждёт A; R(70) ждёт B. Максимум для L равен 90.');
  w.release('L','A');take('L передал A H','Ожидающий R всё ещё связан с B: L теперь 70, а не базовые 10. H готов с A.');
  w.cancelWait('R');take('Истёк срок ожидания R','Уход из очереди B снял оставшееся повышение: L стал 10. R готов обработать отказ и не владеет B.');
 }else{
  w.acquire('L','A');w.acquire('V','B');w.acquire('L','B');w.acquire('V','A');take('Образовался цикл','L ждёт B у V, V ждёт A у L. Оба заблокированы.');
  w.activate('M');w.activate('H');w.acquire('H','A');take('H повысил владельцев до 90','Приоритет распространяется по циклу, но L и V не стали готовыми. M может работать; ресурсы по-прежнему не освобождаются.');
 }
 return rows;
}
const rights=Object.freeze({counter:['read','write'],reader:['read'],other:[]});
function access(subject,action){if(!Object.hasOwn(rights,subject)||!['read','write','change-policy'].includes(action))return false;return rights[subject].includes(action);}
function accessWrite(world,subject,value){uint32(value);if(!access(subject,'write'))return {allowed:false,value:world.value};world.value=value;return {allowed:true,value:world.value};}
function budget(arrival,cpuMs,cpuBudget){if(![arrival,cpuMs,cpuBudget].every(Number.isFinite)||arrival<0||cpuMs<=0||cpuBudget<0)throw new RangeError('Конечные неотрицательные значения, CPU-цена >0');const capacity=cpuBudget/(cpuMs/1000),demand=arrival*cpuMs/1000;if(!Number.isFinite(capacity)||!Number.isFinite(demand))throw new RangeError('Масштаб выходит за конечную модель');return {arrival,cpuMs,cpuBudget,demand,capacity,queueGrowth:Math.max(0,arrival-capacity),steadyPossible:arrival<=capacity};}
return Object.freeze({TRACE,encode,decode,increment,interleavings,raceTrace,atomicTrace,casAttempt,casTrace,abaOutcome,publicationAllowed,wakeTrace,findCycle,RecordQueue,SignalNotice,RecordAssembler,safeSequence,ByteStream,CompletionBuffer,access,accessWrite,budget,PriorityWorld,priorityTrace});
});
