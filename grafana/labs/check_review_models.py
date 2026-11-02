#!/usr/bin/env python3
"""Pure arithmetic on authored fixtures. Reads JSON, prints a trace; no writes/network."""
import argparse,json,math
from pathlib import Path

def grid_trace(model,step):
 if not isinstance(step,int) or step<=0:raise ValueError('step must be a positive integer number of seconds')
 start_ms=int(model['from_ms']);end_ms=int(model['to_ms'])
 if start_ms%1000 or end_ms%1000 or end_ms<start_ms:raise ValueError('model supports ordered whole-second endpoints only')
 start=(start_ms//1000//step)*step;end=(end_ms//1000//step)*step
 selected=[[t,v] for t,v in model['table'] if start<=t<=end and (t-start)%step==0]
 return dict(step=step,start=start,end=end,values=selected)

def join_trace(model):
 tables=[]
 times=set()
 for name in ['A','B']:
  table={}
  for key,t,value in model[name]:
   if not isinstance(key,str) or key in table:raise ValueError('model requires unique string instance keys')
   times.add(t);table[key]=value
  tables.append(table)
 if len(times)!=1:raise ValueError('model requires one common time before joining on instance')
 a,b=tables
 inner=[[key,a[key],b[key]] for key in sorted(a.keys() & b.keys())]
 outer=[[key,a.get(key),b.get(key)] for key in sorted(a.keys() | b.keys())]
 return dict(inner=inner,outer=outer)

def alert_trace(model):
 interval=model['evaluation_seconds'];pending=model['pending_seconds'];keep=model['keep_firing_seconds']
 if interval<=0 or pending<0 or keep<0:raise ValueError('invalid timing parameters')
 state='Normal';began=None;recovery=None;result=[];previous=None
 for t,value in model['values']:
  if previous is not None and t-previous!=interval:raise ValueError('model requires regular evaluations')
  if not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('model supports finite numeric values only')
  previous=t
  if value>model['threshold']:
   recovery=None
   if state=='Normal':state='Pending';began=t
   if state=='Pending' and t-began>=pending:state='Alerting'
   elif state=='Recovering':state='Alerting'
  else:
   if state=='Pending':state='Normal';began=None
   elif state=='Alerting':
    if keep==0:state='Normal'
    else:state='Recovering';recovery=t
   elif state=='Recovering' and t-recovery>=keep:state='Normal';recovery=None
  result.append([t,state])
 return result

def evaluate(model):
 grid=[grid_trace(model['grid'],step) for step in model['grid']['steps_seconds']]
 joined=join_trace(model['join']);states=alert_trace(model['alert'])
 assert grid==model['grid']['expected'],'grid expectation differs'
 assert joined['inner']==model['join']['expected_inner'],'inner-join expectation differs'
 assert joined['outer']==model['join']['expected_outer'],'outer-join expectation differs'
 assert states==model['alert']['expected'],'alert expectation differs'
 return dict(boundary=model['description'],grid=grid,join=joined,alert=states,limits=model['limits'])

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--fixture',type=Path,default=Path(__file__).resolve().parent/'fixtures/review-models.json')
 args=parser.parse_args()
 print(json.dumps(evaluate(json.loads(args.fixture.read_text())),ensure_ascii=False,indent=2))
