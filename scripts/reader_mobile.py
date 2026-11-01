"""Idempotent, self-contained phone controls for the static offline readers."""
import re

if __package__:
    from .reader_theme_picker import theme_grid
else:
    from reader_theme_picker import theme_grid

ICONS = {
    'prev':'<path d="m14 6-6 6 6 6"/>',
    'chapters':'<path d="M4 6h16M4 12h16M4 18h16"/>',
    'dictionary':'<path d="M4 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4zM14 7a3 3 0 0 1 3-3h3v15h-3a4 4 0 0 0-3 2"/>',
    'view':'<path d="m3 18 5-12 5 12M5 14h6M16 18l3-8 3 8M17 15h4"/>',
    'next':'<path d="m10 6 6 6-6 6"/>',
}

# The preference bootstrap computes these together. Fall back to the established
# reader colors when JavaScript or storage is unavailable.
PALETTE_FALLBACKS = {
    'light': dict(bg='#f4f1e9', paper='#fffcf5', text='#202d34', muted='#5a696e',
                  line='#d9ded8', accent='#0c6b63', soft='#e8f2ec', code='#182b35',
                  **{'code-text':'#e3eeef', 'shadow':'0 12px 40px #17332b12'}),
    'dark': dict(bg='#142027', paper='#1c2a31', text='#e4e8e1', muted='#b4c1be',
                 line='#3b4c51', accent='#85d2bd', soft='#243d3b', code='#101b21',
                 **{'code-text':'#e4eeee', 'shadow':'0 12px 40px #17332b12'}),
}


def palette_css(*, home=False):
    rules = []
    for theme, colors in PALETTE_FALLBACKS.items():
        selector = ':root' if theme == 'light' and not home else ':root[data-theme='+theme+']'
        if home and theme == 'dark': selector += ',:root:not([data-theme])'
        declarations = ''.join('--'+('home-' if home else '')+name+':var(--reader-'+name+','+value+');'
                               for name,value in colors.items())
        rules.append(selector+'{'+declarations+'}')
    return '\n'.join(rules)

