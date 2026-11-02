"""One source for the native test request and the literal JSON in chapter 05."""
def payload(interval_ms=15000):
 return {'from':'1700000000000','to':'1700000030000','queries':[{'refId':'A','expr':'lab_inflight_requests{job="go-lab"}','range':True,'instant':False,'format':'time_series','datasource':{'type':'prometheus','uid':'prom-local'},'intervalMs':interval_ms,'maxDataPoints':120}]}
