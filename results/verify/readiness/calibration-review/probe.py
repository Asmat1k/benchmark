import sys,json,hashlib,time,datetime
from pathlib import Path
import numpy as np
sys.path[:0]=['docker','src/analysis']
from calibration_report import directions,rate
from acceptance import dependence,exact_binomial,probe_records
root=Path('results/verify/diagnostic/calibration.ZQRTHB2H')
read=lambda p:json.loads(p.read_text())
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),integrity=[],echo={},saturation={})
for r in read(root/'captured.json'):
 p=Path(r['path']); okay=hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
 out['integrity'].append(dict(path=str(p),passed=okay))
out['contexts_equal']=read(root/'context-before.json')==read(root/'context-after.json')
out['sources_equal']=read(root/'sources-before.json')==read(root/'sources-after.json')
for p in root.iterdir():
 if p.is_dir() and (p/'probe.json').exists():
  d=read(p/'probe.json')
  if p.name.startswith('saturation'):
   _,loss,direction=p.name.split('-')
   try: out['saturation'][p.name]=rate(p,direction,int(loss)/100)
   except Exception as e: out['saturation'][p.name]=dict(error=str(e))
  else:
   values=d['rtt_ms'];sent=d['sent_records']
   row=dict(sent=len(sent),replies=len(values),median_ms=float(np.median(values)),p99_ms=float(np.percentile(values,99)),dependence=dependence(values),late_slots=sum(r['t_send_ms']>=r['t_plan_ms']+10 for r in sent),max_lag_ms=max(r['t_send_ms']-r['t_plan_ms'] for r in sent))
   try: probe_records(d);row['grid_passed']=True
   except Exception as e:row['grid_error']=str(e)
   try:
    ds=directions(p,d);row['directions']=[dict(direction=r['direction'],entered=len(r['entered_ids']),dropped=len(r['dropped_ids']),CI99=exact_binomial(len(r['dropped_ids']),len(r['entered_ids']))) for r in ds]
   except Exception as e:row['directions_error']=str(e)
   row['capture_logs']={f.name:f.read_text() for f in p.glob('*.log')}
   out['echo'][p.name]=row
for k,v in out['saturation'].items():
 if 'forwarded_bytes'in v:v['mbit_s']=v['forwarded_bytes']*8/v['duration_s']/1e6
Path('results/verify/readiness/calibration-review/observations.json').write_text(json.dumps(out,indent=2)+'\n')
print('Integrity',len(out['integrity']),all(x['passed'] for x in out['integrity']))
for k,v in out['echo'].items():print(k,'median',v['median_ms'],'late',v['late_slots'],'lag1',v['dependence']['lag1'],'directions',v.get('directions_error',v.get('directions')))
print('Rate',out['saturation'])
