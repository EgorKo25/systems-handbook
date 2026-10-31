(function(root){'use strict';
function ttlBounds(v){
 const names=['rate','keys','budget','background','freshness','sourceAge','fillDelay'];
 if(!names.every(k=>Number.isFinite(v[k])&&v[k]>=0&&v[k]<=1e12)||!Number.isSafeInteger(v.keys)||v.keys<1)return null;
 const available=v.budget-v.background,perKey=v.rate/v.keys;
 const lower=v.rate===0?0:available<=0?Infinity:Math.max(0,(v.rate/available-1)/perKey);
 const upper=v.freshness-v.sourceAge-v.fillDelay;
 const feasible=available>=0&&upper>=0&&lower<=upper;
 const atUpper=upper<0?null:v.background+(v.rate===0?0:v.rate/(1+perKey*upper));
 return {available,perKey,lower,upper,feasible,atUpper};
}
function slabBudget(v){
 if(!['payload','key','overhead','count','pages'].every(k=>Number.isInteger(v[k])&&v[k]>=0)||v.pages<1||v.pages>8||v.count>128||v.payload>2048||v.key>1024||v.overhead>1024)return null;
 const size=v.payload+v.key+v.overhead,classes=[128,256,512,1024],chunk=classes.find(c=>c>=size);
 if(!chunk)return {size,oversize:true};
 const page=1024,perPage=Math.floor(page/chunk),capacity=perPage*v.pages,stored=Math.min(v.count,capacity);
 return {size,chunk,page,perPage,capacity,stored,missing:v.count-stored,
  valueBytes:stored*v.payload,metadata:stored*(v.key+v.overhead),padding:stored*(chunk-size),
  freeChunks:capacity-stored,reserved:page*v.pages,tail:(page%chunk)*v.pages,oversize:false};
}
const api={ttlBounds,slabBudget};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.CacheResources=api;
if(typeof document==='undefined')return;
const fmt=x=>Number.isFinite(x)?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:3}).format(x):'∞';
function fields(el,items,prefix){el.querySelector('[data-fields]').innerHTML=items.map(([key,label,value])=>'<label for="'+prefix+key+'">'+label+'<input id="'+prefix+key+'" data-field="'+key+'" type="number" min="0" step="any" value="'+value+'"></label>').join('');}
function values(el){return Object.fromEntries([...el.querySelectorAll('[data-field]')].map(x=>[x.dataset.field,Number(x.value)]));}
const ttl=document.querySelector('[data-ttl-lab]');
if(ttl){
 ttl.className='interactive resource-lab';
 ttl.innerHTML='<h3>Проверка совместимости TTL и бюджета источника</h3><p>Одинаковая популярность ключей, независимые обращения Пуассона, fixed TTL, без вытеснения и продления при чтении. Заполнение считается быстрым относительно срока. Максимальная задержка заполнения отдельно расходует бюджет свежести.</p><div class="resource-fields" data-fields></div><output aria-live="polite"></output><div class="resource-chart"></div><p class="small">Уровень нагрузки рассчитан для модели установившегося режима. Холодный старт, всплески и задержки самого источника требуют отдельных ограничителей.</p>';
 fields(ttl,[['rate','Общий поток чтений, запросов/с',20000],['keys','Число равнопопулярных ключей',5000],['budget','Допустимые чтения источника/с',2500],['background','Прочие чтения источника/с',0],['freshness','Допустимый возраст данных, с',1],['sourceAge','Возраст снимка при чтении источника, с',0],['fillDelay','Верхняя оценка задержки заполнения, с',0]],'ttl-');
 const render=()=>{const r=ttlBounds(values(ttl));if(!r){ttl.querySelector('output').textContent='Проверьте числа: нужны неотрицательные значения и целое положительное число ключей.';ttl.querySelector('.resource-chart').innerHTML='';return;}
  ttl.querySelector('output').innerHTML='<strong>'+(r.feasible?'Совместимый диапазон существует.':'Совместимого TTL нет.')+'</strong><br>Нагрузка требует T ≥ '+fmt(r.lower)+' с. Свежесть требует T ≤ '+fmt(r.upper)+' с.<br>При верхней границе срока источник получает '+(r.atUpper===null?'недопустимо старые данные':fmt(r.atUpper)+' запросов/с')+'.'+(!r.feasible?'<br>Нужно изменить условия: снизить поток, повысить бюджет, улучшить обновление или пересмотреть допустимый возраст. Простая настройка TTL не решает конфликт.':'');
  const max=Math.max(1,r.upper>0?r.upper:0,Number.isFinite(r.lower)?r.lower:0)*1.3,map=t=>70+Math.max(0,t)/max*620;
  const a=map(r.upper),b=map(Number.isFinite(r.lower)?r.lower:max),color=r.feasible?'#147d73':'#bf4040';
  ttl.querySelector('.resource-chart').innerHTML='<svg viewBox="0 0 760 200" role="img" aria-label="Границы допустимого TTL"><path d="M70 100H690" stroke="currentColor" stroke-width="2"/><text x="70" y="165" fill="currentColor">0 с</text><path d="M'+a+' 55V135M'+b+' 65V145" stroke="'+color+'" stroke-width="3"/><text x="70" y="30" fill="currentColor">Свежесть: до '+fmt(r.upper)+' с · нагрузка: от '+fmt(r.lower)+' с</text><rect x="'+Math.min(a,b)+'" y="85" width="'+Math.max(2,Math.abs(a-b))+'" height="30" fill="'+color+'" opacity=".25"/><text x="70" y="195" fill="currentColor">'+(r.feasible?'Зелёный участок: допустимые сроки':'Красный участок: несовместимые требования')+'</text></svg>';
 };ttl.addEventListener('input',render);render();
}
const slab=document.querySelector('[data-slab-lab]');
if(slab){
 slab.className='interactive resource-lab';
 slab.innerHTML='<h3>Куда расходуется память slab-класса</h3><p>Учебная модель: страницы по 1024 байта; классы блоков 128, 256, 512 и 1024 байта. Это условные размеры, не параметры установленного Memcached. Накладные расходы задаются явно; у настоящего сервера проверяются его статистика и сборка.</p><div class="resource-fields" data-fields></div><output aria-live="polite"></output><div class="slab-pages"></div><p>В другом классе могут оставаться свободные блоки: например, шесть блоков по 128 Б — всего 768 Б. Запись, которой нужен блок 256 Б, не размещается в одном из этих блоков. Перераспределение страниц — отдельная операция, зависящая от состояния и реализации.</p>';
 fields(slab,[['payload','Байты значения',150],['key','Байты ключа',16],['overhead','Служебные байты на запись',64],['count','Сколько записей хотим разместить',5],['pages','Страниц в выбранном классе (1–8)',1]],'slab-');
 slab.querySelector('.slab-pages').insertAdjacentHTML('beforebegin','<p class="small">В каждом блоке слева направо: зелёный — значение; синий — ключ и служебные поля; охра — пустота внутри занятого блока. Числа под блоком показывают тот же состав в байтах.</p>');
 const render=()=>{const v=values(slab),r=slabBudget(v),out=slab.querySelector('output'),chart=slab.querySelector('.slab-pages');
  if(!r){out.textContent='Нужны целые неотрицательные числа: до 128 записей, 1–8 страниц, значение до 2048 Б, ключ и метаданные до 1024 Б.';chart.innerHTML='';return;}
  if(r.oversize){out.textContent='Размер записи '+fmt(r.size)+' Б: подходящего класса в этой учебной модели нет.';chart.innerHTML='';return;}
  out.innerHTML='Запись: '+fmt(r.size)+' Б → блок '+r.chunk+' Б. Вместимость: '+r.capacity+' записей.<br>Размещено: '+r.stored+'; не помещается: <strong>'+r.missing+'</strong>.<br>Из '+r.reserved+' Б страниц: значения '+r.valueBytes+' Б; ключи и служебные поля '+r.metadata+' Б; пустота внутри занятых блоков '+r.padding+' Б; свободные блоки '+r.freeChunks*r.chunk+' Б; хвост страниц '+r.tail+' Б.';
  chart.innerHTML=Array.from({length:v.pages},(_,p)=>'<div class="slab-page"><strong>Страница '+(p+1)+' · 1024 Б</strong><div class="slab-chunks">'+Array.from({length:r.perPage},(_,j)=>{const used=p*r.perPage+j<r.stored;return '<div class="slab-chunk">'+(used?'<div class="slab-fill"><span style="width:'+v.payload/r.chunk*100+'%;background:#167d73" title="Значение"></span><span style="width:'+(v.key+v.overhead)/r.chunk*100+'%;background:#4263b8" title="Ключ и служебные поля"></span><span style="width:'+(r.chunk-r.size)/r.chunk*100+'%;background:#b57e24" title="Пустота внутри блока"></span></div><small>'+v.payload+' + '+(v.key+v.overhead)+' + '+(r.chunk-r.size)+' Б</small>':'<span>Свободный блок '+r.chunk+' Б</span>')+'</div>';}).join('')+'</div></div>').join('');
 };slab.addEventListener('input',render);render();
}
})(typeof globalThis!=='undefined'?globalThis:this);
