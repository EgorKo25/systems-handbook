(function(){'use strict';
const S=window.M32Scenes,$=id=>document.getElementById(id),key='handbook-ca-logic-scenes-v1',defaults={scene:'loop',count:3,value:42,counter:1,btb:'correct'};let result=null,blocked=false;
const hex=n=>n===null?'нет':(n>>>0).toString(16).toUpperCase().padStart(4,'0');
function validate(x){if(!x||!['loop','call','call-broken','rename','rename-fault','predictor'].includes(x.scene)||!Number.isInteger(x.count)||x.count<1||x.count>10||!Number.isInteger(x.value)||x.value<0||x.value>4294967295||!Number.isInteger(x.counter)||x.counter<0||x.counter>3||!['correct','stale','missing'].includes(x.btb))throw new Error('неподходящие входы');return x;}
let selected={...defaults};try{const raw=localStorage.getItem(key);if(raw!==null)selected=validate(JSON.parse(raw));$('storage').textContent=raw===null?'Исходные входы; сохранение после явного вычисления.':'Продолжены собственные сохранённые входы.';}catch(error){blocked=true;$('storage').textContent='Сохранённые входы недоступны или повреждены. Их не перезаписали; нужен явный сброс.';}
function setInputs(x){for(const name of Object.keys(defaults))$(name).value=String(x[name]);}
function getInputs(){return validate({scene:$('scene').value,count:Number($('count').value),value:Number($('value').value),counter:Number($('counter').value),btb:$('btb').value});}
function fields(){const scene=$('scene').value;for(const [id,visible] of [['count-label',scene==='loop'],['value-label',scene==='rename'],['counter-label',scene==='predictor'],['btb-label',scene==='predictor']])$(id).hidden=!visible;}
function row(parent,values,tag='td'){const tr=document.createElement('tr');values.forEach(v=>{const cell=document.createElement(tag);cell.textContent=String(v);tr.appendChild(cell);});parent.appendChild(tr);}
function render(x){document.body.dataset.scene=x.scene;$('rows').replaceChildren();$('heads').replaceChildren();let headings;
 if(x.scene==='predictor'){
  const target={correct:0x1104,stale:0x1110,missing:null}[x.btb];result=S.predictorTrace(x.counter,target);headings=['Проверка','Счётчик до → после','Прогноз направления/PC','Факт/верный PC','Причина'];
  result.forEach((r,i)=>row($('rows'),[i+1,r.stateBefore+' → '+r.stateAfter,(r.predictsTaken?'T':'N')+' / '+hex(r.predictedPC),(r.taken?'T':'N')+' / '+hex(r.actualPC),!r.predictionAvailable?'Цель недоступна':r.addressCorrect?'Адрес верен':r.directionCorrect?'Верное направление, неверная цель':'Неверное направление']));
  $('explanation').textContent='Одна и та же команда по 1108 получает фактические исходы T,T,N. Счётчик обучается по факту; BTB в этой ограниченной трассе сохраняет выбранную вами цель.';
  $('summary').textContent='Доступных ошибочных адресов: '+result.filter(r=>r.mispredict).length+'; недоступных прогнозов: '+result.filter(r=>!r.predictionAvailable).length+'. Это не измерение аппаратной точности.';
 }else if(x.scene.startsWith('rename')){
  result=S.renameTrace({faultA:x.scene==='rename-fault',input:x.value});headings=['Событие','RAT x6/x8','Принятая x6/x8','ROB: голова слева','Готовые новые числа','Свободные; store/RAM'];
  result.forEach(r=>row($('rows'),[r.event,r.rat.x6+'/'+r.rat.x8,r.committed.x6+'/'+r.committed.x8,r.rob.map(i=>i.label+(i.fault?'!':i.ready?'+':'−')).join(' ')||'пусто',['P10','P11','P12'].filter(p=>r.physical[p]?.ready).map(p=>p+'='+r.physical[p].value).join(', ')||'нет',r.free.join(', ')+'; '+(r.store?'store committed='+r.store.committed:'store нет')+'; RAM2200='+r.memory2200]));
  $('explanation').textContent='Четыре отдельные команды A/B/C/D назначаются по порядку. B готова раньше A, C ждёт P10, D захватывает P12. Отправка разрешённой записи показана отдельным событием после commit D.';
  const last=result.at(-1);$('summary').textContent='RAT '+JSON.stringify(last.rat)+'; принятая таблица '+JSON.stringify(last.committed)+'; RAM2200='+last.memory2200+'; otherCoreObserved=null (не моделируется).';
 }else{
  result=S.controlTrace(x.scene==='loop'?'loop':'call',{loopCount:x.count,restoreLink:x.scene!=='call-broken'});headings=['PC / слово','Действие','PC после','ra / SP после','x7 / память'];
  result.trace.forEach(r=>row($('rows'),[hex(r.before.pc)+' / '+hex(r.word),r.decoded.op+(r.taken===undefined?'':r.taken?' T':' N')+(r.fault?' — '+r.fault:''),hex(r.after.pc),hex(r.after.ra)+' / '+hex(r.after.sp),r.after.x7+(r.memory?'; '+r.memory.kind+' '+hex(r.memory.address)+': '+r.memory.bytes.map(b=>b.toString(16).padStart(2,'0')).join(' '):'')]));
  $('explanation').textContent=x.scene==='loop'?'Уменьшение x7 меняет условие BNE. Смещение −4 отсчитывается от 1108, поэтому цель 1104.':'JAL по 1100 сохраняет 1104. Вложенный JAL меняет ra на 1210. Копия в 6FFC позволяет восстановить 1104; без LW возврат попадает в 1210.';
  $('summary').textContent='Сцена '+result.scene+'; '+result.status+(result.cause?' / '+result.cause:'')+'; PC='+hex(result.pc)+'; событий='+result.trace.length+'. scene-goal — граница примера, не HALT.';
 }
 row($('heads'),headings,'th');$('raw').textContent=JSON.stringify(result,null,2);$('compute').disabled=blocked;$('download').disabled=blocked;fields();
}
setInputs(selected);fields();if(!blocked)render(selected);else{$('compute').disabled=true;$('download').disabled=true;}
$('scene').onchange=fields;
$('compute').onclick=()=>{if(blocked)return;try{const x=getInputs();render(x);selected=x;try{localStorage.setItem(key,JSON.stringify(x));$('storage').textContent='Входы сохранены; конечная трасса воспроизводится из них.';}catch(error){$('storage').textContent='Сохранение недоступно; скачайте JSON до закрытия.';}}catch(error){$('storage').textContent='Вычисление отвергнуто: '+error.message+'. Предыдущая трасса сохранена.';}};
$('reset').onclick=()=>{if(!confirm('Явно заменить сохранённые входы сцен исходными?'))return;blocked=false;selected={...defaults};setInputs(selected);render(selected);try{localStorage.setItem(key,JSON.stringify(selected));$('storage').textContent='Выполнен явный сброс входов сцен.';}catch(error){$('storage').textContent='Хранилище недоступно; входы только в памяти вкладки.';}};
$('download').onclick=()=>{if(blocked||!result)return;const blob=new Blob([JSON.stringify({profile:'M32-bounded-scenes-v1',inputs:selected,result},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='m32-own-scene.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('print').onclick=()=>window.print();window.M32Appearance.mount($('model-theme'),$('warmth'));
}());
