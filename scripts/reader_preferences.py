"""Idempotent, in-memory HTML patch for the library's shared theme.

No files or browser preferences are modified merely by importing this module.
"""
import json
import re

BOOTSTRAP_ID = 'library-preferences-bootstrap-v1'

# Runs before the first stylesheet. Storage failure only prevents persistence;
# the current page still has a consistent in-memory preference.
_BOOTSTRAP = r'''(() => {
'use strict';
const key='library-theme-v1', appearanceKey='library-reader-appearance-v1', oldHome='library-home-theme-v1', oldBook=__BOOK_KEY__;
const valid=value=>value==='dark'||value==='light';
const fonts={book:'Georgia, "DejaVu Serif", serif',sans:'system-ui, sans-serif',palatino:'Palatino, Georgia, serif'};
const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
// Warm the whole reading palette, not a translucent layer over cool panels.
// Neutral endpoints match the original reader CSS exactly, including its shadow.
const palettes={
 light:{
  neutral:{bg:'#f4f1e9',paper:'#fffcf5',soft:'#e8f2ec',text:'#202d34',muted:'#5a696e',line:'#d9ded8',accent:'#0c6b63',code:'#182b35','code-text':'#e3eeef',shadow:'#17332b12'},
  warm:{bg:'#f4ecde',paper:'#fff7e9',soft:'#eee4d0',text:'#302c25',muted:'#70634f',line:'#ddd1bd',accent:'#79603b',code:'#2b2822','code-text':'#f3ead9',shadow:'#24180e1c'}
 },
 dark:{
  neutral:{bg:'#142027',paper:'#1c2a31',soft:'#243d3b',text:'#e4e8e1',muted:'#b4c1be',line:'#3b4c51',accent:'#85d2bd',code:'#101b21','code-text':'#e4eeee',shadow:'#17332b12'},
  warm:{bg:'#24211d',paper:'#2d2923',soft:'#3a332a',text:'#eee7d9',muted:'#c2b8a8',line:'#51483c',accent:'#d8be8b',code:'#191714','code-text':'#ece5d8',shadow:'#130f092e'}
 }
};
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
function normalizeAppearance(value,base={font:'book',warmth:0,size:null}){
 const next={...base};if(!value||typeof value!=='object')return next;
 if(Object.hasOwn(fonts,value.font))next.font=value.font;
 if(typeof value.warmth==='number'&&Number.isFinite(value.warmth))next.warmth=clamp(value.warmth,0,100);
 if(value.size===null)next.size=null;
 else if(typeof value.size==='number'&&Number.isFinite(value.size))next.size=clamp(value.size,16,26);
 return next;
}
function readAppearance(){try{return normalizeAppearance(JSON.parse(localStorage.getItem(appearanceKey)||'null'));}catch{return normalizeAppearance(null);}}
let theme=read(),appearance=readAppearance();
let oldSize=null;
if(oldBook)try{const value=JSON.parse(localStorage.getItem(oldBook)||'null')?.size;if(typeof value==='number'&&Number.isFinite(value)&&value>=16&&value<=26)oldSize=value;}catch{}
const subscribers=new Set();
function paint(){
 const html=document.documentElement;
 html.dataset.theme=theme;
 html.style.setProperty('--reader-font',fonts[appearance.font]);
 const palette=palettes[theme],amount=appearance.warmth/100;
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
  const dark=theme==='dark';button.textContent=dark?'Светлая тема':'Тёмная тема';
  button.setAttribute('aria-pressed',String(dark));
  button.setAttribute('aria-label',dark?'Включить светлую тему':'Включить тёмную тему');
 }
}
function notify(){paint();for(const update of subscribers)update(theme,{...appearance});}
function apply(value){if(!valid(value))return theme;theme=value;notify();return theme;}
window.LibraryPreferences={
 get theme(){return theme;},
 get appearance(){return {...appearance};},
 setTheme(value){if(!valid(value))return theme;try{localStorage.setItem(key,value);}catch{}return apply(value);},
 setAppearance(partial){appearance=normalizeAppearance(partial,appearance);try{localStorage.setItem(appearanceKey,JSON.stringify(appearance));}catch{}notify();return {...appearance};},
 subscribe(update){subscribers.add(update);return ()=>subscribers.delete(update);}
};
// Only shared scalars are migrated; notes and other book data are untouched.
try{if(!valid(localStorage.getItem(key)))localStorage.setItem(key,theme);}catch{}
paint();
window.addEventListener('storage',event=>{
 if(event.key===key)apply(valid(event.newValue)?event.newValue:read());
 else if(event.key===appearanceKey){try{appearance=normalizeAppearance(JSON.parse(event.newValue||'null'));}catch{appearance=normalizeAppearance(null);}notify();}
 else if(event.key===null){theme=read();appearance=readAppearance();notify();}
});
window.addEventListener('pageshow',()=>{theme=read();appearance=readAppearance();notify();});
function ready(){
 paint();
 const button=document.getElementById('home-theme-toggle');
 if(button)button.addEventListener('click',()=>window.LibraryPreferences.setTheme(theme==='dark'?'light':'dark'));
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});else ready();
})();'''