CSS = '''
.drawer h2[tabindex="-1"]:focus,.sidebar .bookname[tabindex="-1"]:focus{outline:0}
.phone-tools,.phone-view,.phone-backdrop,.phone-sidebar-close{display:none}.phone-backdrop{border:0;border-radius:0;padding:0}
body{background:var(--reader-page,var(--bg))}.chapter{font-family:var(--reader-font,var(--serif))}.chapter p,.chapter li,.command-card p,.term p{text-align:justify;text-align-last:start;text-justify:inter-word;hyphens:auto;-webkit-hyphens:auto;overflow-wrap:break-word}.chapter pre,.chapter code{hyphens:none;-webkit-hyphens:none;text-align:start}
@media(max-width:750px){
.phone-volume-open .progress-track,.phone-volume-open main,.phone-volume-open .topbar{display:none!important}.phone-volume-open .sidebar{width:100%;inset:0;padding:28px 24px calc(110px + env(safe-area-inset-bottom));transform:none;transition:none;z-index:85}.phone-volume-open .sidebar .bookname{font-size:30px;line-height:1.15}.phone-volume-open .phone-sidebar-close{display:none}.phone-volume-open .phone-tools{grid-template-columns:repeat(3,minmax(0,1fr))}.phone-volume-open .phone-tools [data-phone-action=chapters],.phone-volume-open .phone-tools [data-phone-action=dictionary]{display:none}.phone-volume-open .sidebar .brand{display:inline-block;margin-bottom:22px;font-size:12px}.phone-volume-open{overflow:hidden}
.phone-settings-preview .phone-backdrop:not([hidden]){background:transparent;backdrop-filter:none;-webkit-backdrop-filter:none}.phone-view .phone-view-head{margin-bottom:14px}.phone-typefaces{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:4px 0 16px}.phone-typefaces button{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:4px;min-height:60px;min-width:0;border-radius:13px;padding:8px 3px}.phone-typefaces button strong{font-size:24px;line-height:1}.phone-typefaces button span{font:11px/1.3 var(--sans)}.phone-typefaces button[aria-pressed=true]{border-color:var(--accent);background:var(--soft);box-shadow:inset 0 0 0 1px var(--accent)}[data-phone-typeface=book] strong{font-family:Georgia,serif}[data-phone-typeface=sans] strong{font-family:system-ui,sans-serif}[data-phone-typeface=palatino] strong{font-family:Palatino,Georgia,serif}.phone-warmth{margin:0 0 16px}.phone-warmth>label{display:flex;justify-content:space-between;gap:12px;font:650 13px var(--sans)}.phone-warmth>label output{color:var(--muted);font-weight:400}.phone-warmth input[type=range]{appearance:none;-webkit-appearance:none;display:block;width:100%;height:38px;margin:4px 0 0;background:transparent;cursor:pointer}.phone-warmth input::-webkit-slider-runnable-track{height:8px;border-radius:9px;background:linear-gradient(90deg,#dce8ed,#dfac59)}.phone-warmth input::-moz-range-track{height:8px;border-radius:9px;background:linear-gradient(90deg,#dce8ed,#dfac59)}.phone-warmth input::-webkit-slider-thumb{appearance:none;-webkit-appearance:none;width:25px;height:25px;border:3px solid var(--paper);border-radius:50%;background:var(--accent);box-shadow:0 1px 5px #0004;margin-top:-8px}.phone-warmth input::-moz-range-thumb{width:20px;height:20px;border:3px solid var(--paper);border-radius:50%;background:var(--accent);box-shadow:0 1px 5px #0004}.phone-warmth-ends{display:flex;justify-content:space-between;color:var(--muted);font:11px var(--sans)}
.phone-view button,.phone-sidebar-close,.drawer button,.deep-sketch button{touch-action:manipulation}.phone-view .phone-view-head button{width:44px;height:44px;min-width:44px;min-height:44px;flex:0 0 44px;display:grid;place-items:center;padding:0;line-height:1;border-radius:50%;font-size:22px}.phone-view-head button svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}
.topbar{padding-top:calc(10px + env(safe-area-inset-top))!important}.sidebar{padding-top:calc(20px + env(safe-area-inset-top))!important}.drawer{padding-top:calc(22px + env(safe-area-inset-top))!important}html{scroll-padding-top:calc(76px + env(safe-area-inset-top))!important}
.phone-reference-hint{display:none!important}.deep-sketch .ds-navigation>button{min-width:44px;min-height:44px}.deep-sketch .ds-steps{gap:5px}.deep-sketch .ds-steps button{width:38px;height:38px;min-width:38px;min-height:38px}
html{scroll-padding-top:76px}body{padding-bottom:0}main{padding:24px 20px calc(112px + env(safe-area-inset-bottom))!important;min-width:0}.reader,.chapter{min-width:0;max-width:100%}.chapter{font-size:var(--size,19px);line-height:1.74}.chapter p,.chapter li,.chapter h1,.chapter h2,.chapter h3,.chapter dd{overflow-wrap:anywhere}.chapter h1{font-size:clamp(30px,8vw,39px);line-height:1.13}.chapter h2{font-size:26px;line-height:1.25}.chapter pre{max-width:100%;font-size:13px;line-height:1.65;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}.chapter table{font-size:14px}.table-wrap{width:100%;max-width:100%;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}.chapter .deep-sketch{min-width:0;max-width:100%}
.topbar{min-height:55px;padding:10px 18px;gap:12px}.topbar #menu,.topbar .tools>button{display:none}.topbar-title{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;min-width:0;font:600 12px/1.4 var(--sans);color:var(--muted)}.topbar .tools{flex-shrink:0}.library-back{font-size:12px;padding:7px 9px;border-radius:20px}.progress-track{height:3px}.sidebar{width:min(88vw,350px);z-index:85;padding:20px 18px calc(100px + env(safe-area-inset-bottom))}.chapter-nav a{padding:13px 10px;min-height:46px;font-size:14px}.phone-sidebar-close{display:block;min-height:44px;margin:0 0 15px auto;font:650 13px var(--sans);border-radius:20px}.sidebar input,.drawer input,.drawer select,.phone-view input{font-size:16px}.drawer{z-index:95;top:0;bottom:calc(72px + env(safe-area-inset-bottom));width:100%;padding:22px 18px;overscroll-behavior:contain;border-radius:0 0 20px 20px}.drawer-head{position:sticky;top:-22px;z-index:1;background:var(--paper);padding:12px 0}.drawer-head h2{font-size:22px}.drawer-head button{min-height:44px;border-radius:20px}.command-card .flag-detail>summary{min-height:52px}.command-card .command-intro h2{overflow-wrap:anywhere}.reference-nav{flex-wrap:wrap}.reference-nav button{min-height:42px;font-size:12px}.flag-toolbar input{min-width:0}
.phone-tools{position:fixed;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;z-index:90;left:10px;right:10px;bottom:calc(8px + env(safe-area-inset-bottom));padding:6px;border:1px solid var(--line);border-radius:23px;background:var(--paper);box-shadow:0 5px 30px #0003;font-family:var(--sans)}.phone-tools button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:52px;padding:6px 1px;border:0;border-radius:16px;background:transparent;color:var(--muted);font:650 10px/1.15 var(--sans);touch-action:manipulation}.phone-tools button svg{width:23px;height:23px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.phone-tools button:active{transform:scale(.95)}.phone-tools button[aria-expanded=true]{background:var(--soft);color:var(--accent)}.phone-tools button:focus-visible{outline:2px solid var(--accent);outline-offset:0}.phone-tools [data-phone-action=next]{background:var(--soft);color:var(--accent)}
.phone-backdrop:not([hidden]){display:block;position:fixed;inset:0;z-index:80;background:#07141699;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px)}.phone-view:not([hidden]){display:block;position:fixed;left:10px;right:10px;bottom:calc(86px + env(safe-area-inset-bottom));z-index:95;padding:21px;border:1px solid var(--line);border-radius:23px;background:var(--paper);box-shadow:0 8px 38px #0003;font:15px/1.5 var(--sans)}.phone-view-head{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:18px}.phone-view h2{margin:0;font:750 22px var(--sans)}.phone-view-head button{min-width:44px;min-height:44px;border-radius:50%;padding:5px;font-size:24px}.phone-font-row{display:grid;grid-template-columns:60px 1fr 60px;align-items:center;gap:12px;margin-bottom:14px}.phone-font-row button{min-height:52px;font-size:22px;font-weight:650;border-radius:15px}.phone-font-row output{text-align:center;color:var(--muted);font-size:14px}.phone-theme-toggle{width:100%;min-height:50px;border-radius:15px;text-align:left;padding:12px 16px;font-weight:650}.phone-panel-open{overflow:hidden}
}
@media(prefers-reduced-motion:reduce){.sidebar{transition:none}.phone-tools button:active{transform:none}}
@media(max-width:750px),(hover:none) and (pointer:coarse){
.chapter a,.drawer a{text-decoration:none;text-underline-offset:0}
.chapter .command-ref{border-bottom:0!important;text-decoration:none!important;color:var(--accent)!important;cursor:pointer}
.chapter .command-ref:hover:not(:focus-visible){outline:none}
.chapter a:focus-visible,.drawer a:focus-visible,.chapter .command-ref:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:3px}
}
'''

