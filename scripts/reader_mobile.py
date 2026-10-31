"""Idempotent, self-contained phone controls for the static offline readers."""
import re

ICONS = {
    'prev':'<path d="m14 6-6 6 6 6"/>',
    'chapters':'<path d="M4 6h16M4 12h16M4 18h16"/>',
    'dictionary':'<path d="M4 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4zM14 7a3 3 0 0 1 3-3h3v15h-3a4 4 0 0 0-3 2"/>',
    'view':'<path d="m3 18 5-12 5 12M5 14h6M16 18l3-8 3 8M17 15h4"/>',
    'next':'<path d="m10 6 6 6-6 6"/>',
}

CSS = '''
.phone-tools,.phone-view,.phone-backdrop,.phone-sidebar-close{display:none}
@media(max-width:750px){
.topbar{padding-top:calc(10px + env(safe-area-inset-top))!important}.sidebar{padding-top:calc(20px + env(safe-area-inset-top))!important}.drawer{padding-top:calc(22px + env(safe-area-inset-top))!important}html{scroll-padding-top:calc(76px + env(safe-area-inset-top))!important}
.phone-reference-hint{display:none!important}.deep-sketch .ds-navigation>button{min-width:44px;min-height:44px}.deep-sketch .ds-steps{gap:5px}.deep-sketch .ds-steps button{width:38px;height:38px;min-width:38px;min-height:38px}
html{scroll-padding-top:76px}body{padding-bottom:0}main{padding:24px 20px calc(112px + env(safe-area-inset-bottom))!important;min-width:0}.reader,.chapter{min-width:0;max-width:100%}.chapter{font-size:var(--size,19px);line-height:1.74}.chapter p,.chapter li,.chapter h1,.chapter h2,.chapter h3,.chapter dd{overflow-wrap:anywhere}.chapter h1{font-size:clamp(30px,8vw,39px);line-height:1.13}.chapter h2{font-size:26px;line-height:1.25}.chapter pre{max-width:100%;font-size:13px;line-height:1.65;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}.chapter table{font-size:14px}.table-wrap{width:100%;max-width:100%;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}.chapter .deep-sketch{min-width:0;max-width:100%}
.topbar{min-height:55px;padding:10px 18px;gap:12px}.topbar #menu,.topbar .tools>button{display:none}.topbar-title{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;min-width:0;font:600 12px/1.4 var(--sans);color:var(--muted)}.topbar .tools{flex-shrink:0}.library-back{font-size:12px;padding:7px 9px;border-radius:20px}.progress-track{height:3px}.sidebar{width:min(88vw,350px);z-index:85;padding:20px 18px calc(100px + env(safe-area-inset-bottom))}.chapter-nav a{padding:13px 10px;min-height:46px;font-size:14px}.phone-sidebar-close{display:block;min-height:44px;margin:0 0 15px auto;font:650 13px var(--sans);border-radius:20px}.sidebar input,.drawer input,.drawer select,.phone-view input{font-size:16px}.drawer{z-index:95;top:0;bottom:calc(72px + env(safe-area-inset-bottom));width:100%;padding:22px 18px;overscroll-behavior:contain;border-radius:0 0 20px 20px}.drawer-head{position:sticky;top:-22px;z-index:1;background:var(--paper);padding:12px 0}.drawer-head h2{font-size:22px}.drawer-head button{min-height:44px;border-radius:20px}.command-card .flag-detail>summary{min-height:52px}.command-card .command-intro h2{overflow-wrap:anywhere}.reference-nav{flex-wrap:wrap}.reference-nav button{min-height:42px;font-size:12px}.flag-toolbar input{min-width:0}
.phone-tools{position:fixed;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;z-index:90;left:10px;right:10px;bottom:calc(8px + env(safe-area-inset-bottom));padding:6px;border:1px solid var(--line);border-radius:23px;background:var(--paper);box-shadow:0 5px 30px #0003;font-family:var(--sans)}.phone-tools button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:52px;padding:6px 1px;border:0;border-radius:16px;background:transparent;color:var(--muted);font:650 10px/1.15 var(--sans);touch-action:manipulation}.phone-tools button svg{width:23px;height:23px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.phone-tools button:active{transform:scale(.95)}.phone-tools button[aria-expanded=true]{background:var(--soft);color:var(--accent)}.phone-tools button:focus-visible{outline:2px solid var(--accent);outline-offset:0}.phone-tools [data-phone-action=next]{background:var(--soft);color:var(--accent)}
.phone-backdrop:not([hidden]){display:block;position:fixed;inset:0;z-index:80;background:#07141699;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px)}.phone-view:not([hidden]){display:block;position:fixed;left:10px;right:10px;bottom:calc(86px + env(safe-area-inset-bottom));z-index:95;padding:21px;border:1px solid var(--line);border-radius:23px;background:var(--paper);box-shadow:0 8px 38px #0003;font:15px/1.5 var(--sans)}.phone-view-head{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:18px}.phone-view h2{margin:0;font:750 22px var(--sans)}.phone-view-head button{min-width:44px;min-height:44px;border-radius:50%;padding:5px;font-size:24px}.phone-font-row{display:grid;grid-template-columns:60px 1fr 60px;align-items:center;gap:12px;margin-bottom:14px}.phone-font-row button{min-height:52px;font-size:22px;font-weight:650;border-radius:15px}.phone-font-row output{text-align:center;color:var(--muted);font-size:14px}.phone-theme-toggle{width:100%;min-height:50px;border-radius:15px;text-align:left;padding:12px 16px;font-weight:650}.phone-panel-open{overflow:hidden}
}
@media(prefers-reduced-motion:reduce){.sidebar{transition:none}.phone-tools button:active{transform:none}}
'''

