/* Offline snapshot of the existing library appearance API; no network.
   Source: scripts/reader_preferences.py, _BOOTSTRAP; generated 2026-11-01.
   Keep this independent asset with the volume when exporting. */
(() => {
'use strict';
const key='library-theme-v1', presetKey='library-reader-preset-v1', appearanceKey='library-reader-appearance-v1', oldHome='library-home-theme-v1', oldBook=null;
const valid=value=>value==='dark'||value==='light';
const fonts={book:'Georgia, "DejaVu Serif", serif',sans:'system-ui, sans-serif',palatino:'Palatino, Georgia, serif'};
const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
// Each preset owns all reading surfaces. Warmth interpolates a coordinated
// palette; White and Black are monochrome at their neutral endpoint.
// Paper and Night retain the original reader's exact neutral/warm endpoints.
const presets={
 paper:{name:'Бумага',mode:'light',description:'Светлая бумага и спокойный зелёный акцент',supportsWarmth:true,
  neutral:{bg:'#f4f1e9',paper:'#fffcf5',soft:'#e8f2ec',text:'#202d34',muted:'#5a696e',line:'#d9ded8',accent:'#0c6b63',code:'#182b35','code-text':'#e3eeef',shadow:'#17332b12'},
  warm:{bg:'#f4ecde',paper:'#fff7e9',soft:'#eee4d0',text:'#302c25',muted:'#70634f',line:'#ddd1bd',accent:'#79603b',code:'#2b2822','code-text':'#f3ead9',shadow:'#24180e1c'}
 },
 night:{name:'Ночь',mode:'dark',description:'Тёмный сине-серый фон и мягкий светлый текст',supportsWarmth:true,
  neutral:{bg:'#142027',paper:'#1c2a31',soft:'#243d3b',text:'#e4e8e1',muted:'#b4c1be',line:'#3b4c51',accent:'#85d2bd',code:'#101b21','code-text':'#e4eeee',shadow:'#17332b12'},
  warm:{bg:'#24211d',paper:'#2d2923',soft:'#3a332a',text:'#eee7d9',muted:'#c2b8a8',line:'#51483c',accent:'#d8be8b',code:'#191714','code-text':'#ece5d8',shadow:'#130f092e'}
 },
 white:{name:'Белая',mode:'light',description:'Чистый белый фон и чёрный текст',supportsWarmth:true,
  neutral:{bg:'#ffffff',paper:'#ffffff',soft:'#ffffff',text:'#000000',muted:'#333333',line:'#b3b3b3',accent:'#000000',code:'#ffffff','code-text':'#000000',shadow:'#0000000f'},
  warm:{bg:'#f7efdd',paper:'#fff7e7',soft:'#eee3cd',text:'#2a251d',muted:'#6c5b42',line:'#cab99c',accent:'#6f4f2e',code:'#f1e6d0','code-text':'#292319',shadow:'#35251314'}
 },
 black:{name:'Чёрная',mode:'dark',description:'Чистый чёрный фон и белый текст',supportsWarmth:true,
  neutral:{bg:'#000000',paper:'#000000',soft:'#000000',text:'#ffffff',muted:'#cccccc',line:'#666666',accent:'#ffffff',code:'#000000','code-text':'#ffffff',shadow:'#00000000'},
  warm:{bg:'#100d08',paper:'#17120c',soft:'#211b12',text:'#fff0d5',muted:'#d1bfa1',line:'#665339',accent:'#f1d3a0',code:'#0c0905','code-text':'#fff0d5',shadow:'#00000000'}
 },
 sepia:{name:'Сепия',mode:'light',description:'Кремовая страница, тёплые коричневые оттенки',supportsWarmth:true,
  neutral:{bg:'#f1e5cc',paper:'#fbf0d9',soft:'#e8dac0',text:'#362b1e',muted:'#69573f',line:'#cdbb9c',accent:'#75502b',code:'#33291f','code-text':'#f4e6cd',shadow:'#49341b1a'},
  warm:{bg:'#eddfc0',paper:'#f7e9ca',soft:'#e5d4b0',text:'#342719',muted:'#655037',line:'#cab58d',accent:'#704522',code:'#302419','code-text':'#f3e3c4',shadow:'#49341b20'}
 },
 graphite:{name:'Графит',mode:'dark',description:'Нейтральный тёмно-серый фон без синевы',supportsWarmth:true,
  neutral:{bg:'#202020',paper:'#292929',soft:'#343434',text:'#eeeeee',muted:'#bfbfbf',line:'#505050',accent:'#d6c59d',code:'#171717','code-text':'#eeeeee',shadow:'#00000030'},
  warm:{bg:'#27231e',paper:'#302a23',soft:'#3c342a',text:'#f0e8da',muted:'#c9bcaa',line:'#564b3d',accent:'#dfc397',code:'#1b1713','code-text':'#efe5d5',shadow:'#100c0833'}
 },
 midnight:{name:'Полночь',mode:'dark',description:'Глубокий тёмно-синий фон и светлый голубой акцент',supportsWarmth:true,
  neutral:{bg:'#111b2d',paper:'#18253b',soft:'#23344d',text:'#e5edf8',muted:'#b5c5dc',line:'#425775',accent:'#a2c9fa',code:'#0c1422','code-text':'#e4edfa',shadow:'#030a1633'},
  warm:{bg:'#211f27',paper:'#2b2933',soft:'#39343e',text:'#eee7e6',muted:'#c5babc',line:'#564b59',accent:'#d1bbdf',code:'#18161d','code-text':'#eee5e9',shadow:'#100b1338'}
 },
 forest:{name:'Лес',mode:'dark',description:'Приглушённые зелёные поверхности и мягкий светлый текст',supportsWarmth:true,
  neutral:{bg:'#15231d',paper:'#1d2d25',soft:'#2b3d31',text:'#e5eddf',muted:'#bacab5',line:'#485e4a',accent:'#b7d99f',code:'#101a15','code-text':'#e3efdd',shadow:'#08130b30'},
  warm:{bg:'#23261d',paper:'#2d3023',soft:'#3b3e2c',text:'#eeeedd',muted:'#c7c9af',line:'#555b40',accent:'#d0d69f',code:'#181b13','code-text':'#ebeed8',shadow:'#0e13082e'}
 }
};
const validPreset=value=>typeof value==='string'&&Object.hasOwn(presets,value);
const defaultPreset=mode=>mode==='light'?'paper':'night';
function mixColour(from,to,amount){
 if(amount===0)return from;
 if(amount===1)return to;
 const channels=value=>value.slice(1).match(/.{2}/g).map(part=>parseInt(part,16));
 const start=channels(from),end=channels(to),mixed=start.map((value,index)=>Math.round(value+(end[index]-value)*amount));
 return mixed.length===4?'rgba('+mixed.slice(0,3).join(', ')+', '+(mixed[3]/255).toFixed(4)+')':'rgb('+mixed.join(', ')+')';
}
function read(){
 let value;
 try{value=localStorage.getItem(key);if(valid(value))return value;}catch{}
 try{value=localStorage.getItem(oldHome);if(valid(value))return value;}catch{}
 if(oldBook)try{value=JSON.parse(localStorage.getItem(oldBook)||'null')?.theme;if(valid(value))return value;}catch{}
 return 'dark';
}
function readPreset(mode=read()){
 let value;try{value=localStorage.getItem(presetKey);}catch{}
 return validPreset(value)&&presets[value].mode===mode?value:defaultPreset(mode);
}
function normalizeAppearance(value,base={font:'book',warmth:0,size:null}){
 const next={...base};if(!value||typeof value!=='object')return next;
 if(Object.hasOwn(fonts,value.font))next.font=value.font;
 if(typeof value.warmth==='number'&&Number.isFinite(value.warmth))next.warmth=clamp(value.warmth,0,100);
 if(value.size===null)next.size=null;
 else if(typeof value.size==='number'&&Number.isFinite(value.size))next.size=clamp(value.size,16,26);
 return next;
}
function readAppearance(){try{return normalizeAppearance(JSON.parse(localStorage.getItem(appearanceKey)||'null'));}catch{return normalizeAppearance(null);}}
let selectedTheme=readPreset(),theme=presets[selectedTheme].mode,appearance=readAppearance();
let oldSize=null;
if(oldBook)try{const value=JSON.parse(localStorage.getItem(oldBook)||'null')?.size;if(typeof value==='number'&&Number.isFinite(value)&&value>=16&&value<=26)oldSize=value;}catch{}
const subscribers=new Set();
function paint(){
 const html=document.documentElement;
 html.dataset.theme=theme;
 html.dataset.readerTheme=selectedTheme;
 html.style.setProperty('color-scheme',theme);
 html.style.setProperty('--reader-font',fonts[appearance.font]);
 const palette=presets[selectedTheme],amount=palette.supportsWarmth?appearance.warmth/100:0;
 for(const [name,from] of Object.entries(palette.neutral)){
  const colour=mixColour(from,palette.warm[name],amount);
  html.style.setProperty('--reader-'+name,name==='shadow'?'0 12px 40px '+colour:colour);
  // Compatibility with reading copies using the former background-only API.
  if(name==='bg')html.style.setProperty('--reader-page',colour);
 }
 const size=appearance.size===null?oldSize:appearance.size;
 if(size!==null)html.style.setProperty('--size',size+'px');
 for(const id of ['theme','home-theme-toggle']){
  const button=document.getElementById(id);if(!button)continue;
  button.textContent=id==='home-theme-toggle'?'Тема':'Тема: '+palette.name;
  button.title='Текущая тема: '+palette.name;
  button.removeAttribute('aria-pressed');
  button.setAttribute('aria-label','Выбрать тему оформления');
 }
}
function notify(){paint();for(const update of subscribers)update(theme,{...appearance});}
function applyPreset(value){if(!validPreset(value))return selectedTheme;selectedTheme=value;theme=presets[value].mode;notify();return selectedTheme;}
function setPreset(value){
 if(!validPreset(value))return selectedTheme;
 try{localStorage.setItem(presetKey,value);localStorage.setItem(key,presets[value].mode);}catch{}
 return applyPreset(value);
}
window.LibraryPreferences={
 get theme(){return theme;},
 get selectedTheme(){return selectedTheme;},
 get themes(){return Object.entries(presets).map(([id,palette])=>({id,name:palette.name,mode:palette.mode,description:palette.description,supportsWarmth:palette.supportsWarmth,preview:{bg:palette.neutral.bg,paper:palette.neutral.paper,text:palette.neutral.text,accent:palette.neutral.accent}}));},
 get appearance(){return {...appearance};},
 setPreset,
 setTheme(value){if(valid(value))setPreset(defaultPreset(value));return theme;},
 setAppearance(partial){appearance=normalizeAppearance(partial,appearance);try{localStorage.setItem(appearanceKey,JSON.stringify(appearance));}catch{}notify();return {...appearance};},
 subscribe(update){subscribers.add(update);return ()=>subscribers.delete(update);}
};
// Only shared scalars are migrated; notes and other book data are untouched.
try{if(!valid(localStorage.getItem(key)))localStorage.setItem(key,theme);if(!validPreset(localStorage.getItem(presetKey)))localStorage.setItem(presetKey,selectedTheme);}catch{}
paint();
window.addEventListener('storage',event=>{
 if(event.key===presetKey)applyPreset(validPreset(event.newValue)?event.newValue:readPreset());
 else if(event.key===key)applyPreset(readPreset(valid(event.newValue)?event.newValue:read()));
 else if(event.key===appearanceKey){try{appearance=normalizeAppearance(JSON.parse(event.newValue||'null'));}catch{appearance=normalizeAppearance(null);}notify();}
 else if(event.key===null){selectedTheme=readPreset();theme=presets[selectedTheme].mode;appearance=readAppearance();notify();}
});
window.addEventListener('pageshow',()=>{
 // A denied storage API must not undo a choice made in this page's memory.
 try{localStorage.getItem(key);}catch{notify();return;}
 selectedTheme=readPreset();theme=presets[selectedTheme].mode;appearance=readAppearance();notify();
});
function ready(){paint();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});else ready();
})();
/* Model controls use model-theme, never the reader's reserved theme button ID. */
(function(){'use strict';
const api=window.LibraryPreferences;
window.M32Appearance={mount(select,warmth){
 if(!select||!warmth)throw new Error('appearance controls required');
 select.replaceChildren();for(const t of api.themes){const o=document.createElement('option');o.value=t.id;o.textContent=t.name;select.append(o);}
 warmth.min=0;warmth.max=100;warmth.step=5;
 function sync(){select.value=api.selectedTheme;warmth.value=api.appearance.warmth;}
 select.addEventListener('change',()=>api.setPreset(select.value));warmth.addEventListener('input',()=>api.setAppearance({warmth:Number(warmth.value)}));api.subscribe(sync);sync();return api;
}};
}());