SCRIPT = r'''(()=>{'use strict';
const bar=document.getElementById('phone-tools'),view=document.getElementById('phone-view'),backdrop=document.getElementById('phone-backdrop'),side=document.getElementById('side-nav'),dictionary=document.getElementById('dictionary');
if(!bar||!view||!side||!dictionary)return;
const mq=matchMedia('(max-width:750px)'),button=name=>bar.querySelector('[data-phone-action="'+name+'"]');
let volumeLevel=location.hash==='#volume';
for(const hint of document.querySelectorAll('aside.callout'))if(hint.querySelector('strong')?.textContent==='Справка по ходу чтения')hint.classList.add('phone-reference-hint');
function closeView(){view.hidden=true;button('view').setAttribute('aria-expanded','false');}
function sync(){
 const inVolume=mq.matches&&volumeLevel;
 document.body.classList.toggle('phone-volume-open',inVolume);
 if(inVolume&&!side.classList.contains('open'))side.classList.add('open');
 const panelOpen=!view.hidden||!dictionary.hidden;
 button('prev').querySelector('span').textContent=panelOpen?(inVolume?'К тому':'К главе'):inVolume?'Библиотека':'К тому';
 button('prev').setAttribute('aria-label',panelOpen?(inVolume?'К содержанию тома':'Вернуться к чтению'):inVolume?'Вернуться в библиотеку':'К содержанию тома');
 button('next').querySelector('span').textContent=inVolume?'Читать':'Дальше';
 const opened=side.classList.contains('open'),dictOpen=!dictionary.hidden;
 button('chapters').setAttribute('aria-expanded',String(opened));button('dictionary').setAttribute('aria-expanded',String(dictOpen));
 backdrop.hidden=!mq.matches||!(dictOpen||!view.hidden||(opened&&!inVolume));
 document.body.classList.toggle('phone-panel-open',mq.matches&&!backdrop.hidden);
 document.body.classList.toggle('phone-settings-preview',mq.matches&&!view.hidden);
 const size=parseInt(document.documentElement.style.getPropertyValue('--size'),10)||19;
 view.querySelector('output').textContent='Размер текста · '+size;
 const appearance=window.LibraryPreferences?.appearance||{font:'book',warmth:0};
 for(const control of view.querySelectorAll('[data-phone-typeface]'))control.setAttribute('aria-pressed',String(control.dataset.phoneTypeface===appearance.font));
 view.querySelector('[data-phone-warmth]').value=appearance.warmth;
 view.querySelector('[data-phone-warmth-value]').textContent=appearance.warmth+'%';
}
function closeAll(){closeView();side.classList.remove('open');document.getElementById('menu').setAttribute('aria-expanded','false');if(!dictionary.hidden)document.getElementById('dictionary-close').click();sync();}
function continueReading(){const chapter=document.querySelector('article.chapter:not([hidden])');if(chapter)location.hash=chapter.id;}
function parentLevel(){
 if(!view.hidden||!dictionary.hidden){closeAll();return;}
 if(volumeLevel||side.classList.contains('open')){location.href='../index.html';return;}
 closeAll();location.hash='volume';
}
bar.addEventListener('click',event=>{
 const pressed=event.target.closest('[data-phone-action]');if(!pressed)return;
 const action=pressed.dataset.phoneAction;
 if(action==='prev'){parentLevel();return;}
 if(action==='next'){
  if(volumeLevel){continueReading();return;}
  closeAll();const chapter=document.querySelector('article.chapter:not([hidden])');
  const links=chapter?.querySelectorAll('.footer-nav a');links?.[1]?.click();return;
 }
 if(action==='chapters'){closeView();if(!dictionary.hidden)document.getElementById('dictionary-close').click();document.getElementById('menu').click();sync();return;}
 if(action==='dictionary'){closeView();side.classList.remove('open');document.getElementById(dictionary.hidden?'dictionary-open':'dictionary-close').click();sync();return;}
 if(action==='view'){const was=view.hidden;closeAll();view.hidden=!was;button('view').setAttribute('aria-expanded',String(was));if(was)view.querySelector('[data-phone-close]').focus();sync();}
});
view.addEventListener('click',event=>{const target=event.target.closest('button');if(!target)return;if(target.hasAttribute('data-phone-close')){closeView();sync();button('view').focus();}if(target.dataset.phoneFont){document.getElementById(target.dataset.phoneFont==='up'?'font-up':'font-down').click();sync();}if(target.hasAttribute('data-phone-theme')){document.getElementById('theme').click();sync();}if(target.dataset.phoneTypeface){window.LibraryPreferences?.setAppearance?.({font:target.dataset.phoneTypeface});sync();}});
view.addEventListener('input',event=>{if(event.target.matches('[data-phone-warmth]')){window.LibraryPreferences?.setAppearance?.({warmth:Number(event.target.value)});sync();}});
view.addEventListener('dblclick',event=>{if(event.target.closest('button'))event.preventDefault();});
view.addEventListener('keydown',event=>{if(event.key!=='Tab')return;const all=[...view.querySelectorAll('button,input,select')].filter(el=>!el.disabled&&el.getClientRects().length),first=all[0],last=all.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}});
backdrop.addEventListener('click',closeAll);addEventListener('keydown',event=>{if(event.key==='Escape'){if(volumeLevel)continueReading();else closeAll();}});
const close=document.createElement('button');close.type='button';close.className='phone-sidebar-close';close.textContent='Закрыть главы ×';close.addEventListener('click',closeAll);side.prepend(close);
new MutationObserver(sync).observe(side,{attributes:true,attributeFilter:['class']});new MutationObserver(sync).observe(dictionary,{attributes:true,attributeFilter:['hidden']});new MutationObserver(sync).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
window.LibraryPreferences?.subscribe(sync);
function routeLevel(){
 closeView();volumeLevel=location.hash==='#volume';
 if(!volumeLevel)side.classList.remove('open');
 else {
  const search=document.getElementById('search');search.value='';search.dispatchEvent(new Event('input',{bubbles:true}));
  document.getElementById('search-results').hidden=true;
  document.getElementById('chapter-links').hidden=false;
  side.scrollTop=0;
  if(mq.matches){const title=side.querySelector('.bookname');title.tabIndex=-1;title.focus({preventScroll:true});}
 }
 sync();
}
addEventListener('hashchange',routeLevel);mq.addEventListener('change',()=>{if(!mq.matches)closeAll();sync();});routeLevel();
})();'''