_OLD_CLICK = "$('#theme').addEventListener('click',()=>{state.theme=state.theme==='dark'?'light':'dark';applyPreferences();save();});"
_NEW_CLICK = "$('#theme').addEventListener('click',()=>{state.theme=window.LibraryPreferences.setTheme(window.LibraryPreferences.theme==='dark'?'light':'dark');applyPreferences();save();});"
_OLD_APPLY = 'function applyPreferences(){document.documentElement.dataset.theme=state.theme;'
_PREVIOUS_APPLY = 'function applyPreferences(){state.theme=window.LibraryPreferences.theme;document.documentElement.dataset.theme=state.theme;'
_NEW_APPLY = 'function applyPreferences(){state.theme=window.LibraryPreferences.theme;const appearance=window.LibraryPreferences.appearance;if(appearance.size!==null)state.size=appearance.size;document.documentElement.dataset.theme=state.theme;'
_OLD_DOWN = "$('#font-down').onclick=()=>{state.size=Math.max(16,state.size-1);applyPreferences();save();};"
_NEW_DOWN = "$('#font-down').onclick=()=>{state.size=window.LibraryPreferences.setAppearance({size:Math.max(16,(Number(state.size)||19)-1)}).size;applyPreferences();save();};"
_OLD_UP = "$('#font-up').onclick=()=>{state.size=Math.min(26,state.size+1);applyPreferences();save();};"
_NEW_UP = "$('#font-up').onclick=()=>{state.size=window.LibraryPreferences.setAppearance({size:Math.min(26,(Number(state.size)||19)+1)}).size;applyPreferences();save();};"
_SUBSCRIBE = 'window.LibraryPreferences.subscribe(()=>applyPreferences());'


def enhance(page, *, home=False):
    """Return patched HTML; preserve unrelated reader state and HTML verbatim."""
    page = re.sub(r'\n?<script\b[^>]*id="' + BOOTSTRAP_ID + r'"[^>]*>.*?</script>\n?', '', page, flags=re.S)
    if home:
        # Remove only the former home-specific theme controllers, not other scripts.
        def remove_legacy(match):
            source = match[1]
            if 'library-home-theme-v1' in source and ('home-theme-toggle' in source or 'document.documentElement.dataset.theme' in source):
                return ''
            return match[0]
        page = re.sub(r'<script\b[^>]*>(.*?)</script>', remove_legacy, page, flags=re.S)
        book_key = None
    else:
        match = re.search(r'\bdata-storage-key="([^"]+)"', page)
        book_key = match[1] if match else None
        if book_key is None:
            match = re.search(r"Object\.assign\(state,JSON\.parse\(localStorage\.getItem\('([^']+)'\)", page)
            book_key = match[1] if match else None
        if not book_key:
            raise ValueError('reader storage key not found')
        if _OLD_CLICK in page:
            if page.count(_OLD_CLICK) != 1:
                raise ValueError('ambiguous reader theme toggle')
            page = page.replace(_OLD_CLICK, _NEW_CLICK)
        elif page.count(_NEW_CLICK) != 1:
            raise ValueError('reader theme toggle not found')
        for prefix in (_OLD_APPLY, _PREVIOUS_APPLY):
            if prefix in page:
                if page.count(prefix) != 1:
                    raise ValueError('ambiguous reader preference function')
                page = page.replace(prefix, _NEW_APPLY)
                break
        if page.count(_NEW_APPLY) != 1:
            raise ValueError('reader preference function not found')
        for before, after in ((_OLD_DOWN, _NEW_DOWN), (_OLD_UP, _NEW_UP)):
            if before in page:
                page = page.replace(before, after)
            elif page.count(after) != 1:
                raise ValueError('reader font-size control not found')
        if _SUBSCRIBE not in page:
            page, changed = re.subn(r'(function applyPreferences\(\)\{[^\n]*\})', lambda m:m[1]+'\n'+_SUBSCRIBE, page, count=1)
            if changed != 1:
                raise ValueError('reader preference subscription point not found')
    script = '\n<script id="'+BOOTSTRAP_ID+'">'+_BOOTSTRAP.replace('__BOOK_KEY__', json.dumps(book_key))+'</script>\n'
    head = re.search(r'<head\b[^>]*>', page)
    if head is None:
        raise ValueError('head not found')
    # Keep charset within the first 1024 bytes while applying before CSS/paint.
    charset = re.search(r'<meta\b[^>]*charset[^>]*>', page[head.end():], re.I)
    position = head.end()+charset.end() if charset else head.end()
    return page[:position]+script+page[position:]
