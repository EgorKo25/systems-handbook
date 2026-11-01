"""A local, selection-triggered dictionary lookup for every offline reader."""
import re

STYLE = '''
.selection-dictionary-action{position:fixed;z-index:110;max-width:calc(100vw - 24px);min-height:44px;padding:10px 16px;border:1px solid var(--reader-line,var(--line));border-radius:14px;background:var(--reader-paper,var(--paper));color:var(--reader-accent,var(--accent));box-shadow:var(--reader-shadow,0 6px 24px #0003);font:650 14px/1.3 system-ui,sans-serif;cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent;user-select:none;-webkit-user-select:none}
.selection-dictionary-action:focus-visible{outline:2px solid var(--reader-accent,var(--accent));outline-offset:3px}
.selection-dictionary-action[hidden]{display:none!important}
@media print{.selection-dictionary-action{display:none!important}}
'''

# Insert inside the existing reference controller: the real renderer, navigation
# and mobile focus handling stay the same as for ordinary dictionary access.
BRIDGE = '''
root.LibraryDictionary = Object.freeze({searchTerms(query, element) {
    rememberOrigin(element || document.activeElement);
    navigation = []; termLimit = 80;
    input.value = String(query); termScope.value = 'all';
    manualTerms = true;
    setMode('terms', true);
    document.getElementById('side-nav')?.classList.remove('open');
    document.getElementById('menu')?.setAttribute('aria-expanded','false');
    drawer.hidden = false; drawer.scrollTop = 0;
    focusReferenceSearch();
}});
'''

SCRIPT = r'''(()=>{'use strict';
if(!window.LibraryDictionary)return;
const button=document.getElementById('selection-dictionary-action');
if(!button)return;
let query='',origin=null,armed=false,frame=0;
function hide(){if(frame)cancelAnimationFrame(frame);frame=0;button.hidden=true;query='';origin=null;}
function element(node){return node?.nodeType===1?node:node?.parentElement;}
function readingSelection(){
 const selected=window.getSelection();
 if(!selected||selected.isCollapsed||selected.rangeCount!==1)return null;
 const range=selected.getRangeAt(0),start=element(range.startContainer),end=element(range.endContainer);
 const chapter=start?.closest('article.chapter:not([hidden])');
 if(!chapter||chapter!==end?.closest('article.chapter:not([hidden])'))return null;
 if(start.closest('input,textarea,select,[contenteditable]:not([contenteditable=false])')||end.closest('input,textarea,select,[contenteditable]:not([contenteditable=false])'))return null;
 const text=selected.toString().replace(/\s+/g,' ').trim();
 if(!text||text.length>160)return null;
 const rect=range.getBoundingClientRect();
 if(!rect.width&&!rect.height)return null;
 return {text,rect,chapter};
}
function update(){
 frame=0;if(armed)return;
 const selection=readingSelection();
 if(!selection){hide();return;}
 const viewport=window.visualViewport;
 const left=viewport?.offsetLeft||0,top=viewport?.offsetTop||0;
 const width=viewport?.width||innerWidth,height=viewport?.height||innerHeight;
 const r=selection.rect;
 const topbar=document.querySelector('.topbar')?.getBoundingClientRect();
 const toolbar=document.getElementById('phone-tools');
 const toolbarRect=toolbar?.getBoundingClientRect();
 const lower=toolbarRect?.height?Math.min(top+height-12,toolbarRect.top-10):top+height-12;
 const upper=Math.max(top+12,topbar?.bottom||0)+8;
 if(r.bottom<upper||r.top>lower){hide();return;}
 query=selection.text;origin=selection.chapter;
 button.setAttribute('aria-label','Найти «'+query+'» в словаре');
 button.hidden=false;
 const box=button.getBoundingClientRect();
 const x=Math.max(left+12,Math.min(r.left+(r.width-box.width)/2,left+width-box.width-12));
 const below=r.bottom+10;
 const y=Math.max(upper,Math.min(below+box.height<=lower?below:r.top-box.height-10,lower-box.height));
 button.style.left=Math.round(x)+'px';button.style.top=Math.round(y)+'px';
}
function schedule(){if(!frame)frame=requestAnimationFrame(update);}
button.addEventListener('pointerdown',event=>{armed=true;event.preventDefault();});
button.addEventListener('pointercancel',()=>{armed=false;schedule();});
button.addEventListener('click',()=>{
 const value=query,target=origin;
 armed=false;hide();
 if(!value||!target?.isConnected)return;
 target.tabIndex=-1;
 window.getSelection()?.removeAllRanges();
 window.LibraryDictionary.searchTerms(value,target);
});
document.addEventListener('pointerup',event=>{if(event.target!==button){armed=false;schedule();}});
document.addEventListener('selectionchange',schedule);
document.addEventListener('scroll',schedule,true);
addEventListener('resize',schedule);
window.visualViewport?.addEventListener('resize',schedule);
window.visualViewport?.addEventListener('scroll',schedule);
addEventListener('hashchange',hide);
addEventListener('keydown',event=>{if(event.key==='Escape'){armed=false;hide();}});
addEventListener('blur',()=>{armed=false;hide();});
})();'''


def enhance(page):
    page = re.sub(r'<style id="library-selection-style">.*?</style>','',page,flags=re.S)
    page = re.sub(r'<div id="library-selection-lookup">.*?</div><!-- /library-selection-lookup -->','',page,flags=re.S)
    page = re.sub(r'\n?root\.LibraryDictionary = Object\.freeze\(\{searchTerms\(query, element\) \{.*?\}\}\);\n?', '', page, flags=re.S)
    marker = 'root.CommandReferenceCoverage='
    if page.count(marker) != 1 or 'function focusReferenceSearch() {' not in page:
        raise ValueError('Expected one enhanced command reference controller')
    page = page.replace(marker,BRIDGE+marker,1)
    popup = '<div id="library-selection-lookup"><button type="button" id="selection-dictionary-action" class="selection-dictionary-action" aria-controls="dictionary" hidden>Найти в словаре</button><script id="library-selection-controller">'+SCRIPT+'</script></div><!-- /library-selection-lookup -->'
    return page.replace('</head>','<style id="library-selection-style">'+STYLE+'</style></head>',1).replace('</body>',popup+'</body>',1)
