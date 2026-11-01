"""Approximate, local reading-time labels and conservative pace observations.

The estimator measures eligible forward text traversal, never gaze or completion.
It does not change the existing scroll progress bar, chapter notes or preferences.
"""
import re

STYLE_ID = 'library-reading-time-style-v1'
SCRIPT_ID = 'library-reading-time-v1'
CSS = r'''
.chapter-reading-time{display:block;margin-top:3px;font:500 11px/1.4 var(--sans);color:var(--muted);letter-spacing:0;white-space:normal}
.reading-time-status{display:flex;align-items:baseline;gap:6px 12px;flex-wrap:wrap;margin:14px 0 0!important;font:550 13px/1.5 var(--sans)!important;color:var(--muted);text-align:start!important;overflow-wrap:anywhere}
.reading-time-status small{font:400 11px/1.5 var(--sans);opacity:.85}
#top-title.topbar-title{display:block;min-width:0}
.topbar-title .reading-time-current{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:500 11px/1.4 var(--sans);color:var(--muted);margin-top:2px}
@media(max-width:750px){.reading-time-status{font-size:12px!important;gap:3px 9px}.chapter-reading-time{font-size:11px}}
@media print{.chapter-reading-time,.reading-time-status{display:none!important}}
'''

SCRIPT = r'''
(function(root){
  'use strict';
  const KEY='library-reading-pace-v1', VERSION=1, DEFAULT_WPM=180;
  const LIMIT=15, MIN_RATE=80, MAX_RATE=420, MIN_HISTORY=3, IDLE_MS=45000;
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
  const median=values=>{const v=[...values].sort((a,b)=>a-b),m=Math.floor(v.length/2);return v.length%2?v[m]:(v[m-1]+v[m])/2;};
  function validSample(s){
    if(!s||typeof s.key!=='string'||!s.key.length||s.key.length>200)return false;
    if(![s.words,s.activeMs,s.chapterWords,s.steps,s.at].every(finite))return false;
    const rate=s.words*60000/s.activeMs;
    return s.chapterWords>=600&&s.chapterWords<=500000&&s.words>=Math.max(350,s.chapterWords*.25)&&s.words<=s.chapterWords&&s.activeMs>=90000&&s.activeMs<=28800000&&s.steps>=5&&Number.isInteger(s.steps)&&s.at>=0&&rate>=MIN_RATE&&rate<=MAX_RATE;
  }
  function clean(samples){
    const byKey=new Map();
    for(const s of Array.isArray(samples)?samples:[])if(validSample(s)){
      const next={key:s.key,words:s.words,activeMs:s.activeMs,chapterWords:s.chapterWords,steps:s.steps,at:s.at};
      if(!byKey.has(s.key)||byKey.get(s.key).at<=s.at)byKey.set(s.key,next);
    }
    return [...byKey.values()].sort((a,b)=>a.at-b.at).slice(-LIMIT);
  }
  function decode(value){
    if(typeof value!=='string'||value.length>65536)return null;
    try{const d=JSON.parse(value);return d&&d.version===VERSION&&Array.isArray(d.samples)&&d.samples.length<=256?clean(d.samples):null;}catch(_){return null;}
  }
  function encode(samples){return JSON.stringify({version:VERSION,samples:clean(samples)});}
  function rate(samples){
    const values=clean(samples).map(s=>s.words*60000/s.activeMs);
    if(values.length<MIN_HISTORY)return DEFAULT_WPM;
    const middle=median(values),mad=median(values.map(v=>Math.abs(v-middle)));
    const accepted=values.filter(v=>Math.abs(v-middle)<=Math.max(30,3*mad));
    return Math.round(clamp(median(accepted.length>=MIN_HISTORY?accepted:values),MIN_RATE,MAX_RATE));
  }
  function minutes(words,wpm=DEFAULT_WPM){return Math.max(1,Math.ceil(Math.max(0,finite(words)?words:0)/clamp(wpm,MIN_RATE,MAX_RATE)));}
  function remaining(words,position,wpm=DEFAULT_WPM){
    const rest=Math.max(0,words*(1-clamp(position,0,1)))/clamp(wpm,MIN_RATE,MAX_RATE);
    return rest<1?'До конца текста меньше минуты':'Осталось примерно '+Math.ceil(rest)+' мин';
  }
  // Union of genuinely traversed intervals: rereading cannot manufacture words.
  function addInterval(intervals,start,end){
    let before=intervals.reduce((n,[a,b])=>n+b-a,0),next=[],placed=false;
    for(const [a,b]of intervals){
      if(b<start)next.push([a,b]);
      else if(end<a){if(!placed){next.push([start,end]);placed=true;}next.push([a,b]);}
      else{start=Math.min(start,a);end=Math.max(end,b);}
    }
    if(!placed)next.push([start,end]);
    return {intervals:next,added:Math.max(0,next.reduce((n,[a,b])=>n+b-a,0)-before)};
  }
  class Session{
    constructor(key,words){this.key=key;this.words=words;this.intervals=[];this.activeMs=0;this.steps=0;this.intent=-Infinity;this.last=null;this.anchor=null;this.pending=0;this.until=0;}
    activity(now){if(finite(now))this.intent=now;}
    interrupt(now=0,pause=0){this.last=null;this.anchor=null;this.pending=0;this.until=Math.max(this.until,now+pause);}
    observe(o){
      const {now,position,viewportWords=150}=o;
      if(!finite(now)||!finite(position)||!finite(viewportWords))return;
      const p=clamp(position,0,1),eligible=o.visible&&o.focused&&!o.blocked&&now-this.intent<=IDLE_MS&&now>=this.until;
      if(!eligible){this.interrupt(now);return;}
      if(this.last===null){this.last=now;this.anchor=p;return;}
      const dt=now-this.last;this.last=now;
      if(dt<0||dt>2500){this.anchor=p;this.pending=0;return;}
      this.pending+=dt;
      const travelled=(p-this.anchor)*this.words;
      const maxStep=Math.max(100,viewportWords*1.5);
      if(travelled<-.005*this.words||travelled>maxStep){this.anchor=p;this.pending=0;this.until=now+1500;return;}
      if(travelled<=0||this.pending<5000)return;
      // Only a plausible sustained traverse is eligible. A page left for hours
      // expires before its next scroll and contributes no outstanding interval.
      if(travelled*60000/this.pending>MAX_RATE*1.5){this.anchor=p;this.pending=0;this.until=now+1500;return;}
      const merged=addInterval(this.intervals,this.anchor*this.words,p*this.words);
      if(merged.added>=5){this.intervals=merged.intervals;this.activeMs+=this.pending*(merged.added/travelled);this.steps++;}
      this.anchor=p;this.pending=0;
    }
    sample(at){
      const words=this.intervals.reduce((n,[a,b])=>n+b-a,0);
      const s={key:this.key,words,activeMs:this.activeMs,chapterWords:this.words,steps:this.steps,at};
      return validSample(s)?s:null;
    }
  }
  const model=Object.freeze({KEY,VERSION,DEFAULT_WPM,LIMIT,MIN_HISTORY,IDLE_MS,clean,decode,encode,rate,minutes,remaining,Session});
  if(typeof module!=='undefined'&&module.exports)module.exports=model;
  if(!root.document)return;
  const doc=root.document;
  if(root.LibraryReadingTime)return;
  const dataNode=doc.getElementById('book-data');if(!dataNode)return;
  let rows;try{rows=JSON.parse(dataNode.textContent);}catch(_){return;}
  if(!Array.isArray(rows))return;
  const chapters=rows.filter(r=>r&&typeof r.id==='string'&&finite(r.words)&&r.words>0).map(r=>({...r,element:doc.getElementById(r.id)})).filter(r=>r.element?.classList.contains('chapter'));
  let history=[];try{history=decode(root.localStorage.getItem(KEY))||[];}catch(_){}
  let current=null,session=null,units=[],unitWords=0,activeWords=0,lastPosition=0,lastRemaining='',lastIntent=-Infinity,holdUntil=0,scheduled=false,positionFrozen=false,readingOutsideInteractive=false;
  const now=()=>root.performance.now();
  const volume=doc.body.dataset.volume||'book';
  function explanation(){
    const n=clean(history).length,wpm=rate(history);
    return 'Приблизительное время текста, без выполнения упражнений. Оглавление оценивает весь текст главы; остаток — текущий развёрнутый текст, без закрытых подсказок. '+(n>=MIN_HISTORY?'Ориентир '+wpm+' слов/мин: медиана пригодных наблюдений прошлых глав.':'Начальный ориентир 180 слов/мин; адаптация после трёх подходящих глав.')+' Остаток считается по месту в тексте, а не по доказанному прочтению. Подробный разбор кода может занять больше времени. Это не распознавание чтения глазами. Скрытая вкладка, потеря фокуса, долгий покой, формы и скачки не обучают оценку.';
  }
  function paintAll(){
    const wpm=rate(history),tip=explanation();
    for(const row of chapters){
      const link=doc.getElementById('nav-'+row.id);
      if(link){
        let badge=link.querySelector('[data-reading-total]');
        if(!badge){badge=doc.createElement('small');badge.className='chapter-reading-time';badge.dataset.readingTotal='';const spans=link.querySelectorAll('span');(spans[spans.length-1]||link).appendChild(badge);}
        badge.textContent='≈ '+minutes(row.words,wpm)+' мин';badge.title=tip;
      }
      let status=row.element.querySelector('[data-reading-status]');
      if(!status){
        status=doc.createElement('p');status.className='reading-time-status';status.dataset.readingStatus='';
        const text=doc.createElement('span');text.dataset.readingRemaining='';status.appendChild(text);
        const note=doc.createElement('small');note.textContent='без выполнения упражнений';status.appendChild(note);
        (row.element.querySelector('header.hero,header')||row.element).appendChild(status);
      }
      status.title=tip;status.querySelector('[data-reading-remaining]').textContent='≈ '+minutes(row.words,wpm)+' мин текста';
    }
    paintCurrent();
  }
  function paintCurrent(){
    const title=doc.getElementById('top-title');if(!title)return;
    let label=title.querySelector('[data-reading-current]');
    if(!current){label?.remove();return;}
    if(!label){label=doc.createElement('span');label.className='reading-time-current';label.dataset.readingCurrent='';title.appendChild(label);}
    const text=lastRemaining||remaining(activeWords,lastPosition,rate(history));
    if(label.textContent!==text)label.textContent=text;label.title=explanation();
  }
  function saveSample(){
    const candidate=session?.sample(Date.now());if(!candidate)return;
    try{const stored=decode(root.localStorage.getItem(KEY));if(stored)history=clean([...history,...stored]);}catch(_){}
    history=clean([...history,candidate]);
    try{root.localStorage.setItem(KEY,encode(history));}catch(_){}
    paintAll();
  }
  function blocked(){
    if(doc.body.classList.contains('phone-volume-open')||root.location.hash==='#volume')return true;
    if(doc.querySelector('dialog[open],.drawer:not([hidden]),.sidebar.open,.phone-view:not([hidden])'))return true;
    const active=doc.activeElement;
    if(active?.closest('input,textarea,select,[contenteditable="true"],[data-learning-terminal],.learning-terminal'))return true;
    return !readingOutsideInteractive&&!!active?.closest('.deep-sketch,.command-ref');
  }
  const skip='header,.hero,.deep-sketch,.local-toc,.chapter-footer,script,style,button,input,textarea,select,.ds-live,[data-learning-terminal],.learning-terminal,.reading-time-status';
  function buildUnits(){
    units=[];unitWords=0;activeWords=0;
    if(!current)return;
    const walker=doc.createTreeWalker(current.element,root.NodeFilter.SHOW_TEXT);
    const groups=new Map();let node;
    while((node=walker.nextNode())){
      const parent=node.parentElement;if(!parent||parent.closest(skip))continue;
      const words=(node.textContent.match(/\S+/g)||[]).length;if(!words)continue;
      const block=parent.closest('p,h2,h3,h4,pre,li,dt,dd,td,th')||parent;
      groups.set(block,(groups.get(block)||0)+words);
    }
    let allWords=0;
    for(const [element,words]of groups){
      allWords+=words;
      if(!element.getClientRects().length||!element.getBoundingClientRect().height)continue;
      units.push({element,words,start:unitWords});unitWords+=words;
    }
    activeWords=Math.max(1,Math.round(current.words*unitWords/Math.max(1,allWords)));
  }
  function position(){
    if(!current||!unitWords)return {position:lastPosition,viewportWords:150};
    const line=root.innerHeight*.35;let best=null,nearest=Infinity,visibleWords=0;
    for(const unit of units){
      const rect=unit.element.getBoundingClientRect();
      if(!rect.height||!unit.element.getClientRects().length)continue;
      if(rect.bottom>0&&rect.top<root.innerHeight)visibleWords+=unit.words*Math.min(1,Math.max(0,Math.min(rect.bottom,root.innerHeight)-Math.max(0,rect.top))/rect.height);
      const distance=line<rect.top?rect.top-line:line>rect.bottom?line-rect.bottom:0;
      if(distance<nearest){nearest=distance;best={unit,rect};}
    }
    if(!best)return {position:lastPosition,viewportWords:150};
    const local=clamp((line-best.rect.top)/Math.max(1,best.rect.height),0,1);
    return {position:clamp((best.unit.start+local*best.unit.words)/unitWords,0,1),viewportWords:Math.max(50,visibleWords/unitWords*activeWords)};
  }
  function selected(){
    if(root.location.hash==='#volume'||doc.body.classList.contains('phone-volume-open'))return null;
    return chapters.find(r=>!r.element.hidden&&r.element.getClientRects().length)||null;
  }
  function sync(){
    scheduled=false;const next=selected();
    if(next!==current){saveSample();current=next;buildUnits();session=next?new Session(volume+':'+next.id,activeWords):null;lastPosition=0;lastRemaining='';positionFrozen=false;if(session&&now()-lastIntent<IDLE_MS)session.activity(lastIntent);}
    if(!current){paintCurrent();return;}
    const p=position();
    if(!positionFrozen&&now()>=holdUntil){lastPosition=p.position;lastRemaining=remaining(activeWords,lastPosition,rate(history));}
    paintCurrent();
    session.observe({now:now(),position:p.position,viewportWords:p.viewportWords,visible:!doc.hidden,focused:doc.hasFocus(),blocked:blocked()||positionFrozen||now()<holdUntil});
  }
  function schedule(){if(!scheduled){scheduled=true;root.requestAnimationFrame(sync);}}
  function interrupt(pause=0){const t=now();session?.interrupt(t,pause);holdUntil=Math.max(holdUntil,t+pause);}
  function layoutChanged(){
    positionFrozen=true;interrupt(1000);buildUnits();
    // The visible word coordinate system changed. Discard this unfinished
    // observation rather than transfer intervals to different words.
    session=current?new Session(volume+':'+current.id,activeWords):null;
    schedule();
  }
  function activity(event){
    if(event.isTrusted===false)return;
    const target=event.target?.nodeType===1?event.target:event.target?.parentElement;
    if(target?.closest('input,textarea,select,button,summary,[contenteditable="true"],.deep-sketch,[data-learning-terminal],.learning-terminal,.command-ref')){readingOutsideInteractive=false;interrupt(1500);return;}
    if(event.type==='keydown'&&!['ArrowDown','ArrowUp','PageDown','PageUp',' ','Home','End'].includes(event.key))return;
    if(event.type==='wheel'||event.type==='touchmove'||event.type==='keydown'){positionFrozen=false;readingOutsideInteractive=true;}
    lastIntent=now();session?.activity(lastIntent);schedule();
  }
  paintAll();sync();
  doc.addEventListener('pointerdown',activity,{passive:true});doc.addEventListener('wheel',activity,{passive:true});doc.addEventListener('touchmove',activity,{passive:true});doc.addEventListener('keydown',activity);
  root.addEventListener('scroll',schedule,{passive:true});
  doc.addEventListener('toggle',layoutChanged,true);
  root.addEventListener('resize',layoutChanged);
  root.addEventListener('hashchange',()=>{interrupt(1000);schedule();});
  root.addEventListener('blur',()=>interrupt());root.addEventListener('focus',()=>{interrupt();schedule();});
  doc.addEventListener('visibilitychange',()=>{interrupt();schedule();});
  root.addEventListener('pagehide',()=>{saveSample();session=null;current=null;});
  root.addEventListener('pageshow',()=>{interrupt();schedule();});
  root.addEventListener('storage',event=>{if(event.key===KEY){const decoded=event.newValue===null?[]:decode(event.newValue);if(decoded){history=decoded;paintAll();}}});
  const observer=new root.MutationObserver(()=>schedule());
  observer.observe(doc.body,{attributes:true,attributeFilter:['class']});
  for(const row of chapters)observer.observe(row.element,{attributes:true,attributeFilter:['hidden']});
  root.setInterval(sync,1000);
  root.LibraryReadingTime=Object.freeze({version:VERSION,rate:()=>rate(history),sampleCount:()=>history.length,explanation});
})(typeof window==='undefined'?globalThis:window);
'''


def enhance(page):
    """Install one estimator in a reader; preserve all unrelated reader state."""
    if 'id="book-data"' not in page:
        return page
    for tag, identifier in [('style', STYLE_ID), ('script', SCRIPT_ID)]:
        page = re.sub(r'<' + tag + r'\b[^>]*id="' + identifier + r'"[^>]*>.*?</' + tag + '>', '', page, flags=re.S)
    # Old prose-only estimates used a different fixed speed. Keep lead/word count.
    def strip_old_time(match):
        content = re.sub(r'\s*·\s*(?:≈\s*)?\d+(?:[\s\u00a0]\d{3})*\s*мин(?:ут(?:ы|у)?)?\s+чтения\s+без\s+опытов', '', match[2])
        return match[1] + content + match[3]
    page = re.sub(r'(<div class="meta">)(.*?)(</div>)', strip_old_time, page, flags=re.S)
    assert page.count('</head>') == page.count('</body>') == 1
    page = page.replace('</head>', '<style id="' + STYLE_ID + '">' + CSS + '</style></head>', 1)
    page = page.replace('</body>', '<script id="' + SCRIPT_ID + '">' + SCRIPT + '</script></body>', 1)
    return page
