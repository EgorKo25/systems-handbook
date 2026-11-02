import os,subprocess,time
start=time.perf_counter()
p=subprocess.run([os.environ['GO'],'test','-count=1','./...'],timeout=120)
print(f'elapsed_seconds={time.perf_counter()-start:.6f} exit={p.returncode}')
raise SystemExit(p.returncode)