def enhance(page, *, home=False):
    page = re.sub(r'(<meta name="viewport" content=")([^"]*)(")',lambda m:m[1]+m[2]+('' if 'viewport-fit=' in m[2] else ',viewport-fit=cover')+m[3],page,count=1)
    page = re.sub(r'<style id="library-phone-style">.*?</style>', '', page, flags=re.S)
    page = re.sub(r'<div id="library-phone-controls">.*?</div><!-- /library-phone-controls -->', '', page, flags=re.S)
    if home:
        page = re.sub(r'<div class="home-toolbar">(<button\b.*?</button>)</div><div class="eyebrow">.*?</div>',lambda m:'<div class="home-masthead"><div class="eyebrow">Интерактивная<br>библиотека</div><div class="home-toolbar">'+m[1]+'</div></div>',page,count=1,flags=re.S)
        css = '''.home-masthead{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:30px}.home-masthead .eyebrow{font-size:18px;line-height:1.35;letter-spacing:.06em}.home-masthead .home-toolbar{margin:0;flex-shrink:0}#home-theme-toggle{min-height:44px;padding:9px 13px!important;border-radius:12px!important;font:600 13px/1.3 system-ui!important;background:transparent;box-shadow:none}#home-theme-toggle::before{content:'◐';font-size:18px;vertical-align:-1px;margin-right:7px}@media(max-width:750px){body{padding:26px 19px 40px}.home-masthead{gap:14px;margin-bottom:30px}.home-masthead .eyebrow{font-size:16px}h1{font-size:clamp(37px,10vw,56px);line-height:1.04}.grid{grid-template-columns:minmax(0,1fr)!important;gap:15px}.volume{padding:24px!important;min-width:0;border-radius:20px!important}.volume h2{font-size:28px}.volume p{font-size:16px;line-height:1.6}.volume .open{display:inline-block;margin-top:12px}.notes{border-radius:20px!important;padding:24px!important}summary{min-height:44px;padding:10px 0}a,button{touch-action:manipulation}}'''
        return page.replace('</head>','<style id="library-phone-style">'+palette_css(home=True)+css+'</style></head>',1)
    # Opening a reference is a reading action on a phone, not a request to type.
    # Focus a non-editable heading before Safari can summon the keyboard.
    focus_helper = '''function focusReferenceSearch() {
    if (matchMedia('(max-width:750px), (pointer:coarse)').matches) {
        const heading = drawer.querySelector('.command-card h2') || drawer.querySelector('.drawer-head h2');
        if (heading) { heading.tabIndex = -1; heading.focus({preventScroll:true}); }
    } else input.focus({preventScroll:true});
}
'''
    if 'function focusReferenceSearch() {' not in page:
        assert page.count('function open(query, element) {') == 1
        page = page.replace('function open(query, element) {',focus_helper+'function open(query, element) {',1)
    page = page.replace('input.focus({ preventScroll: true });','focusReferenceSearch();')
    page = page.replace("$('#term-search').focus();", "if(matchMedia('(max-width:750px), (pointer:coarse)').matches){const heading=$('#dictionary .drawer-head h2');heading.tabIndex=-1;heading.focus({preventScroll:true});}else $('#term-search').focus({preventScroll:true});")
    page = page.replace("const visibleOrigin = originFocus?.isConnected && !originFocus.closest('.chapter[hidden]');", "const visibleOrigin = originFocus?.isConnected && !originFocus.closest('.chapter[hidden]') && originFocus.getClientRects().length;")
    page = page.replace('(visibleOrigin ? originFocus : dictionaryOpen)?.focus({ preventScroll: true });', '(visibleOrigin ? originFocus : document.querySelector(\'[data-phone-action="dictionary"]\')?.getClientRects().length ? document.querySelector(\'[data-phone-action="dictionary"]\') : dictionaryOpen)?.focus({preventScroll:true});')
    controls = '<div id="library-phone-controls"><span id="volume" hidden></span><button id="phone-backdrop" class="phone-backdrop" aria-label="Закрыть панель" hidden></button><section id="phone-view" class="phone-view" role="dialog" aria-modal="true" aria-labelledby="phone-view-title" hidden><div class="phone-view-head"><h2 id="phone-view-title">Текст и тема</h2><button type="button" data-phone-close aria-label="Закрыть настройки чтения"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><div class="phone-font-row"><button type="button" data-phone-font="down" aria-label="Уменьшить шрифт">A−</button><output>Размер текста</output><button type="button" data-phone-font="up" aria-label="Увеличить шрифт">A+</button></div><div class="phone-typefaces" role="group" aria-label="Шрифт текста"><button type="button" data-phone-typeface="book" aria-label="Шрифт Georgia" aria-pressed="true"><strong>Aa</strong><span>Книжный</span></button><button type="button" data-phone-typeface="sans" aria-label="Системный шрифт" aria-pressed="false"><strong>Aa</strong><span>Системный</span></button><button type="button" data-phone-typeface="palatino" aria-label="Шрифт Palatino" aria-pressed="false"><strong>Aa</strong><span>Palatino</span></button></div><div class="phone-warmth"><label for="phone-warmth">Теплота страницы <output data-phone-warmth-value>0%</output></label><input id="phone-warmth" data-phone-warmth type="range" min="0" max="100" step="5" value="0"><div class="phone-warmth-ends"><span>Нейтрально</span><span>Теплее</span></div></div><div class="reader-theme-section-title">Оформление</div>'+theme_grid()+'</section><nav id="phone-tools" class="phone-tools" aria-label="Управление чтением">'
    for name,label in [('prev','К тому'),('chapters','Главы'),('dictionary','Справка'),('view','Вид'),('next','Дальше')]:
        attrs = ' aria-expanded="false"' if name in {'chapters','dictionary','view'} else ''
        controls += '<button type="button" data-phone-action="'+name+'"'+attrs+'><svg viewBox="0 0 24 24" aria-hidden="true">'+ICONS[name]+'</svg><span>'+label+'</span></button>'
    controls += '</nav><script>'+SCRIPT+'</script></div><!-- /library-phone-controls -->'
    page = page.replace('</head>','<style id="library-phone-style">'+palette_css()+CSS+'</style></head>',1)
    return page.replace('</body>',controls+'</body>',1)
