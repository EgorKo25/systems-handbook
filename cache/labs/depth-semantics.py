"""Portable, bounded Redis semantics checks. No existing server is used.

Requires Redis 7+ and Python 3. Reference run: Redis 7.0.15.
No packages/services are installed; no load or power-loss claims are made.
"""
from pathlib import Path
import sys, tempfile, subprocess, socket, select, time, json, re, shutil
import argparse
parser = argparse.ArgumentParser(description="Verify Redis command semantics using only owned loopback processes (32 MiB each).")
parser.add_argument('--redis-server', default='redis-server', help='Redis 7+ server executable; default: PATH')
parser.add_argument('--output', type=Path, default=Path(__file__).with_name('depth-semantics-results.json'))
options = parser.parse_args()
server_binary = shutil.which(options.redis_server)
if server_binary is None:
 parser.error('Redis executable not found; install separately or pass --redis-server.')
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live import Redis,port,wait_ready
report={'status':'RUNNING','kind':'owned Linux loopback Redis semantic checks','cases':[], 'limits':['No performance measurements','No power-loss or hardware durability experiment','No Sentinel or Cluster deployment/failure experiment','No production services changed','Reference run: Redis 7.0.15, MALLOC=libc; memory sizes depend on the supplied build']}
output=options.output
def check(name,actual,expected):
 if actual!=expected:raise AssertionError((name,actual,expected))
 report['cases'].append({'name':name,'actual':actual,'expected':expected,'status':'PASS'})
def err(v,word):return isinstance(v,dict) and word in v.get('error','')

def published_conditional_lua(index_path):
 from html.parser import HTMLParser
 class ArticleCode(HTMLParser):
  def __init__(self):
   super().__init__(convert_charrefs=True)
   self.matches=0;self.article_depth=0;self.code_depth=0;self.blocks=[];self.parts=[]
  def handle_starttag(self,tag,attrs):
   if tag=='article':
    if self.article_depth:self.article_depth+=1
    elif dict(attrs).get('id')=='08-atomicity':
     self.matches+=1;self.article_depth=1
   if self.article_depth and tag=='code':
    if self.code_depth==0:self.parts=[]
    self.code_depth+=1
  def handle_data(self,data):
   if self.article_depth and self.code_depth:self.parts.append(data)
  def handle_endtag(self,tag):
   if self.article_depth and tag=='code' and self.code_depth:
    self.code_depth-=1
    if self.code_depth==0:self.blocks.append(''.join(self.parts))
   if tag=='article' and self.article_depth:self.article_depth-=1
 parser=ArticleCode();parser.feed(index_path.read_text(encoding='utf-8'));parser.close()
 if parser.matches!=1 or parser.article_depth!=0 or parser.code_depth!=0:
  raise RuntimeError('Expected one complete published article id=08-atomicity.')
 matches=[match for block in parser.blocks for match in
          re.findall(r"EVAL '(\nlocal q =.*?)' 1 book:stock:conditional 3",block,re.S)]
 if len(matches)!=1:
  raise RuntimeError('Expected exactly one published conditional-stock Lua example.')
 return matches[0]
