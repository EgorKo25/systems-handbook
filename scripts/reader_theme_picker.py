"""Shared, offline theme previews for the library and every reader."""
import re


def theme_grid():
    return '<div class="reader-theme-grid" data-reader-theme-grid role="group" aria-label="Темы оформления"></div>'


CSS = r'''
.reader-theme-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.reader-theme-choice{position:relative;display:flex;flex-direction:column;gap:7px;align-items:stretch;min-width:0;min-height:84px;margin:0;padding:7px;border:1px solid var(--reader-line);border-radius:13px;background:var(--reader-paper);color:var(--reader-text);cursor:pointer;box-shadow:none;text-align:left;font:600 12px/1.3 system-ui,sans-serif;touch-action:manipulation}
.reader-theme-choice[aria-pressed=true]{border-color:var(--reader-accent);box-shadow:inset 0 0 0 1px var(--reader-accent)}
.reader-theme-choice:focus-visible{outline:2px solid var(--reader-accent);outline-offset:3px}
.reader-theme-swatch{display:flex;align-items:center;gap:12px;min-height:43px;border:1px solid var(--swatch-text);border-radius:7px;padding:6px 9px;background:var(--swatch-bg);color:var(--swatch-text)}
.reader-theme-swatch>b{font:600 25px/1 Georgia,serif}
.reader-theme-lines{display:grid;gap:4px;flex:1}
.reader-theme-lines>i{display:block;height:2px;border-radius:2px;background:currentColor;opacity:.65}
.reader-theme-lines>i:last-child{width:65%;background:var(--swatch-accent);opacity:1}
.reader-theme-label{display:flex;align-items:center;justify-content:space-between;gap:4px;padding:0 2px}
.reader-theme-label::after{content:'✓';color:var(--reader-accent);visibility:hidden}
.reader-theme-choice[aria-pressed=true] .reader-theme-label::after{visibility:visible}
.reader-theme-dialog{box-sizing:border-box;width:min(620px,calc(100% - 24px));max-width:none;max-height:calc(100dvh - 32px);overflow:auto;margin:auto;padding:24px;border:1px solid var(--reader-line);border-radius:22px;background:var(--reader-paper);color:var(--reader-text);box-shadow:var(--reader-shadow);font:15px/1.5 system-ui,sans-serif;color-scheme:inherit}
.reader-theme-dialog::backdrop{background:rgb(0 0 0 / .2)}
.reader-theme-dialog header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 20px}
.reader-theme-dialog h2{margin:0;color:inherit;font:750 24px/1.2 system-ui,sans-serif;letter-spacing:-.025em}
.reader-theme-close{display:grid;place-items:center;flex:0 0 44px;width:44px;height:44px;min-width:44px;min-height:44px;padding:0;border:1px solid var(--reader-line);border-radius:50%;background:transparent;color:inherit;cursor:pointer;touch-action:manipulation}
.reader-theme-close svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}
.reader-theme-close:focus-visible{outline:2px solid var(--reader-accent);outline-offset:3px}
.reader-theme-caption{margin:14px 0 0;color:var(--reader-muted);font:13px/1.5 system-ui,sans-serif}
.reader-theme-section-title{margin:4px 0 10px;font:650 13px/1.4 var(--sans,system-ui)}
:root:is([data-reader-theme=white],[data-reader-theme=black]) .deep-sketch{--ds-blue:var(--text);--ds-purple:var(--muted);--ds-gold:var(--text);--ds-green:var(--accent)}
:root:is([data-reader-theme=white],[data-reader-theme=black]) mark{background:var(--soft);color:var(--text);outline:1px solid var(--line)}
@media(max-width:750px){
 .reader-theme-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
 .reader-theme-choice{min-height:74px;font-size:12px;padding:6px;gap:5px;border-radius:11px}
 .reader-theme-swatch{min-height:36px;padding:5px 8px}
 .reader-theme-swatch>b{font-size:23px}
 .reader-theme-dialog{padding:20px;border-radius:20px}
 .reader-theme-dialog h2{font-size:22px}
 .phone-view:not([hidden]){max-height:calc(100dvh - 112px - env(safe-area-inset-bottom));overflow-y:auto;overscroll-behavior:contain}
 .phone-view .reader-theme-grid{margin-bottom:2px}
 .phone-view .phone-warmth{margin-bottom:12px}
}
@media print{.reader-theme-dialog{display:none}}
'''

SCRIPT = r'''(()=>{'use strict';
const api=window.LibraryPreferences,dialog=document.getElementById('reader-theme-dialog');
if(!api||!dialog)return;
let origin=null;
for(const grid of document.querySelectorAll('[data-reader-theme-grid]')){
 for(const theme of api.themes){
  const button=document.createElement('button');button.type='button';button.className='reader-theme-choice';button.dataset.readerPreset=theme.id;button.title=theme.description;
  button.setAttribute('aria-label',theme.name);button.setAttribute('aria-pressed','false');
  const sample=document.createElement('span');sample.className='reader-theme-swatch';sample.setAttribute('aria-hidden','true');
  for(const [name,value] of Object.entries(theme.preview))sample.style.setProperty('--swatch-'+name,value);
  const letters=document.createElement('b');letters.textContent='Aa';sample.append(letters);
  const lines=document.createElement('span');lines.className='reader-theme-lines';for(let n=0;n<3;n++)lines.append(document.createElement('i'));sample.append(lines);
  const label=document.createElement('span');label.className='reader-theme-label';label.textContent=theme.name;button.append(sample,label);grid.append(button);
 }
 grid.addEventListener('click',event=>{const button=event.target.closest('[data-reader-preset]');if(button)api.setPreset(button.dataset.readerPreset);});
 grid.addEventListener('dblclick',event=>{if(event.target.closest('button'))event.preventDefault();});
}
function sync(){for(const button of document.querySelectorAll('[data-reader-preset]'))button.setAttribute('aria-pressed',String(button.dataset.readerPreset===api.selectedTheme));}
function open(trigger){origin=trigger;if(!dialog.open)dialog.showModal();dialog.querySelector('[aria-pressed=true]')?.focus({preventScroll:true});}
document.addEventListener('click',event=>{
 const trigger=event.target.closest('#theme,#home-theme-toggle');if(!trigger)return;
 event.preventDefault();event.stopImmediatePropagation();open(trigger);
},true);
dialog.querySelector('[data-reader-theme-close]').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)dialog.close();});
dialog.addEventListener('close',()=>{if(origin?.isConnected)origin.focus({preventScroll:true});});
api.subscribe(sync);sync();
})();'''


def enhance(page):
    page = re.sub(r'<style id="library-theme-picker-style">.*?</style>', '', page, flags=re.S)
    page = re.sub(r'<div id="library-theme-picker">.*?</div><!-- /library-theme-picker -->', '', page, flags=re.S)
    dialog = '<div id="library-theme-picker"><dialog id="reader-theme-dialog" class="reader-theme-dialog" aria-labelledby="reader-theme-title"><header><h2 id="reader-theme-title">Тема оформления</h2><button type="button" class="reader-theme-close" data-reader-theme-close aria-label="Закрыть выбор темы"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></header>'+theme_grid()+'<p class="reader-theme-caption">Одна тема для библиотеки и всех томов.</p></dialog><script>'+SCRIPT+'</script></div><!-- /library-theme-picker -->'
    return page.replace('</head>', '<style id="library-theme-picker-style">'+CSS+'</style></head>',1).replace('</body>',dialog+'</body>',1)
