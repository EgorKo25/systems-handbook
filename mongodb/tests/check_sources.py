#!/usr/bin/env python3
"""Read-only static contract test; no server, downloads or shared build."""
import ast,html,importlib.util,json,pathlib,re,subprocess,sys
sys.dont_write_bytecode=True
p=pathlib.Path(__file__).resolve().parents[1]
def module(file):
 spec=importlib.util.spec_from_file_location('mongodb_check_'+file.stem,file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cfg=module(p/'volume_config.py').CONFIG;ref=module(p/'sources/reference.py');diagrams=module(p/'sources/diagrams.py').DIAGRAMS
order=[x for _,ids in cfg['sections'] for x in ids];assert len(order)==len(set(order))
assert all(x in ('00-route','99-glossary') or x.startswith('mongodb-') for x in order)
words=0
for id in order:
 if id=='99-glossary':continue
 f=p/'sources'/(id+'.html');s=f.read_text();assert s.count('<header>')==s.count('</header>')==s.count('<h1>')==s.count('</h1>')==1
 words+=len(re.findall(r'\S+',re.sub('<[^>]+>',' ',s)))
 assert not re.search(r'<(?:script|iframe)\b|https?://[^\s\"]+\.(?:css|js|woff)(?:[?#\"]|$)',s)
 for href in re.findall(r'href="([^"]+)"',s):
  if href.startswith('#'):assert href[1:] in order,(id,href)
  elif not re.match(r'https?://',href):assert (p/html.unescape(href.split('#')[0])).is_file(),(id,href)
 for block in re.findall(r'<pre><code>(.*?)</code></pre>',s,re.S):assert block.startswith('set -euo pipefail\n'),id
for d in diagrams:
 s=(p/'sources'/(d['chapter']+'.html')).read_text();assert s.count(d['insert_before'])==1
 nodes={x['id'] for x in d['nodes']};edges={x['id'] for x in d['edges']};assert len(nodes)==len(d['nodes'])
 for e in d['edges']:assert e['from'] in nodes and e['to'] in nodes
 for step in d['steps']:
  assert set(step['states'])==nodes and set(step['focus'])<=nodes and set(step['active'])<=edges
  assert step['actor'] and step['fields'] and step['bands']
for c in ref.COMMANDS:
 assert c['volume']=='mongodb' and c['chapter'] in order and c['flags']
 assert c['name'] not in ('go','curl','python3','bash')
 for f in c['flags']:assert all(f.get(k) for k in ('flag','action','when','example','result'))
for f in p.rglob('*.py'):ast.parse(f.read_text())
parser=p.parent/'scripts/command_reference_parser.js'
js=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={normalizeText:v=>String(v).toLowerCase()};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const cards=JSON.parse(fs.readFileSync(0,'utf8'));const get=n=>cards.find(c=>c.name===n);
for(const [name,query,count] of [
 ['mongod','mongod -f "path with spaces.yml" --fork',2],
 ['mongod','mongod --config="path with spaces.yml" --shutdown',2],
 ['mongosh','mongosh --quiet "mongodb://127.0.0.1:27117/" -f "my script.js"',2],
 ['mongosh','mongosh --nodb --eval "print(\'--tls\')" --quiet',3],
 ['mongodump','mongodump --config "private file.yml" --archive="backup file.gz" --gzip',3],
 ['mongorestore','mongorestore --uri "mongodb://127.0.0.1:27118/" --archive="backup file.gz" --gzip --stopOnError',4],
 ['job-service','job-service --mode=bson -- -hint=natural',1],
 ['job-service','job-service -mode=measure -n=200 --hint "tenant state"',3],
 ['job-service','job-service -mode=bson operand --hint=natural',1],
 ]){const c=get(name),r=ctx.analyzeQuery(c,query);assert(r.explicit,query);assert.equal(r.unmatched.length,0,query);assert.equal(r.matchedIndices.length,count,query);}
const r=ctx.analyzeQuery(get('mongosh'),'--eval "mongod --fork"');assert(!r.explicit);assert.equal(r.matchedIndices.length,1);
console.log(JSON.stringify({cases:10,declaredForms:cards.reduce((s,c)=>s+c.flags.reduce((n,f)=>n+ctx.flagForms(f.flag).length,0),0)}));
'''
r=subprocess.run(['node','-e',js,str(parser)],input=json.dumps(ref.COMMANDS),text=True,capture_output=True);assert r.returncode==0,r.stderr
print(json.dumps(dict(chapters=len(order),sourceFragments=len(order)-1,wordsApprox=words,terms=len(ref.GLOSSARY),cards=len(ref.COMMANDS),diagrams=len(diagrams),parser=json.loads(r.stdout)),ensure_ascii=False))
