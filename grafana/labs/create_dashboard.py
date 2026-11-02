#!/usr/bin/env python3
"""Generate the authored stable classic dashboard model. No server requests."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DS={'type':'prometheus','uid':'prom-local'}
def panel(i,title,expr,unit,pos,kind='timeseries',instant=False):
 return {'id':i,'title':title,'type':kind,'datasource':DS,'gridPos':dict(x=pos[0],y=pos[1],w=pos[2],h=pos[3]),'targets':[{'refId':'A','datasource':DS,'expr':expr,'legendFormat':'{{instance}}','range':not instant,'instant':instant,'format':'time_series','editorMode':'code','interval':'15s'}],'fieldConfig':{'defaults':{'unit':unit,'decimals':2,'custom':{'drawStyle':'line','lineInterpolation':'linear','spanNulls':False,'showPoints':'always','pointSize':4}},'overrides':[]},'options':{'legend':{'displayMode':'list','placement':'bottom'},'tooltip':{'mode':'single'}}}
def build():
 base='job="go-lab",instance=~"${instance:regex}"'
 panels=[
 panel(1,'Завершённые запросы / s','sum by (instance) (rate(lab_requests_total{'+base+'}[$__rate_interval]))','reqps',(0,0,12,8)),
 panel(2,'Ошибки 5xx: доля, не проценты','sum by (instance) (rate(lab_requests_total{'+base+',code=~"5.."}[$__rate_interval])) / sum by (instance) (rate(lab_requests_total{'+base+'}[$__rate_interval]))','percentunit',(12,0,12,8)),
 panel(3,'p90 длительности: оценка histogram, s','histogram_quantile(0.90, sum by (le, instance) (rate(lab_request_duration_seconds_bucket{'+base+'}[$__rate_interval])))','s',(0,8,12,8)),
 panel(4,'Текущие активные обработчики','lab_inflight_requests{'+base+'}','short',(12,8,12,8)),
 panel(5,'Успех scrape сейчас','up{'+base+'}','short',(0,16,12,6),'stat',True),
 panel(6,'RSS процесса, bytes','process_resident_memory_bytes{'+base+'}','bytes',(12,16,12,6))]
 panels[4]['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'colorMode':'value','graphMode':'none','justifyMode':'auto','orientation':'auto','textMode':'auto'}
 return {'uid':'go-service-lab','title':'Go service · вопросы и доказательства','schemaVersion':41,'version':1,'timezone':'utc','editable':False,'refresh':'30s','time':{'from':'now-1h','to':'now'},'tags':['handbook','go'],'panels':panels,'annotations':{'list':[{'builtIn':1,'datasource':{'type':'grafana','uid':'-- Grafana --'},'enable':True,'hide':True,'iconColor':'rgba(0,211,255,1)','name':'Annotations & Alerts','type':'dashboard'}]},'templating':{'list':[{'name':'instance','label':'Экземпляр','type':'query','datasource':DS,'definition':'label_values(up{job="go-lab"}, instance)','query':{'query':'label_values(up{job="go-lab"}, instance)','refId':'PrometheusVariableQueryEditor-VariableQuery'},'refresh':1,'multi':True,'includeAll':True,'allValue':'.*','current':{'selected':True,'text':'All','value':'$__all'},'options':[],'sort':1}]},'links':[]}
if __name__=='__main__':(ROOT/'dashboards/go-service.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n')