SCRIPT = r'''(()=>{'use strict';
const bar=document.getElementById('phone-tools'),view=document.getElementById('phone-view'),backdrop=document.getElementById('phone-backdrop'),side=document.getElementById('side-nav'),dictionary=document.getElementById('dictionary');
if(!bar||!view||!side||!dictionary)return;
const mq=matchMedia('(max-width:750px)'),button=name=>bar.querySelector('[data-phone-action="'+name+'"]');
for(const hint of document.querySelectorAll('aside.callout'))if(hint.querySelector('strong')?.textContent==='Справка по ходу чтения')hint.classList.add('phone-reference-hint');
function closeView(){view.hidden=true;button('view').setAttribute('aria-expanded','false');}
function sync(){
 const opened=side.classList.contains('open'),dictOpen=!dictionary.hidden;
 button('chapters').setAttribute('aria-expanded',String(opened));button('dictionary').setAttribute('aria-expanded',String(dictOpen));
 backdrop.hidden=!mq.matches||!(opened||dictOpen||!view.hidden);
 document.body.classList.toggle('phone-panel-open',mq.matches&&!backdrop.hidden);
 const size=parseInt(document.documentElement.style.getPropertyValue('--size'),10)||19;
 view.querySelector('output').textContent='Размер текста · '+size;
 view.querySelector('[data-phone-theme]').textContent=document.documentElement.dataset.theme==='dark'?'☀  Светлая тема':'☾  Тёмная тема';
}
function closeAll(){closeView();side.classList.remove('open');document.getElementById('menu').setAttribute('aria-expanded','false');if(!dictionary.hidden)document.getElementById('dictionary-close').click();sync();}
bar.addEventListener('click',event=>{
 const pressed=event.target.closest('[data-phone-action]');if(!pressed)return;
 const action=pressed.dataset.phoneAction;
 if(action==='prev'||action==='next'){
  closeAll();const chapter=document.querySelector('article.chapter:not([hidden])');
  const links=chapter?.querySelectorAll('.footer-nav a');links?.[action==='prev'?0:1]?.click();return;
 }
 if(action==='chapters'){closeView();if(!dictionary.hidden)document.getElementById('dictionary-close').click();document.getElementById('menu').click();sync();return;}
 if(action==='dictionary'){closeView();side.classList.remove('open');document.getElementById(dictionary.hidden?'dictionary-open':'dictionary-close').click();sync();return;}
 if(action==='view'){const was=view.hidden;closeAll();view.hidden=!was;button('view').setAttribute('aria-expanded',String(was));if(was)view.querySelector('[data-phone-close]').focus();sync();}
});
view.addEventListener('click',event=>{const target=event.target.closest('button');if(!target)return;if(target.hasAttribute('data-phone-close')){closeView();sync();button('view').focus();}if(target.dataset.phoneFont){document.getElementById(target.dataset.phoneFont==='up'?'font-up':'font-down').click();sync();}if(target.hasAttribute('data-phone-theme')){document.getElementById('theme').click();sync();}});
view.addEventListener('keydown',event=>{if(event.key!=='Tab')return;const all=[...view.querySelectorAll('button')],first=all[0],last=all.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}});
backdrop.addEventListener('click',closeAll);addEventListener('keydown',event=>{if(event.key==='Escape')closeAll();});
const close=document.createElement('button');close.type='button';close.className='phone-sidebar-close';close.textContent='Закрыть главы ×';close.addEventListener('click',closeAll);side.prepend(close);
new MutationObserver(sync).observe(side,{attributes:true,attributeFilter:['class']});new MutationObserver(sync).observe(dictionary,{attributes:true,attributeFilter:['hidden']});new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
addEventListener('hashchange',()=>{closeView();sync();});mq.addEventListener('change',()=>{if(!mq.matches)closeAll();sync();});sync();
})();'''


