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
const key='library-theme-v1', oldHome='library-home-theme-v1', oldBook=__BOOK_KEY__;
const valid=value=>value==='dark'||value==='light';
function read(){
 let value;
 try{value=localStorage.getItem(key);if(valid(value))return value;}catch{}
 try{value=localStorage.getItem(oldHome);if(valid(value))return value;}catch{}
 if(oldBook)try{value=JSON.parse(localStorage.getItem(oldBook)||'null')?.theme;if(valid(value))return value;}catch{}
 return 'dark';
}
let theme=read();
const subscribers=new Set();
function paint(){
 document.documentElement.dataset.theme=theme;
 for(const id of ['theme','home-theme-toggle']){
  const button=document.getElementById(id);if(!button)continue;
  const dark=theme==='dark';button.textContent=dark?'Светлая тема':'Тёмная тема';
  button.setAttribute('aria-pressed',String(dark));
  button.setAttribute('aria-label',dark?'Включить светлую тему':'Включить тёмную тему');
 }
}
function apply(value){if(!valid(value))return theme;theme=value;paint();for(const update of subscribers)update(theme);return theme;}
window.LibraryPreferences={
 get theme(){return theme;},
 setTheme(value){if(!valid(value))return theme;try{localStorage.setItem(key,value);}catch{}return apply(value);},
 subscribe(update){subscribers.add(update);return ()=>subscribers.delete(update);}
};
// Migrate only the shared scalar; no book notes, font size or progress is rewritten.
try{if(!valid(localStorage.getItem(key)))localStorage.setItem(key,theme);}catch{}
paint();
window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(valid(event.newValue)?event.newValue:read());});
window.addEventListener('pageshow',()=>apply(read()));
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
_NEW_APPLY = 'function applyPreferences(){state.theme=window.LibraryPreferences.theme;document.documentElement.dataset.theme=state.theme;'
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
        if _OLD_APPLY in page:
            if page.count(_OLD_APPLY) != 1:
                raise ValueError('ambiguous reader preference function')
            page = page.replace(_OLD_APPLY, _NEW_APPLY)
        elif page.count(_NEW_APPLY) != 1:
            raise ValueError('reader preference function not found')
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
