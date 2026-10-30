/* Run: node work/library/ere-engine-tests.js
 * Uses the actual GNU grep -E in LC_ALL=C.UTF-8.
 * No package installation. The engine itself needs only a browser's JS runtime.
 */
'use strict';
const assert = require('assert');
const cp = require('child_process');
const path = require('path');
const E = require('./ere-engine.js');
const env = Object.assign({}, process.env, {LC_ALL:'C.UTF-8', LANG:'C.UTF-8'});
let checked = 0;
function grep(pattern,text,ignoreCase) {
  const opts=['-a','-E','-o','-b'];
  if(ignoreCase)opts.push('-i');
  opts.push('--',pattern);
  const r=cp.spawnSync('grep',opts,{input:text+'\n',encoding:'utf8',env,timeout:5000,maxBuffer:1000000});
  if(r.error)throw r.error;
  assert([0,1].includes(r.status),'grep failed '+JSON.stringify({pattern,text,stderr:r.stderr}));
  const nonempty=[];
  const lines=r.stdout.split('\n');
  for(let i=0;i<lines.length-1;i++) {
    const sep=lines[i].indexOf(':'),byteStart=Number(lines[i].slice(0,sep)),body=lines[i].slice(sep+1);
    const start=Buffer.from(text,'utf8').subarray(0,byteStart).toString('utf8').length;
    nonempty.push({start,end:start+body.length});
  }
  const q=cp.spawnSync('grep',['-a','-E','-q',...(ignoreCase?['-i']:[]),'--',pattern],
    {input:text+'\n',encoding:'utf8',env,timeout:5000});
  assert([0,1].includes(q.status),'grep -q failed');
  return {nonempty,selected:q.status===0};
}
function verify(pattern,text,ignoreCase=false) {
  const engine=E.compile(pattern,{ignoreCase}),all=engine.findAll(text),actual=grep(pattern,text,ignoreCase);
  assert.deepStrictEqual(all.filter(x=>x.end>x.start),actual.nonempty,
    'nonempty mismatch '+JSON.stringify({pattern,text,ignoreCase,all,actual}));
  assert.strictEqual(all.length>0,actual.selected,
    'selection mismatch '+JSON.stringify({pattern,text,ignoreCase,all,actual}));
  for(let i=0;i<all.length;i++) {
    assert(all[i].start>=0&&all[i].end>=all[i].start&&all[i].end<=text.length);
    if(i)assert(all[i].start>=all[i-1].end);
  }
  checked++;
}
// Leftmost-longest, not JS alternation's first successful branch.
assert.deepStrictEqual(E.compile('a|ab').findAll('ab'),[{start:0,end:2}]);
assert.deepStrictEqual(E.compile('(a|aa)*').findAll('aaaa').filter(x=>x.end>x.start),[{start:0,end:4}]);
assert.deepStrictEqual(E.compile('😀.').findAll('x😀я!'),[{start:1,end:4}]);
const patterns=[
  '', 'a','ab','abc','a|ab','ab|a','a|abc','(a|ab)b','(ab|a)*','(a|aa)*',
  '.','..','.*','.+','.?','^a','a$','^a$','^$','^(a|ab)$',
  'a*','a+','a?','a{0}','a{1}','a{2}','a{1,3}','a{0,2}','a{2,}',
  '(ab){1,3}','(a?)*','(a*)+','((ab)?)*',
  '[ab]','[^ab]','[a-z]','[A-Z]','[0-9]','[A-Za-z0-9_]+',
  '[-a]+','[a-]+','[]a]+','[^]a]+','[[]','[--0]',
  '[[:digit:]]+','[[:alpha:]]+','[[:alnum:]_]+','[[:space:]]+',
  '[[:blank:]]+','[[:xdigit:]]+','[^[:space:]]+','[[:alpha:]0-9]+',
  '\\.','\\+','\\?','\\*','\\(','\\)','\\[','\\]','\\{','\\}','\\|','\\\\',
  'я','[яю]+','(я|😀)+','😀*','[^😀]+'
];
const texts=[
  '', 'a','ab','aab','abc','aaaa','baba','bbb','xabcab!',' -./01239AZ_afz',
  'one two\tthree','[](){}+*?|\\.','Привет мир','яюя😀!','😀😀aя','é中Ω9',
  '\t \r','\u00a0\u2003x'
];
for(let i=0;i<patterns.length;i++) {
  // Every declared feature gets several real comparisons, with Unicode samples too.
  for(const j of [i%texts.length,(i*7+3)%texts.length,(i*11+9)%texts.length])
    verify(patterns[i],texts[j]);
}
for(const p of ['a','[A-Z]+','[^A]','[a-z]+','(a|AB)+','[[:alpha:]]+','^ABC$','[A-z]+']) {
  for(const t of ['ABCabc','aB Ab 17','zzz','abc','AZ_az'])verify(p,t,true);
}
// Deterministic generated expressions exercise combinations.
let seed=128376;
function random(n){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%n;}
const atoms=['a','b','c','.','[ab]','[^c]','[a-c]','(ab|a)','(a|bc)','я','[[:digit:]]'];
const repeats=['','*','+','?','{0,2}','{1,3}','{2}','{1,}'];
for(let n=0;n<120;n++) {
  const a=atoms[random(atoms.length)]+repeats[random(repeats.length)];
  const b=atoms[random(atoms.length)]+repeats[random(repeats.length)];
  const p=random(2)?a+b:'('+a+'|'+b+')';
  let t='';for(let k=0;k<random(18);k++)t+=['a','b','c','я','1',' '][random(6)];
  verify(p,t);
}
// Character classes are backed by generated C.UTF-8 glibc classifications.
for(const name of E.supportedClasses)
  for(const text of ['AaяЁé中Ω','09０١','\t \r\u00a0\u2003','+-_.😀'])
    verify('[[:'+name+':]]+',text);
const rejected=[
  '\\1','\\9','\\d','\\w','\\s','\\b','\\<','a\\q',
  '(?=a)','(?:a)','(?<name>a)','(?!a)','a+?','a++','a**',
  '(','[','[]','[^]','a{','a{2,1}','a{201}','a{1,x}','a{1,2',
  '[z-a]','[я-ю]','[[.a.]]','[[=a=]]','[[:word:]]','[[:digit:]',
  'a|','|a','()','a^b','a$b','a\nb'
];
for(const p of rejected)assert.throws(()=>E.compile(p),undefined,'must reject '+JSON.stringify(p));
assert.throws(()=>E.compile('a').findAll('a\nb'));
assert.throws(()=>E.compile('a').findAll('\0'));
assert.throws(()=>E.compile('(a{200}){200}'));
assert.throws(()=>E.compile('a'.repeat(513)));
assert.throws(()=>E.compile('a').findAll('a'.repeat(12001)));
const version=cp.spawnSync('grep',['--version'],{encoding:'utf8'}).stdout.split('\n')[0];
console.log(JSON.stringify({status:'passed',actualGrepComparisons:checked,
  rejectedPatterns:rejected.length,locale:env.LC_ALL,grep:version,
  engine:E.version,classes:E.classSource,limits:E.limits},null,2));
