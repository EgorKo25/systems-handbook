(()=>{'use strict';const el=document.querySelector('.replication-lab');if(!el)return;
const scenarios=JSON.parse(document.getElementById('replication-scenarios').textContent),controls=el.querySelector('[data-replication-controls]');let scenario='loss',step=0;
controls.innerHTML='<label>Сценарий <select data-scenario>'+Object.entries(scenarios).map(([k,s])=>'<option value="'+k+'">'+s.title+'</option>').join('')+'</select></label><div class="step-toolbar"><button data-back>←</button><strong data-counter></strong><button data-forward>Дальше →</button></div>';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){const rows=scenarios[scenario].steps,r=rows[step],x=[95,365,635,905],svg=el.querySelector('svg');let s='<defs><marker id="rep-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="context-stroke"/></marker></defs>';
['Клиент','Основной Redis','Реплика Redis','Sentinel'].forEach((name,i)=>{s+='<text x="'+x[i]+'" y="32" text-anchor="middle" fill="currentColor" font-size="20">'+name+'</text><path d="M'+x[i]+' 50 V650" stroke="currentColor" opacity=".2" stroke-dasharray="5 7"/>';});
rows.forEach((row,i)=>{const y=92+i*78,active=i===step,seen=i<=step,color=active?'var(--accent)':'currentColor';s+='<g opacity="'+(seen?1:.18)+'">';if(active)s+='<rect x="8" y="'+(y-37)+'" width="984" height="70" rx="9" fill="var(--soft)"/>';
 const a=x[row.sender],b=x[row.receiver];s+='<path d="'+(a===b?'M'+a+' '+(y-7)+' h42 v24 h-42':'M'+a+' '+y+' H'+b)+'" fill="none" stroke="'+color+'" stroke-width="'+(active?3:2)+'" marker-end="url(#rep-arrow)"/>';
 const tx=a===b?(a>800?a-180:a+55):Math.min(a,b)+12;
 const label=row.sender===3&&row.receiver===2?'REPLICAOF NO ONE':row.label;
 s+='<text x="'+tx+'" y="'+(y-12)+'" fill="'+color+'" font-size="17">'+esc(label)+'</text><text x="12" y="'+(y+25)+'" fill="currentColor" font-size="14">'+(i+1)+'</text></g>';});svg.innerHTML=s;
el.querySelector('[data-counter]').textContent='Шаг '+(step+1)+' из '+rows.length+' · '+r.title;el.querySelector('[data-back]').disabled=step===0;el.querySelector('[data-forward]').disabled=step===rows.length-1;
el.querySelector('[data-replication-state]').innerHTML='<p>'+esc(r.detail)+'</p><div class="table-wrap"><table><thead><tr><th>Наблюдение</th><th>Основной</th><th>Реплика</th></tr></thead><tbody><tr><th>Данные</th><td>'+esc(r.primary)+'</td><td>'+esc(r.replica)+'</td></tr><tr><th>Позиция потока</th><td>'+esc(r.po)+'</td><td>'+esc(r.ro)+'</td></tr></tbody></table></div><p><strong>Что знает клиент:</strong> '+esc(r.client)+'</p>';
}
el.querySelector('[data-scenario]').onchange=e=>{scenario=e.target.value;step=0;render();};el.querySelector('[data-back]').onclick=()=>{step--;render();};el.querySelector('[data-forward]').onclick=()=>{step++;render();};render();})();
