#!/usr/bin/env python3
"""Check explicit arithmetic fixtures. Not a PromQL or Grafana engine."""
from pathlib import Path
import json,math
s=json.loads((Path(__file__).resolve().parent/'fixtures/samples.json').read_text())
g=s['gauge'];present=[v for t,v in g if v is not None]
assert len(present)==4 and sum(present)/len(present)==2.25
assert sum(0 if v is None else v for t,v in g)/len(g)==1.8
c=s['counter'];window=[(t,v) for t,v in c if 0<t<=60];delta=window[-1][1]-window[0][1]+sum(v1 for (t1,v1),(t2,v2) in zip(window,window[1:]) if v2<v1)
assert delta==35 and window[-1][0]-window[0][0]==45
# Explicit fixture: no extrapolation clipped by counter-zero; boundaries 15s/0s,
# average15s and threshold16.5s -> 60/45 factor, rate=35/45.
assert math.isclose(delta/45,7/9)
h=s['histogram'];rank=.9*h['count'];q=.3+(1-.3)*(rank-3)/(4-3);assert math.isclose(q,.72)
r=s['range'];assert (r['end']-r['start'])//r['step_seconds']+1==241
# Limited state model: one numeric series, no errors/no-data/identity changes.
state='Normal';start=None;recovery=None;actual=[]
for t,v in s['alert']['values']:
 if v>s['alert']['threshold']:
  recovery=None
  if state=='Normal':state='Pending';start=t
  if state=='Pending' and t-start>=s['alert']['pending_seconds']:state='Alerting'
  elif state=='Recovering':state='Alerting'
 else:
  if state=='Pending':state='Normal';start=None
  elif state=='Alerting':state='Recovering';recovery=t
  elif state=='Recovering' and t-recovery>=s['alert']['keep_firing_seconds']:state='Normal';recovery=None
 actual.append([t,state])
assert actual==[[0,'Normal'],[15,'Pending'],[30,'Pending'],[45,'Alerting'],[60,'Recovering'],[75,'Recovering'],[90,'Normal']],actual
print('PASS: null/zero means, reset delta, 241 evaluation points, histogram .72s, limited alert timeline. No PromQL/Grafana engine simulated.')