processes=[];clients=[];log=None
temp_dir=tempfile.TemporaryDirectory(prefix='redis-depth-owned-')
try:
 folder=temp_dir.name
 d=Path(folder); log=(d/'log').open('wb')
 def start(name,extra=None):
  pth=d/name;pth.mkdir();n=port()
  proc=subprocess.Popen([server_binary,'--bind','127.0.0.1','--port',str(n),'--dir',str(pth),'--save','','--appendonly','no','--maxmemory','32mb','--maxmemory-policy','noeviction']+(extra or []),stdout=log,stderr=log)
  processes.append(proc);wait_ready(proc,n);r=Redis(n);clients.append(r);return proc,r,n,pth
 proc,r,n,datadir=start('main')
 report['server_version']=r.send('INFO','server').split('redis_version:')[1].splitlines()[0]
 version_tuple=tuple(int(v) for v in report['server_version'].split('.')[:2])
 check('server supports Redis 7+ commands',version_tuple >= (7,0),True)
 payload=b'*2\r\n$3\r\nGET\r\n$7\r\nbook:42\r\n';check('RESP request byte length',len(payload),26)
 raw=socket.create_connection(('127.0.0.1',n),timeout=2);reader=raw.makefile('rb')
 try:
  raw.sendall(payload[:8]);check('no response to incomplete name',bool(select.select([raw],[],[],.05)[0]),False)
  raw.sendall(payload[8:21]);check('no response to incomplete key',bool(select.select([raw],[],[],.05)[0]),False)
  raw.sendall(payload[21:]);check('nil after final five bytes',reader.readline(),b'$-1\r\n')
  raw.sendall(payload+b'*1\r\n$4\r\nPING\r\n')
  check('first pipelined response nil',reader.readline(),b'$-1\r\n');check('second pipelined response pong',reader.readline(),b'+PONG\r\n')
 finally:reader.close();raw.close()
 r.send('SET','book:empty','');check('empty distinct from missing',r.send('GET','book:empty'),'')
 check('missing distinct from empty',r.send('GET','book:42'),None)
 r.send('SET','book:ttl','v1','EX',60);t1=r.send('PTTL','book:ttl');r.send('SET','book:ttl','v2','KEEPTTL');t2=r.send('PTTL','book:ttl')
 check('KEEPTTL preserves existing deadline',0<t2<=t1<=60000,True)
 r.send('SET','book:ttl','v3');check('plain SET clears TTL',r.send('TTL','book:ttl'),-1)
 r.send('SET','book:tx','text');r.send('MULTI');r.send('SET','book:first','done');r.send('INCR','book:tx');r.send('SET','book:last','done');res=r.send('EXEC')
 check('EXEC neighbors survive runtime error',res[0]=='OK' and err(res[1],'integer') and res[2]=='OK',True)
 check('EXEC no rollback',r.send('MGET','book:first','book:tx','book:last'),['done','text','done'])
 r.send('MULTI');check('queue wrong arity is an error',err(r.send('SET','book:arity'),'wrong number'),True);r.send('SET','book:not-executed','x');check('queue error gives EXECABORT',err(r.send('EXEC'),'EXECABORT'),True);check('queue error has no queued effects',r.send('GET','book:not-executed'),None)
 b=Redis(n);clients.append(b)
 r.send('SET','book:watched','10');r.send('WATCH','book:watched');b.send('SET','book:watched','10');r.send('MULTI');r.send('SET','book:watched','11');check('WATCH detects writing identical bytes',r.send('EXEC'),None)
 r.send('SET','book:watched-expire','10','PX',20);r.send('WATCH','book:watched-expire');time.sleep(.04);b.send('GET','book:watched-expire');r.send('MULTI');r.send('SET','book:watched-expire','11');check('WATCH detects expiration',r.send('EXEC'),None)
 bad='redis.call("SET",KEYS[1],"before-error"); return redis.call("INCR",KEYS[1])'
 check('Lua later error',err(r.send('EVAL',bad,1,'book:lua-error'),'integer'),True);check('Lua prior write retained',r.send('GET','book:lua-error'),'before-error')
 script=published_conditional_lua(repo/'cache/index.html')
 r.send('SET','book:stock:conditional',10)
 check('conditional decrement accepted',r.send('EVAL',script,1,'book:stock:conditional',3),[1,'7'])
 check('conditional decrement insufficient',r.send('EVAL',script,1,'book:stock:conditional',8),[0,'7'])
 check('insufficient leaves stock unchanged',r.send('GET','book:stock:conditional'),'7')
 for value in ['0','-1','1.5','1000001','not-number']:
  check('invalid quantity '+value,err(r.send('EVAL',script,1,'book:stock:conditional',value),'BAD_QUANTITY'),True)
 check('invalid quantities leave stock unchanged',r.send('GET','book:stock:conditional'),'7')
 check('missing stock is explicit',r.send('EVAL',script,1,'book:no-stock',1),[0,'missing'])
 for value in ['text','03','-1','1000001']:
  r.send('SET','book:stock:invalid',value);check('invalid stock '+value,err(r.send('EVAL',script,1,'book:stock:invalid',1),'BAD_STOCK'),True)
  check('invalid stock unchanged '+value,r.send('GET','book:stock:invalid'),value)
 r.send('HSET','book:stock:hash','a','b');check('wrong type stock has no mutation',err(r.send('EVAL',script,1,'book:stock:hash',1),'WRONGTYPE'),True);check('wrong type hash retained',r.send('HGET','book:stock:hash','a'),'b')
 r.send('HSET','book:encoding:hash','a','one','b','two');check('small hash is listpack',r.send('OBJECT','ENCODING','book:encoding:hash'),'listpack');before=r.send('MEMORY','USAGE','book:encoding:hash')
 r.send('HSET','book:encoding:hash','long','x'*65);check('long value converts hash',r.send('OBJECT','ENCODING','book:encoding:hash'),'hashtable');after=r.send('MEMORY','USAGE','book:encoding:hash');report['hash_memory']={'before':before,'after':after,'difference_not_pure_encoding_cost':after-before}
 r.send('SADD','book:encoding:set',1,2);check('integer set is intset',r.send('OBJECT','ENCODING','book:encoding:set'),'intset');r.send('SADD','book:encoding:set','text');check('text converts 7.0 set to hashtable',r.send('OBJECT','ENCODING','book:encoding:set'),'hashtable')
 r.send('SET','book:encoding:number',42);check('integer string is int',r.send('OBJECT','ENCODING','book:encoding:number'),'int')
 r.send('ACL','SETUSER','book-reader','reset','on','>reader','~book:product:*','+get','+mget','+ttl','+ping')
 check('ACL dryrun allowed key',r.send('ACL','DRYRUN','book-reader','GET','book:product:42'),'OK')
 check('ACL dryrun forbidden key',r.send('ACL','DRYRUN','book-reader','GET','other:42')!='OK',True)
 check('ACL dryrun forbidden write',r.send('ACL','DRYRUN','book-reader','SET','book:product:42',150)!='OK',True)
 c=Redis(n);clients.append(c);check('reader authenticates',c.send('AUTH','book-reader','reader'),'OK');check('mixed MGET forbidden even absent key',err(c.send('MGET','book:product:42','other:42'),'NOPERM'),True)
 r.send('ACL','SETUSER','book-selector','reset','on','>selector','+get','~book:public:*','(+set ~book:draft:*)')
 check('selector public read allowed',r.send('ACL','DRYRUN','book-selector','GET','book:public:42'),'OK')
 check('selector draft write allowed',r.send('ACL','DRYRUN','book-selector','SET','book:draft:42','x'),'OK')
 check('selector cannot combine get with draft namespace',r.send('ACL','DRYRUN','book-selector','GET','book:draft:42')!='OK',True)
 # Actual AOF process crash and restore; not a power-loss simulation.
 ap,ar,an,ad=start('aof',['--appendonly','yes','--appendfsync','always'])
 check('AOF SET ack',ar.send('SET','book:durable','confirmed'),'OK');ar.close();clients.remove(ar);ap.kill();ap.wait()
 target=d/'aof-restored';shutil.copytree(ad,target);rn=port();rp=subprocess.Popen([server_binary,'--bind','127.0.0.1','--port',str(rn),'--dir',str(target),'--save','','--appendonly','yes','--appendfsync','always','--maxmemory','32mb'],stdout=log,stderr=log);processes.append(rp);wait_ready(rp,rn);rr=Redis(rn);clients.append(rr)
 check('AOF confirmed key after process crash',rr.send('GET','book:durable'),'confirmed')
 check('AOF multipart manifest exists',bool(list(target.rglob('*.manifest'))),True)
 check('WAITAOF availability follows 7.2 boundary',r.send('COMMAND','INFO','WAITAOF')[0] is not None,version_tuple >= (7,2))
 # Independently check arithmetic used in new text.
 check('break-even percentage',round((1-5.6/6.6)*100,2),15.15)
 check('payload MiB per second',40000*2048/1024/1024,78.125)
 report['status']='PASS';report['cases_count']=len(report['cases'])
except Exception as error:
 report['status']='FAIL'
 report['failure_type']=type(error).__name__
 raise
finally:
 for c in clients:
  try:c.close()
  except Exception:pass
 for p in processes:
  if p.poll() is None:p.terminate()
 for p in processes:
  try:p.wait(5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 report['processes_remaining']=sum(p.poll() is None for p in processes)
 if log is not None:log.close()
 temp_dir.cleanup()
 report['cases_count']=len(report['cases'])
 output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda v: {"hex": v.hex()} if isinstance(v, bytes) else str(v))+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'cases':len(report['cases']),'version':report.get('server_version'),'processes_remaining':report['processes_remaining']}))