def enhance(page, *, home=False):
    page = re.sub(r'(<meta name="viewport" content=")([^"]*)(")',lambda m:m[1]+m[2]+('' if 'viewport-fit=' in m[2] else ',viewport-fit=cover')+m[3],page,count=1)
    page = re.sub(r'<style id="library-phone-style">.*?</style>', '', page, flags=re.S)
    page = re.sub(r'<div id="library-phone-controls">.*?</div><!-- /library-phone-controls -->', '', page, flags=re.S)
    if home:
        css = '''@media(max-width:750px){body{padding:26px 19px 40px}#home-theme-toggle{min-height:44px;padding:9px 16px!important;border-radius:24px!important}h1{font-size:clamp(37px,10vw,56px);line-height:1.04}.grid{grid-template-columns:minmax(0,1fr)!important;gap:15px}.volume{padding:24px!important;min-width:0;border-radius:20px!important}.volume h2{font-size:28px}.volume p{font-size:16px;line-height:1.6}.volume .open{display:inline-block;margin-top:12px}.notes{border-radius:20px!important;padding:24px!important}summary{min-height:44px;padding:10px 0}a,button{touch-action:manipulation}}'''
        return page.replace('</head>','<style id="library-phone-style">'+css+'</style></head>',1)
    controls = '<div id="library-phone-controls"><button id="phone-backdrop" class="phone-backdrop" aria-label="Закрыть панель" hidden></button><section id="phone-view" class="phone-view" role="dialog" aria-modal="true" aria-labelledby="phone-view-title" hidden><div class="phone-view-head"><h2 id="phone-view-title">Как читать</h2><button type="button" data-phone-close aria-label="Закрыть настройки чтения">×</button></div><div class="phone-font-row"><button type="button" data-phone-font="down" aria-label="Уменьшить шрифт">A−</button><output>Размер текста</output><button type="button" data-phone-font="up" aria-label="Увеличить шрифт">A+</button></div><button type="button" class="phone-theme-toggle" data-phone-theme>Тема</button></section><nav id="phone-tools" class="phone-tools" aria-label="Управление чтением">'
    for name,label in [('prev','Назад'),('chapters','Главы'),('dictionary','Справка'),('view','Вид'),('next','Дальше')]:
        attrs = ' aria-expanded="false"' if name in {'chapters','dictionary','view'} else ''
        controls += '<button type="button" data-phone-action="'+name+'"'+attrs+'><svg viewBox="0 0 24 24" aria-hidden="true">'+ICONS[name]+'</svg><span>'+label+'</span></button>'
    controls += '</nav><script>'+SCRIPT+'</script></div><!-- /library-phone-controls -->'
    page = page.replace('</head>','<style id="library-phone-style">'+CSS+'</style></head>',1)
    return page.replace('</body>',controls+'</body>',1)
