/* Original deterministic teaching models. No native code, host control or network. */
(function(root){
'use strict';
const copy=x=>JSON.parse(JSON.stringify(x));
const TRACE=Object.freeze({file:'counter.bin',before:[42,0,0,0],after:[43,0,0,0],va:'0x00403124',pageBytes:4096,pfn:'0x12A',pa:'0x0012A124',readOffset:0,readLength:4,afterReadOffset:4,rewriteOffset:0});
const MODEL_ABI=Object.freeze({wordBytes:4,read:7,userMode:3,frameBase:0x8000EFF0});
function savedUserWords(frame){
 if(!frame||frame.registers.operation!==MODEL_ABI.read)throw new Error('Only the declared teaching READ frame has this layout');
 const r=frame.registers,complete=r.result!==null;
 const result=!complete?0:typeof r.result==='number'?r.result:r.result.error==='BAD_BUFFER'?-14:NaN;
 const fields=[['PC возврата',Number(frame.pc)],['SP пользователя',Number(frame.sp)],['Режим пользователя',MODEL_ABI.userMode],['Номер операции',r.operation],['Номер открытия',r.object],['Адрес буфера',Number(r.buffer)],['Длина запроса',r.length],['Результат',result]];
 return fields.map(([name,value],i)=>{
  if(!Number.isInteger(value)||value< -2147483648||value>0xFFFFFFFF)throw new Error('Frame word outside the 32-bit teaching layout');
  const word=value>>>0;return {name,address:'0x'+(MODEL_ABI.frameBase+4*i).toString(16).toUpperCase().padStart(8,'0'),value,bytes:[word&255,(word>>>8)&255,(word>>>16)&255,(word>>>24)&255],valid:i!==7||complete};
 });
}
function boundaryTrace(kind='cached'){
 if(!['cached','blocked','fault','bad-buffer'].includes(kind))throw new Error('Unknown boundary scenario');
 let state={cpu:'CPU0',process:'P1',thread:'T1',addressSpace:'AS1',mode:'пользователь',pc:'0x00401000',sp:'0x007FF000',registers:{operation:null,object:null,buffer:null,length:null,result:null},userStack:{},savedUser:null,savedKernel:null,irqFrame:null,threads:{T1:'исполняется',T2:'готов'},ready:['T2'],waiting:[],buffer:[],bufferAllowed:kind!=='bad-buffer',offset:0,switches:0,pte:'present',instructionResult:null};
 const out=[];
 function step(title,explanation,change){if(change)change(state);out.push({title,explanation,...copy(state)});}
 if(kind==='fault'){
  step('Загрузка по адресу, пока отсутствует отображение','T1 собирается выполнить LOAD32 из разрешённой области. Данные уже доступны в известном физическом кадре; дисковый ввод не требуется.',s=>{s.pc='0x00401008';s.pte='not-present';s.registers={address:TRACE.va,result:null};});
  step('Сохранена именно повторяемая команда','В модели исключение сохраняет PC самой LOAD32, а не следующей команды. Тот же поток входит в обработчик.',s=>{s.savedUser={pc:s.pc,sp:s.sp,registers:copy(s.registers),mode:s.mode,owner:'T1/P1/AS1',storage:'кадр исключения в защищённом стеке T1'};s.mode='ядро';s.pc='0x80005000';s.sp='0x8000EFF0';});
  step('ОС проверила область и подготовила запись','ОС допускает чтение и связывает страницу с PFN0x12A. Это выбранная ветвь исправления fault, не обещание любого fault.',s=>{s.pte='present: PFN0x12A, чтение разрешено';s.buffer=TRACE.before.slice();});
  step('Возвращён тот же PC','Возврат разрешает повторить LOAD32 после исправления; передачи другому потоку не было.',s=>{s.mode='пользователь';s.pc=s.savedUser.pc;s.sp=s.savedUser.sp;s.registers=copy(s.savedUser.registers);});
  step('Команда завершена после повторения','Четыре байта 2a000000 дают 42. Файловое чтение не выполнялось и его позиция не изменилась.',s=>{s.registers.result=42;s.instructionResult=42;s.pc='0x0040100C';});
  return out;
 }
 step('До вызова функции','T1/P1/AS1. PC выбирает CALL helper, пользовательский SP0x007FF000. В память файла ещё не обращались.');
 step('Обычный вызов функции','Учебный ABI кладёт четырёхбайтовый адрес возврата в пользовательский стек. Режим и поток прежние.',s=>{s.userStack['0x007FEFFC']='0x00401004';s.pc='0x00402000';s.sp='0x007FEFFC';});
 step('Подготовлен системный запрос','В учебном ABI READ имеет номер 7. Это не Linux ABI. Выбрано открытие 3, четыре байта, тот же общий пользовательский адрес.',s=>{s.pc='0x0040200C';s.registers={operation:MODEL_ABI.read,object:3,buffer:TRACE.va,length:4,result:null};});
 step('Вход в ядро, T1 остаётся исполнителем','Кадр на защищённом стеке T1 хранит пользовательские PC/SP/аргументы. Отдельно выбран KSP модели; аппаратный автоматический набор этим рисунком не утверждается.',s=>{s.savedUser={pc:'0x00402010',sp:s.sp,registers:copy(s.registers),mode:s.mode,owner:'T1/P1/AS1',storage:'кадр входа в защищённом стеке T1'};s.mode='ядро';s.pc='0x80001000';s.sp='0x8000EFF0';});
 if(kind==='bad-buffer'){
  step('Проверка отвергла буфер','В этой ветви весь диапазон заведомо недопустим и передача ещё не началась. Открытие и позиция остаются прежними.',s=>{s.pc='0x80001100';s.registers.result={error:'BAD_BUFFER',transferred:0};s.savedUser.registers.result=copy(s.registers.result);});
 }else{
  if(kind==='blocked'){
   step('T1 ждёт работу J17','Создано ожидание по незавершённой операции. Сохранено продолжение ядра T1, не пользовательский адрес после вызова.',s=>{s.savedKernel={pc:'0x80001140',sp:'0x8000EFC0',addressSpace:'AS1',registers:copy(s.registers),owner:'T1/P1',storage:'состояние ожидания T1 и её защищённый стек'};s.threads.T1='ждёт J17';s.waiting=['T1:J17'];s.pc='0x80003000';s.sp='0x8000EFA0';});
   step('CPU передан T2','Первое действительное переключение: сохранённая T1 не исполняется, T2/P2/AS2 получает своё продолжение.',s=>{s.process='P2';s.thread='T2';s.addressSpace='AS2';s.mode='пользователь';s.pc='0x00501000';s.sp='0x009FF000';s.threads.T2='исполняется';s.registers={R1:99,R2:0};s.ready=[];s.switches++;});
   step('IRQ прерывает T2, но завершает J17 для T1','В модели T2 успела выполнить одну команду. Кадр прерывания T2 хранится отдельно от пользовательского кадра T1. После обработки T1 лишь готова; это ещё не её исполнение.',s=>{s.irqFrame={thread:'T2',owner:'T2/P2/AS2',mode:'пользователь',pc:'0x00501004',sp:s.sp,addressSpace:'AS2',registers:copy(s.registers),storage:'кадр IRQ на защищённом стеке T2'};s.mode='ядро/IRQ';s.registers={irq:5,completed:'J17'};s.pc='0x80004000';s.sp='0x8001EFF0';s.threads.T1='готов';s.waiting=[];s.ready=['T1'];});
   step('Обработчик вернулся в T2','В этой разрешённой последовательности сразу не переключаемся. T1 уже готова и ждёт решения планировщика.',s=>{s.mode='пользователь';s.pc=s.irqFrame.pc;s.sp=s.irqFrame.sp;s.registers=copy(s.irqFrame.registers);});
   step('T1 продолжает незавершённый путь ядра','Второе переключение восстанавливает сохранённые KPC/KSP T1 и AS1. Возврат пользователю пока не разрешён.',s=>{s.process='P1';s.thread='T1';s.addressSpace='AS1';s.mode='ядро';s.pc=s.savedKernel.pc;s.sp=s.savedKernel.sp;s.registers=copy(s.savedKernel.registers);s.threads.T1='исполняется';s.threads.T2='готов';s.ready=['T2'];s.switches++;});
  }
  step('Переданы четыре байта','Доступные данные копируются в разрешённый буфер; текущая позиция выбранного открытия 0→4.',s=>{s.pc='0x80001180';s.sp='0x8000EFC0';s.buffer=TRACE.before.slice();s.offset=4;s.registers.result=4;s.savedUser.registers.result=4;});
 }
 step('Возврат из ядра','Восстановлены PC0x00402010/SP0x007FEFFC пользователя. Результат операции передан по ABI модели; это та же T1.',s=>{s.mode='пользователь';s.pc=s.savedUser.pc;s.sp=s.savedUser.sp;s.registers=copy(s.savedUser.registers);});
 step('Функция вернулась вызывающему коду','RETURN извлекает подготовленный CALL адрес 0x00401004 и продвигает SP. Байтам стека не приписывается автоматическое стирание.',s=>{s.pc=s.userStack[s.sp];s.sp='0x007FF000';});
 return out;
}
function schedule(jobs,options={}){
 const policy=options.policy||'rr',quantum=options.quantum===undefined?2:options.quantum;
 if(!['rr','fcfs'].includes(policy)||!Number.isInteger(quantum)||quantum<1||quantum>100)throw new Error('Invalid scheduling policy/quantum');
 if(!Array.isArray(jobs)||jobs.length<1||jobs.length>10)throw new Error('Need1–10 jobs');
 const ids=new Set();let total=0;
 const tasks=jobs.map((j,index)=>{
  if(!j||typeof j.id!=='string'||!/^[A-Za-z][A-Za-z0-9]{0,7}$/.test(j.id)||ids.has(j.id)||!Number.isInteger(j.arrival)||j.arrival<0||j.arrival>1000||!Array.isArray(j.bursts)||!j.bursts.length||j.bursts.length%2!==1||j.bursts.some(n=>!Number.isInteger(n)||n<1||n>200))throw new Error('Invalid job');
  ids.add(j.id);total+=j.bursts.reduce((a,b)=>a+b,0);return {id:j.id,arrival:j.arrival,bursts:j.bursts.slice(),index,phase:0,left:j.bursts[0],status:'ещё не поступила',first:null,finish:null,wake:null,cpu:0,readyWait:0,blocked:0};
 });
 if(total>4000)throw new Error('Scenario too large');
 let t=0,current=null,expired=null,used=0,previous=null,switches=0;const ready=[],timeline=[];
 while(tasks.some(j=>j.finish===null)){
  if(t>6000)throw new Error('Bounded model failed to finish');
  const events=[];
  for(const j of tasks.filter(j=>j.arrival===t)){j.status='готов';ready.push(j);events.push(j.id+' поступила');}
  for(const j of tasks.filter(j=>j.wake===t)){j.wake=null;j.status='готов';ready.push(j);events.push(j.id+' пробуждена');}
  if(expired){expired.status='готов';ready.push(expired);events.push(expired.id+' в конец после кванта');expired=null;}
  if(!current&&ready.length){current=ready.shift();current.status='исполняется';used=0;if(current.first===null)current.first=t;if(previous!==null&&previous!==current.id)switches++;previous=current.id;events.push('выбрана '+current.id);}
  const row={time:t,end:t+1,running:current?current.id:null,ready:ready.map(j=>j.id),waiting:tasks.filter(j=>j.status==='ждёт').map(j=>({id:j.id,wake:j.wake})),remaining:Object.fromEntries(tasks.map(j=>[j.id,j.left])),events:events.slice()};
  for(const j of ready)j.readyWait++;
  for(const j of tasks)if(j.status==='ждёт')j.blocked++;
  if(current){
   current.left--;current.cpu++;used++;
   if(current.left===0){
    if(current.phase===current.bursts.length-1){current.finish=t+1;current.status='завершена';}
    else{const delay=current.bursts[current.phase+1];current.phase+=2;current.left=current.bursts[current.phase];current.status='ждёт';current.wake=t+1+delay;}
    current=null;
   }else if(policy==='rr'&&used===quantum){current.status='готов';expired=current;current=null;}
  }
  row.pendingExpired=expired?expired.id:null;row.after=Object.fromEntries(tasks.map(j=>[j.id,{status:j.status,cpu:j.cpu,readyWait:j.readyWait,blocked:j.blocked,finish:j.finish,wake:j.wake}]));
  timeline.push(row);t++;
 }
 const result=tasks.map(j=>({id:j.id,arrival:j.arrival,first:j.first,finish:j.finish,response:j.first-j.arrival,turnaround:j.finish-j.arrival,cpu:j.cpu,readyWait:j.readyWait,blocked:j.blocked}));
 for(const j of result)if(j.turnaround!==j.cpu+j.readyWait+j.blocked)throw new Error('Accounting invariant');
 return {policy,quantum,timeline,jobs:result,wall:t,cpu:result.reduce((s,j)=>s+j.cpu,0),switches,assumptions:'1CPU, дискретные 1 мс; затраты управления 0; поступления → пробуждения → возврат после кванта; длительности CPU-порций и ожиданий заданы модели; число передач CPU относится к полезным работам, простой отдельно не считается.'};
}
function smp(affinity='both'){
 if(!['both','cpu0'].includes(affinity))throw new Error('Invalid affinity');
 const allowed=affinity==='both'?[0,1]:[0],jobs=[{id:'A',left:6},{id:'B',left:6}],timeline=[];let t=0;
 while(jobs.some(j=>j.left)){
  const picked=new Set(),cpus=[null,null];
  for(let cpu=0;cpu<2;cpu++){const job=jobs.find(j=>j.left>0&&!picked.has(j.id)&&allowed.includes(cpu));if(job){picked.add(job.id);cpus[cpu]=job.id;}}
  for(const job of jobs)if(picked.has(job.id))job.left--;
  timeline.push({time:t,end:t+1,cpus,remaining:Object.fromEntries(jobs.map(j=>[j.id,j.left]))});t++;
 }
 return {affinity,allowed,timeline,wall:t,cpu:12,utilization:12/(2*t),assumptions:'2 равных CPU, A=B=6 мс, затраты 0, разрешённый набор одинаков у A/B.'};
}
function lifecycleTrace(failAt='none'){
 if(!['none','load'].includes(failAt))throw new Error('Unknown lifecycle branch');
 const base={parent:'P0',child:null,image:null,stage:'начало',privateObjects:[],publicObjects:[],result:null,execution:false};const out=[];
 function step(title,explanation,patch){Object.assign(base,patch);out.push({title,explanation,...copy(base)});}
 step('P0 просит создать P1','До создания P1 существует только запрос, принадлежащий инициатору.',{});
 step('Операция создания удерживает частные объекты','В этой модели память и запись ребёнка ещё не опубликованы. Их владелец — операция создания.',{stage:'подготовка',privateObjects:['запись P1','адресная среда AS1','стек T1']});
 if(failAt==='load'){
  step('Образ не принят','Выбранная модель возвращает ошибку до публикации ребёнка; операция создания освобождает всё своё частное состояние.',{stage:'отказ создания',privateObjects:[],result:'LOAD_FAILED'});
  return out;
 }
 step('P1 опубликован с T1','Передано владение обычному жизненному циклу; P0 удерживает предусмотренную ссылку ожидания.',{child:'P1',stage:'готов',privateObjects:[],publicObjects:['P1','AS1','T1','ссылка P0→P1'],image:'launcher'});
 step('В P1 заменён образ','Идентичность P1 прежняя; новый код counter-reader получает явно переданные входы.',{image:'counter-reader',stage:'исполняется',execution:true});
 step('P1 прекратил исполнение','В этой Unix-подобной модели остаётся запись результата до ожидания. Пользовательский код больше не исполняется.',{stage:'завершён, результат ждёт',execution:false,publicObjects:['результат P1','ссылка P0→P1'],result:7});
 step('P0 получил результат','Получение завершения освобождает предусмотренную запись; закрыта собственная ссылка инициатора.',{stage:'результат получен',publicObjects:[]});
 return out;
}
function serviceTrace(branch='normal'){
 if(!['normal','prepare-fails','forced-stop'].includes(branch))throw new Error('Unknown service branch');
 const state={process:'нет',ready:false,accepting:false,inflight:0,durable:false,result:null},rows=[];
 function step(title,explanation,patch){Object.assign(state,patch);rows.push({title,explanation,...copy(state)});}
 step('Создан экземпляр','Создание подтверждено; прикладная готовность ещё не принята.',{process:'существует'});
 if(branch==='prepare-fails'){step('Формат данных не принят','В этой ветви файл неверен. Готовность не публикуется; повтор не обнуляет файл.',{process:'завершён',result:'BAD_FORMAT'});return rows;}
 step('Служба готова','Данные и среда приняты, вход новых запросов доступен.',{process:'работает',ready:true,accepting:true});
 step('Приняты два запроса','Обязательства уже существуют.',{inflight:2});
 step('Приём прекращён','Готовность снята раньше завершения старой работы.',{ready:false,accepting:false});
 if(branch==='forced-stop'){step('Предел ожидания исчерпан','Модель принудительно завершает процесс. Неутверждённые результаты остаются неизвестными; сохранность не обещана.',{process:'принудительно завершён',result:'FORCED/UNKNOWN'});return rows;}
 step('Активная работа закончена','Новые запросы не поступают, старые получили предусмотренный исход.',{inflight:0});
 step('Состояние синхронизировано','Только при явных допущениях исправного поддерживаемого пути sync/flush подтверждена сохранность.',{durable:true});
 step('Процесс завершён и результат получен','Отправленная просьба и принятое завершение — разные ступени.',{process:'завершён',result:0});
 return rows;
}
const WORKLOADS={cpu:[{id:'A',arrival:0,bursts:[8]},{id:'B',arrival:1,bursts:[2]},{id:'C',arrival:2,bursts:[1]}],io:[{id:'A',arrival:0,bursts:[2,3,1]},{id:'B',arrival:0,bursts:[5]},{id:'C',arrival:4,bursts:[1]}]};
const api={TRACE,MODEL_ABI,savedUserWords,boundaryTrace,schedule,smp,lifecycleTrace,serviceTrace,WORKLOADS};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.OSExecutionModels=api;
if(typeof document==='undefined')return;
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function table(rows){const t=el('table');for(const [key,value]of rows){const tr=el('tr');tr.append(el('th',key),el('td',String(value)));t.append(tr);}const wrap=el('div',undefined,'os-exe-table');wrap.append(t);return wrap;}
function options(values,onchange){const s=el('select');for(const [value,label]of values){const o=el('option',label);o.value=value;s.append(o);}s.addEventListener('change',onchange);return s;}
function mount(container){
 if(container.dataset.osExecutionMounted)return;container.dataset.osExecutionMounted='1';
 const kind=container.dataset.osExecution;let index=0,rows=[],summary='',selector=null,extra=null,quantum=null;
 const caption=el('p',undefined,'os-exe-caption'),controls=el('div',undefined,'os-exe-controls'),view=el('div',undefined,'os-exe-view'),foot=el('div',undefined,'os-exe-controls');
 const previous=el('button','←'),next=el('button','Дальше →'),reset=el('button','Сначала'),progress=el('span');for(const b of [previous,next,reset])b.type='button';previous.setAttribute('aria-label','Предыдущий шаг модели');progress.setAttribute('aria-live','polite');
 const label=el('label');label.append(el('span','Сценарий '));
 function recalc(){
  index=0;
  if(kind==='boundary'){rows=boundaryTrace(selector.value);summary='Учебные 32-разрядные регистры/адреса. Общие защищённые отображения ядра, отдельные стеки. Не реальная ISA и не полная модель Linux.';}
  if(kind==='lifecycle'){rows=lifecycleTrace(selector.value);summary='Модель публикации ребёнка и владения частичными объектами. Unix-подобное ожидание; не Windows API.';}
  if(kind==='service'){rows=serviceTrace(selector.value);summary='Готовность процесса, услуги и сохранность различаются. Никаких служб компьютера модель не запускает.';}
  if(kind==='scheduler'){quantum.disabled=selector.value==='fcfs';const r=schedule(WORKLOADS[extra.value],{policy:selector.value,quantum:Number(quantum.value)});rows=r.timeline;summary=r.assumptions+' Исполнение CPU='+r.cpu+'мс; прошло='+r.wall+'мс. '+r.jobs.map(j=>j.id+': первый запуск '+j.response+', очередь '+j.readyWait+', внешнее ожидание '+j.blocked+', полное '+j.turnaround+'мс').join('; ');}
  if(kind==='smp'){const r=smp(selector.value);rows=r.timeline;summary=r.assumptions+' прошло='+r.wall+'мс, Исполнение CPU='+r.cpu+'мс, агрегированная занятость '+Math.round(r.utilization*100)+'%.';}
  draw();
 }
 function draw(){
  const row=rows[index];view.replaceChildren();caption.textContent=summary;progress.textContent=(index+1)+' / '+rows.length;previous.disabled=index===0;next.disabled=index===rows.length-1;
  if(kind==='boundary'){
   view.append(el('h3',row.title),el('p',row.explanation),table([['Исполнитель',row.cpu+' / '+row.process+' / '+row.thread+' / '+row.addressSpace],['Режим',row.mode],['PC / SP',row.pc+' / '+row.sp],['Диапазон буфера',row.bufferAllowed?'разрешён':'доступ запрещён в этой ветви'],['Открытие', 'позиция '+row.offset],['Буфер',row.buffer.length?row.buffer.map(b=>b.toString(16).padStart(2,'0')).join(' '):'не заполнен'],['Очередь готовых',row.ready.join(', ')||'пуста'],['Ожидание',row.waiting.join(', ')||'нет'],['Переключений',row.switches]]));
   const detail=el('details'),regLabels={operation:'Операция',object:'Открытие',buffer:'Адрес буфера',length:'Число байтов',result:'Результат',address:'Адрес загрузки',R1:'Регистр R1',R2:'Регистр R2',irq:'Номер IRQ',completed:'Завершённая работа'};
   detail.append(el('summary','Регистры и сохранённые продолжения'));
   detail.append(table(Object.entries(row.registers).map(([k,v])=>[regLabels[k]||k,v===null?'ещё не задан':typeof v==='object'?'BAD_BUFFER, передано 0':v])));
   if(row.savedUser){detail.append(el('h4','Пользовательское продолжение T1'),el('p',row.savedUser.owner+'; '+row.savedUser.storage));if(row.savedUser.registers.operation===MODEL_ABI.read){detail.append(table(savedUserWords(row.savedUser).map(f=>[f.address+' · '+f.name,f.bytes.map(b=>b.toString(16).padStart(2,'0')).join(' ')+'; '+(f.valid?f.value:'слот результата ещё не действителен')])));}else detail.append(table([['PC / SP',row.savedUser.pc+' / '+row.savedUser.sp]]));}
   if(row.savedKernel)detail.append(el('h4','Продолжение ядра T1'),table([['Владелец',row.savedKernel.owner],['PC / SP',row.savedKernel.pc+' / '+row.savedKernel.sp],['Адресная среда',row.savedKernel.addressSpace],['Хранилище',row.savedKernel.storage]]));
   if(row.irqFrame)detail.append(el('h4','Прерванное продолжение T2'),table([['Владелец / режим',row.irqFrame.owner+' / '+row.irqFrame.mode],['Поток / среда',row.irqFrame.thread+' / '+row.irqFrame.addressSpace],['PC / SP',row.irqFrame.pc+' / '+row.irqFrame.sp],['R1 / R2',row.irqFrame.registers.R1+' / '+row.irqFrame.registers.R2],['Хранилище',row.irqFrame.storage]]));
   view.append(detail);
  }else if(kind==='scheduler'){
   view.append(el('h3','Интервал ['+row.time+','+row.end+') мс'),el('p',row.events.join('; ')||'Исполнение прежнего выбора'),table([['CPU',row.running||'простой'],['Готовые по порядку',row.ready.join(' → ')||'нет'],['Ожидают',row.waiting.map(j=>j.id+' до '+j.wake).join(', ')||'нет'],['Остаток текущих CPU-порций',Object.entries(row.remaining).map(([k,v])=>k+'='+v).join('; ')]]));
  }else if(kind==='smp'){
   view.append(el('h3','Интервал ['+row.time+','+row.end+') мс'),table([['CPU0',row.cpus[0]||'свободен'],['CPU1',row.cpus[1]||'свободен'],['Остаток после шага',Object.entries(row.remaining).map(([k,v])=>k+'='+v).join('; ')]]));
  }else{
   view.append(el('h3',row.title),el('p',row.explanation));const labels={parent:'Родитель',child:'Ребёнок',image:'Образ',stage:'Этап',privateObjects:'Объекты операции создания',publicObjects:'Опубликованные объекты',result:'Результат',execution:'Исполняется',process:'Процесс',ready:'Готовность услуги',accepting:'Приём новой работы',inflight:'Активные запросы',durable:'Подтверждена сохранность'};const values=Object.entries(row).filter(([k])=>!['title','explanation'].includes(k)).map(([k,v])=>[labels[k]||k,Array.isArray(v)?v.join(', ')||'нет':v===null?'ещё нет':typeof v==='boolean'?(v?'да':'нет'):v]);view.append(table(values));
  }
 }
 if(kind==='boundary')selector=options([['cached','Чтение уже доступных байтов'],['blocked','Чтение с ожиданием и IRQ'],['fault','Исправимое страничное исключение'],['bad-buffer','Отказ неподходящего буфера']],recalc);
 else if(kind==='lifecycle')selector=options([['none','Создание → замена → ожидание'],['load','Отказ до публикации']],recalc);
 else if(kind==='service')selector=options([['normal','Штатный жизненный цикл'],['prepare-fails','Ошибка начальных данных'],['forced-stop','Принудительная остановка']],recalc);
 else if(kind==='scheduler'){selector=options([['rr','Круговой обход'],['fcfs','До конца CPU-порции']],recalc);extra=options([['cpu','A: 8, B: 2, C: 1 мс CPU'],['io','Есть ожидание 3 мс']],recalc);const x=el('label');x.append(el('span','Нагрузка '),extra);controls.append(x);quantum=options([['2','2 мс'],['1','1 мс'],['4','4 мс'],['8','8 мс']],recalc);const q=el('label');q.append(el('span','Квант RR '),quantum);controls.append(q);}
 else if(kind==='smp')selector=options([['both','A/B разрешены CPU0 и CPU1'],['cpu0','A/B разрешён только CPU0']],recalc);
 else return;
 label.append(selector);controls.prepend(label);previous.addEventListener('click',()=>{if(index>0){index--;draw();}});next.addEventListener('click',()=>{if(index<rows.length-1){index++;draw();}});reset.addEventListener('click',()=>{index=0;draw();});foot.append(previous,next,reset,progress);container.replaceChildren(controls,caption,view,foot);recalc();
}
function boot(){for(const n of document.querySelectorAll('[data-os-execution]'))mount(n);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})(typeof globalThis!=='undefined'?globalThis:this);
