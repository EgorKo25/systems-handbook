"""Read owned ELF, Go-test JSONL, or benchmark text without executing its contents."""
import argparse,hashlib,json,math,re,statistics,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('kind',choices=['elf','events','stats']);p.add_argument('file',type=Path)
p.add_argument('--require',action='append',default=[])
a=p.parse_args();raw=a.file.read_bytes()
if a.kind=='elf':
 if raw[:6]!=b'\x7fELF\x02\x01':p.error('expected ELF64 little-endian')
 h=struct.unpack_from('<16sHHIQQQIHHHHHH',raw);entry,off,size,count=h[4],h[5],h[9],h[10]
 if size!=56 or off+size*count>len(raw):p.error('invalid program header bounds')
 loads=[]
 for i in range(count):
  t,flags,o,v,pa,fs,ms,align=struct.unpack_from('<IIQQQQQQ',raw,off+i*size)
  if t==1:
   if fs>ms or o+fs>len(raw) or (align>1 and (o-v)%align):p.error('invalid PT_LOAD')
   loads.append(dict(offset=o,vaddr=v,filesz=fs,memsz=ms,align=align,flags=flags,file_end=o+fs,zero_from=v+fs,memory_end=v+ms,zero_bytes=ms-fs))
 print(json.dumps(dict(sha256=hashlib.sha256(raw).hexdigest(),file_bytes=len(raw),header_hex=raw[:64].hex(' '),entry=entry,loads=loads),indent=2))
elif a.kind=='events':
 events=[]
 try:
  for line in raw.decode().splitlines():events.append(json.loads(line))
 except (ValueError,UnicodeError) as e:p.error('truncated or invalid JSONL: '+str(e))
 passed={e['Package']+'/'+e['Test'] for e in events if e.get('Action')=='pass' and e.get('Test')}
 ran={e['Package']+'/'+e['Test'] for e in events if e.get('Action')=='run' and e.get('Test')}
 packages={e['Package'] for e in events if e.get('Action')=='start' and not e.get('Test')}
 final={e['Package']:e['Action'] for e in events if e.get('Action') in ('pass','fail','skip') and not e.get('Test')}
 failures=[e for e in events if e.get('Action') in ('fail','build-fail')]
 missing=[n for n in a.require if n not in passed or n not in ran]
 ok=bool(packages) and all(final.get(n)=='pass' for n in packages) and not failures and not missing
 print(json.dumps(dict(ok=ok,packages=sorted(packages),final=final,tests_run=sorted(ran),tests_passed=sorted(passed),missing=missing,failures=failures),indent=2))
 raise SystemExit(0 if ok else 1)
else:
 groups={}
 for line in raw.decode().splitlines():
  m=re.match(r'(Benchmark\S+)\s+\d+\s+([0-9.]+)\s+ns/op',line)
  if m:groups.setdefault(m[1],[]).append(float(m[2]))
 if not groups:p.error('no benchmark samples')
 result={}
 for n,xs in groups.items():
  xs=sorted(xs);q=statistics.quantiles(xs,n=4,method='inclusive') if len(xs)>1 else [xs[0]]*3
  result[n]=dict(samples=len(xs),unit='ns/op',median=statistics.median(xs),q1=q[0],q3=q[2],nearest_rank_p95=xs[math.ceil(.95*len(xs))-1],min=xs[0],max=xs[-1])
 print(json.dumps(result,indent=2))
