"""Embed the finite, reviewed external SVG set for offline reader theming.

Original images, source files and alt text remain the no-JavaScript fallback.
Importing this module does not modify files. No runtime network/file API is used.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

ASSETS = {
    'cache': tuple('assets/' + name + '.svg' for name in (
        'book-map', 'locality', 'cache-internals', 'ttl-timeline',
        'cache-hierarchy', 'benchmark-phases', 'redis-system', 'redis-access',
        'tls-chain', 'redis-cow', 'redis-cluster', 'memcached-system',
        'memcached-access', 'memcached-shards', 'memcached-proxy', 'memcached-slabs')),
    'docker': ('labs/elf09-cutaway.svg',),
    'computer-architecture': tuple('labs/illustrations/' + name + '.svg' for name in (
        'cmos-inverter-paths', 'cmos-adder-paths', 'cmos-carry-chain',
        'm32-instruction-datapath', 'nvme-sqe-read', 'nvme-cqe-phase', 'nvme-queue-memory')),
}
COLOURS = {
    'paper': '#f3f7f8 #f4f8fa #f6f8f9 #f6f8fa #fff',
    'soft': '#ffffff #e1e8ec #edf3f5 #edf3f6 #e5edf2',
    'text': '#172f40 #142f43 #172b38 #172e3c #172e40 #202b32 #000',
    'muted': '#506879 #a5b7c3 #405b6e #55778b #71808a #526c7c #c4d0d7 #385266 #3d5162',
    'accent': '#256c8e #194f6a #243f50 #25485b #243c50',
    'blue': '#405fb1', 'red': '#b94343 #9a5943 #7c3b25',
    'gold': '#ac7919 #987926 #744615', 'green': '#087e80 #12644d',
    'blueSoft': '#dceaf1 #e3eff6 #d7e8f3 #edf2f9',
    'redSoft': '#fff4ed', 'goldSoft': '#fff0ba #fff2d8',
    'greenSoft': '#cce7d7 #e4eee7 #e8f1eb', 'accentSoft': '#f4eff8',
    'grid': '#d8e1e7',
}
BY_COLOUR = {colour: role for role, colours in COLOURS.items() for colour in colours.split()}
HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
START = '<!-- library-svg-theme-v1:start -->'
END = '<!-- library-svg-theme-v1:end -->'
BLOCK = re.compile(re.escape(START) + r'[\s\S]*?' + re.escape(END) + r'\n?')

RUNTIME = r'''(() => {
'use strict';
if(window.LibrarySvgTheme || !window.LibraryPreferences?.subscribe)return;
const data=document.getElementById('library-svg-theme-data-v1');
if(!data)return;
const sources=JSON.parse(data.textContent), images=[];
for(const img of document.querySelectorAll('img[src]')){
 const source=img.getAttribute('src');
 if(!Object.hasOwn(sources,source))continue;
 img.setAttribute('data-svg-theme-original-src',source);
 img.addEventListener('error',()=>{
  if(img.getAttribute('src')?.startsWith('data:image/svg+xml'))img.setAttribute('src',source);
 });
 images.push({img,source,svg:sources[source].svg});
}
const mix=(a,b,t)=>a.map((v,i)=>Math.round(v+(b[i]-v)*t));
const colour=value=>{
 const v=value.trim();
 if(/^#[0-9a-f]{6}$/i.test(v))return [1,3,5].map(i=>parseInt(v.slice(i,i+2),16));
 if(/^#[0-9a-f]{3}$/i.test(v))return [...v.slice(1)].map(x=>parseInt(x+x,16));
 const rgb=v.match(/^rgb\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)\s*\)$/i);
 return rgb ? rgb.slice(1).map(x=>Math.max(0,Math.min(255,Number(x)))) : null;
};
const css=rgb=>'#'+rgb.map(x=>x.toString(16).padStart(2,'0')).join('');
const luminance=rgb=>rgb.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;})
 .reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
function readable(seed,backgrounds,min=4.5){
 const score=c=>Math.min(...backgrounds.map(bg=>contrast(c,bg)));
 if(score(seed)>=min)return seed;
 const black=[0,0,0],white=[255,255,255],end=score(black)>score(white)?black:white;
 for(let i=1;i<=100;i++){const next=mix(seed,end,i/100);if(score(next)>=min)return next;}
 return end;
}
function palette(printing){
 if(printing)return {paper:'#ffffff',soft:'#f0f0f0',text:'#000000',muted:'#333333',
  accent:'#000000',blue:'#000000',red:'#000000',gold:'#000000',green:'#000000',
  blueSoft:'#eeeeee',redSoft:'#eeeeee',goldSoft:'#eeeeee',greenSoft:'#eeeeee',
  accentSoft:'#eeeeee',grid:'#dddddd',onAccent:'#ffffff'};
 const style=getComputedStyle(document.documentElement);
 const read=(key,fallback)=>colour(style.getPropertyValue('--reader-'+key))||colour(fallback);
 const paper=read('paper','#ffffff'),soft=read('soft','#eeeeee');
 const text=read('text','#202d34'),muted=read('muted','#5a696e'),accent=read('accent','#0c6b63');
 const dark=luminance(paper)<.35;
 const seeds=dark?{blue:[135,182,244],red:[242,152,154],gold:[228,190,108],green:[132,207,155]}
  :{blue:[45,85,150],red:[161,52,56],gold:[127,84,12],green:[23,104,78]};
 const values={paper,soft,text,muted,accent};
 for(const [role,seed]of Object.entries(seeds))values[role]=mix(seed,accent,.12);
 for(const role of ['blue','red','gold','green','accent'])values[role+'Soft']=mix(paper,values[role],.12);
 const backgrounds=['paper','soft','blueSoft','redSoft','goldSoft','greenSoft','accentSoft'].map(k=>values[k]);
 for(const role of ['text','muted','accent','blue','red','gold','green'])values[role]=readable(values[role],backgrounds);
 values.grid=mix(paper,text,.15); // Decorative dotted grid, not a label or data edge.
 values.onAccent=readable(paper,[values.accent]);
 return Object.fromEntries(Object.entries(values).map(([k,v])=>[k,css(v)]));
}
let printing=false,last='',queued=false;
function render(){
 queued=false;
 const roles=palette(printing),key=JSON.stringify(roles);
 if(key===last)return;
 for(const {img,svg}of images){
  const themed=svg.replace(/__LIBRARY_SVG_([A-Za-z]+)__/g,(_,role)=>roles[role]);
  img.setAttribute('src','data:image/svg+xml;charset=utf-8,'+encodeURIComponent(themed));
 }
 last=key;
}
function schedule(){if(!queued){queued=true;requestAnimationFrame(render);}}
window.LibrarySvgTheme={version:1};
window.LibraryPreferences.subscribe(schedule);
window.addEventListener('beforeprint',()=>{printing=true;render();});
window.addEventListener('afterprint',()=>{printing=false;render();});
const media=window.matchMedia?.('print');
if(media){printing=media.matches;const update=e=>{printing=e.matches;render();};
 if(media.addEventListener)media.addEventListener('change',update);else media.addListener?.(update);}
render();
})();'''


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.sources.append(dict(attrs).get('src'))


def template(source, path):
    """Validate this local, finite SVG vocabulary and replace only colour tokens."""
    if '<!DOCTYPE' in source.upper() or '<!ENTITY' in source.upper():
        raise ValueError(f'{path}: external/entity declarations are not permitted')
    tree = ET.fromstring(source)
    allowed = {'svg', 'defs', 'marker', 'pattern', 'style', 'g', 'text', 'title',
               'desc', 'path', 'rect', 'circle', 'polyline'}
    for element in tree.iter():
        if element.tag.rsplit('}', 1)[-1] not in allowed:
            raise ValueError(f'{path}: unsupported SVG element {element.tag}')
        for key in element.attrib:
            name = key.rsplit('}', 1)[-1].lower()
            if name.startswith('on') or name in {'href', 'src'}:
                raise ValueError(f'{path}: executable or external SVG attribute {key}')
    if re.search(r'@import\b', source, re.I):
        raise ValueError(f'{path}: external CSS is not permitted')
    for target in re.findall(r'url\(([^)]*)\)', source, re.I):
        if not re.fullmatch(r'#[A-Za-z_][\w:.-]*', target.strip()):
            raise ValueError(f'{path}: only internal SVG fragment references are allowed')
    # The one light label sits on the ELF accent band, not on a paper surface.
    if path == 'docker/labs/elf09-cutaway.svg':
        assert source.count('.light{fill:#fff}') == 1
        source = source.replace('.light{fill:#fff}', '.light{fill:__LIBRARY_SVG_onAccent__}')
    def replace(match):
        colour = match[0].lower()
        if colour not in BY_COLOUR:
            raise ValueError(f'{path}: unreviewed colour {colour}')
        return '__LIBRARY_SVG_' + BY_COLOUR[colour] + '__'
    return HEX.sub(replace, source)


def themed_page(page, root, slug):
    """Return new HTML plus an asset manifest; never touch original SVG files."""
    if page.count(START) != page.count(END) or page.count(START) > 1:
        raise ValueError(f'{slug}: malformed or duplicate SVG theme block')
    clean = BLOCK.sub('', page)
    parser = Images()
    parser.feed(clean)
    sources, manifest = {}, []
    for src in ASSETS[slug]:
        if parser.sources.count(src) != 1:
            raise ValueError(f'{slug}/{src}: expected exactly one existing image')
        path = root / slug / src
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'{path}: SVG must remain inside the local build root')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        sources[src] = {'svg': template(raw.decode('utf-8'), f'{slug}/{src}'), 'sha256': digest}
        manifest.append({'path': f'{slug}/{src}', 'bytes': len(raw), 'sha256': digest})
    encoded = json.dumps(sources, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    block = START + '\n<script type="application/json" id="library-svg-theme-data-v1">' + encoded + '</script>\n'
    block += '<script id="library-svg-theme-runtime-v1">' + RUNTIME + '</script>\n' + END + '\n'
    if clean.count('</body>') != 1:
        raise ValueError(f'{slug}: expected one closing body')
    return clean.replace('</body>', block + '</body>', 1), manifest


def apply_svg_themes(root, published_slugs):
    """Post-build, idempotent: validate all selected pages before writing any."""
    root = Path(root).resolve()
    plans, manifest = [], []
    for slug in ASSETS:
        if slug not in published_slugs:
            continue
        path = root / slug / 'index.html'
        before = path.read_bytes()
        after, rows = themed_page(before.decode('utf-8'), root, slug)
        plans.append((path, before, after.encode('utf-8')))
        manifest.extend(rows)
    changed = 0
    for path, before, after in plans:
        if path.read_bytes() != before:
            raise ValueError(f'{path}: page changed during validation')
    for path, before, after in plans:
        if before != after:
            path.write_bytes(after)
            changed += 1
    return {'readers': len(plans), 'changed': changed, 'assets': len(manifest)}
