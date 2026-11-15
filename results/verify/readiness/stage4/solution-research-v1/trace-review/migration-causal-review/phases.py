import contextlib
import json
from pathlib import Path
import runpy
import signal
import sys

signal.alarm(90)
base=Path(__file__).parent
raw=Path(sys.argv[1])
with (base/(raw.name+'.phase-parser.stdout')).open('w') as log, contextlib.redirect_stdout(log):
    data=runpy.run_path(str(base/'analyze.py'))
pairs,events,residence=data['pairs'],data['events'],data['residence']
stats=data['stats'];probe=json.loads((raw/'probe.json').read_text())
first=min(r[0] for r in residence['to_server'])
affinity=probe['affinity_records']
boundaries=[r['mono_ns'] for r in affinity]+[first+100*10**9]
intervals=[];active={}
for row in data['switches']:
    if row['edge']=='in':active[row['cpu']]=row['ns']
    elif row['cpu'] in active:intervals.append((active.pop(row['cpu']),row['ns'],row['cpu']))
rows=[]
for i,(a,b) in enumerate(zip(boundaries,boundaries[1:])):
    lower=affinity[i]['id'];upper=affinity[i+1]['id'] if i+1<len(affinity) else 10000
    lag=[r['t_send_ms']-r['t_plan_ms'] for r in probe['sent_records'] if lower<=r['id']<upper]
    row=dict(ids=[lower,upper],requested_cpu=affinity[i]['cpu'],start_ns=a,end_ns=b,
             sender_lag_ms=stats(lag),sender_residence_ms={str(cpu):sum(max(0,min(y,b)-max(x,a)) for x,y,c in intervals if c==cpu)/1e6 for cpu in (0,1)},directions={})
    for dev in ('to_server','to_browser'):
        ps=[p for p in pairs if p['dev']==dev and a<=p['callback_ns']<b]
        row['directions'][dev]=dict(callback_lateness_ms=stats([p['callback_lateness_ns']/1e6 for p in ps]),
                                   sampled_now_lateness_ms=stats([p['timer_now_lateness_ns']/1e6 for p in ps]),
                                   dequeue_after_callback_ms=stats([p['callback_to_next_positive_dequeue_ms'] for p in ps if p['callback_to_next_positive_dequeue_ms'] is not None]),
                                   callback_cpus={str(cpu):sum(p['cpu']==cpu for p in ps) for cpu in (0,1)},
                                   queue_to_xmit_ms=stats([r[3] for r in residence[dev] if a<=r[0]<b]),
                                   queue_cpus={str(cpu):sum(k=='net_dev_queue' and f.get('dev')==dev and c==cpu and a<=ns<b for ns,c,k,f in events) for cpu in (0,1)})
    rows.append(row)
result=dict(affinity=affinity,phases=rows)
(base/raw.name/'phase-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
