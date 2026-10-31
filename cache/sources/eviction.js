(function(root){'use strict';
function simulate(trace,capacity,policy){
 if(!Number.isInteger(capacity)||capacity<1||capacity>12||!Array.isArray(trace)||trace.length<1||trace.length>80||trace.some(k=>typeof k!=='string'||!k||k.length>32))throw Error('Недопустимые параметры трассы');
 if(!['FIFO','LRU','LFU','CLOCK','OPT'].includes(policy))throw Error('Неизвестная политика');
 let cache=[],meta=new Map(),hand=0,hits=0,rows=[];
 trace.forEach((key,i)=>{
  const before=[...cache],hit=meta.has(key);let victim=null,reason='';
  if(hit){hits++;const m=meta.get(key);m.count++;m.last=i;m.bit=1;
   if(policy==='LRU'){cache.splice(cache.indexOf(key),1);cache.push(key);}
   reason=policy==='FIFO'?'Попадание: FIFO не меняет порядок вставки.':policy==='CLOCK'?'Попадание: бит обращения установлен в 1.':'Попадание: история использования обновлена.';
  }else{
   if(cache.length===capacity){let n=0;
    if(policy==='LFU')n=cache.reduce((best,k,j)=>{const a=meta.get(k),b=meta.get(cache[best]);return a.count<b.count||(a.count===b.count&&a.last<b.last)?j:best;},0);
    if(policy==='OPT'){const next=k=>{const p=trace.indexOf(k,i+1);return p<0?Infinity:p;};n=cache.reduce((best,k,j)=>next(k)>next(cache[best])?j:best,0);}
    if(policy==='CLOCK'){while(meta.get(cache[hand]).bit){meta.get(cache[hand]).bit=0;hand=(hand+1)%capacity;}n=hand;}
    victim=cache[n];meta.delete(victim);
    if(policy==='CLOCK'){cache[n]=key;hand=(hand+1)%capacity;}else{cache.splice(n,1);cache.push(key);}
    reason={FIFO:'Удалена самая ранняя вставка.',LRU:'Удалено самое давнее обращение.',LFU:'Минимальная частота; при равенстве — самое давнее обращение.',CLOCK:'Стрелка пропустила биты 1, сняла их и заменила запись с битом 0.',OPT:'Выбрано самое далёкое следующее обращение; отсутствие повторения считается бесконечностью.'}[policy];
   }else{cache.push(key);reason='Свободное место: вытеснение не требуется.';}
   meta.set(key,{count:1,last:i,bit:1});
  }
  rows.push({step:i+1,key,hit,victim,before,after:[...cache],hits,misses:i+1-hits,reason,metadata:cache.map(k=>({key:k,...meta.get(k)})),hand:policy==='CLOCK'?hand:null});
 });return rows;
}
const api={simulate};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.CacheEviction=api;
if(typeof document==='undefined')return;
const el=document.querySelector('[data-eviction-trainer]');if(!el)return;
el.className='interactive eviction-trainer';
el.innerHTML='<h3>Сравнение алгоритмов на одной трассе</h3><p>Одинаковые размеры, пустое начало, без TTL. LFU хранит точные счётчики только резидентных записей, без старения. OPT использует будущее и служит офлайн-ориентиром.</p><label>Ключи через пробел<input data-trace value="A B C A D A B E A B C D"></label><label>Ёмкость в объектах<input data-capacity type="number" min="1" max="12" value="3"></label><label>Политика<select data-policy><option>FIFO</option><option selected>LRU</option><option>LFU</option><option>CLOCK</option><option>OPT</option></select></label><button data-recalculate>Разобрать трассу</button><p data-error role="alert"></p><div class="step-toolbar"><button data-prev>←</button><strong data-position></strong><button data-next>Дальше →</button></div><div data-cache-slots></div><p data-explanation aria-live="polite"></p><div class="table-wrap"><table><thead><tr><th>Шаг</th><th>Ключ</th><th>Результат</th><th>Вытеснен</th><th>Содержимое после</th></tr></thead><tbody data-history></tbody></table></div>';
const q=s=>el.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let rows=[],step=0;
function render(){const r=rows[step];q('[data-position]').textContent='Шаг '+r.step+' из '+rows.length;q('[data-prev]').disabled=step===0;q('[data-next]').disabled=step===rows.length-1;
 q('[data-cache-slots]').innerHTML=r.metadata.map((m,j)=>'<span class="cache-slot"><b>'+esc(m.key)+'</b><small>частота '+m.count+(r.hand!==null?' · бит '+m.bit+(r.hand===j?' · ← стрелка':''):'')+'</small></span>').join('');
 q('[data-explanation]').textContent=(r.hit?'Попадание. ':'Промах. ')+r.reason+' До: '+r.before.join(' · ')+'. После: '+r.after.join(' · ')+'. Попадания: '+r.hits+'; промахи: '+r.misses+'.';
 q('[data-history]').innerHTML=rows.slice(0,step+1).map(x=>'<tr><td>'+x.step+'</td><td>'+esc(x.key)+'</td><td>'+(x.hit?'hit':'miss')+'</td><td>'+esc(x.victim??'—')+'</td><td>'+esc(x.after.join(' · '))+'</td></tr>').join('');}
function rebuild(){try{rows=simulate(q('[data-trace]').value.trim().split(/\s+/),Number(q('[data-capacity]').value),q('[data-policy]').value);step=0;q('[data-error]').textContent='';render();}catch(e){q('[data-error]').textContent='Нужны 1–80 ключей длиной до 32 символов и целая ёмкость от 1 до 12.';}}
q('[data-recalculate]').onclick=rebuild;q('[data-prev]').onclick=()=>{step--;render();};q('[data-next]').onclick=()=>{step++;render();};rebuild();
})(typeof globalThis!=='undefined'?globalThis:this);
