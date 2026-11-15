from bisect import bisect_right
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import statistics
import sys
import time

started=time.monotonic();run=Path(sys.argv[1]);out=Path(sys.argv[2]);d=run/'r80p1-check'
read=lambda p:json.loads(p.read_text())
fields=lambda text:dict(re.findall(r'(\w+)=(\S+)',text))
events=[]
for line in (d/'trace.txt').read_text().splitlines():
 m=re.search(r'\[(\d+)\].*? (\d+)\.(\d+): (\w+): (.*)',line)
 if m:events.append(dict(cpu=int(m[1]),ns=int(m[2])*10**9+int(m[3].ljust(9,'0')),kind=m[4],text=m[5]))
events.sort(key=lambda e:e['ns'])
latest_queue={};queue_identity={};qdequeues=defaultdict(list);starts={};callbacks={};active={};sender=int(read(d/'sender-target.json')['host_tid'])
for ordinal,e in enumerate(events):
 e['ordinal']=ordinal
 f=fields(e['text']);k=e['kind'];cpu=e['cpu']
 if k=='sched_switch':
  if int(f['prev_pid'])==sender:active.pop(cpu,None)
  if int(f['next_pid'])==sender:active[cpu]=True
 e['sender_active_cpus']=sorted(active)
 if k=='net_dev_queue':latest_queue[(f['skbaddr'],cpu)]=(f['dev'],e['ns'])
 if k=='qdisc_enqueue' and (f['skbaddr'],cpu) in latest_queue:
  dev,t=latest_queue[(f['skbaddr'],cpu)];key=(f['ifindex'],f['handle']);assert key not in queue_identity or queue_identity[key]==dev;queue_identity[key]=dev
 if k=='qdisc_dequeue':qdequeues[cpu].append(e)
 if k=='hrtimer_start':starts[(f['hrtimer'],e['ns'])]=e
 if k=='hrtimer_expire_entry':callbacks[(f['hrtimer'],e['ns'])]=e
qdtimes={c:[e['ordinal'] for e in es] for c,es in qdequeues.items()}
pointer_directions=defaultdict(Counter);associations=[]
for (ptr,ns),e in starts.items():
 es=qdequeues[e['cpu']];idx=bisect_right(qdtimes[e['cpu']],e['ordinal'])
 if idx==len(es):continue
 q=es[idx];f=fields(q['text']);dev=queue_identity.get((f['ifindex'],f['handle']))
 if f['packets']=='0' and dev:
  pointer_directions[ptr][dev]+=1
  associations.append(dict(timer=ptr,start_ns=ns,dev=dev,start_to_next_null_dequeue_ns=q['ns']-ns))
mapping={p:next(iter(c)) if len(c)==1 else None for p,c in pointer_directions.items()}
pairs=read(d/'timer-check.json')['pairs'];first=min(e['ns'] for e in events if e['kind']=='net_dev_queue' and fields(e['text']).get('dev')=='to_server')
for p in pairs:
 s=starts[(p['timer'],p['start_ns'])];e=callbacks[(p['timer'],p['callback_ns'])]
 p.update(dev=mapping.get(p['timer']),start_cpu=s['cpu'],callback_cpu=e['cpu'],sender_cpus_at_start=s['sender_active_cpus'],sender_cpus_at_callback=e['sender_active_cpus'],second=(p['callback_ns']-first)//10**9)
def quantiles(values):
 v=sorted(values);n=len(v)
 return dict(n=n,median=statistics.median(v),p95=v[int((n-1)*.95)],p99=v[int((n-1)*.99)],max=max(v),min=min(v)) if v else None
summary={}
for dev in ('to_server','to_browser',None):
 ps=[p for p in pairs if p['dev']==dev]
 if ps:summary[str(dev)]=dict(callback_lateness_ms=quantiles([p['callback_lateness_ns']/1e6 for p in ps]),sampled_now_lateness_ms=quantiles([p['timer_now_lateness_ns']/1e6 for p in ps]),callback_minus_sampled_now_ms=quantiles([p['callback_minus_sampled_now_ns']/1e6 for p in ps]),start_cpus=dict(Counter(p['start_cpu'] for p in ps)),callback_cpus=dict(Counter(p['callback_cpu'] for p in ps)),callback_on_sender_active_cpu=sum(p['callback_cpu'] in p['sender_cpus_at_callback'] for p in ps),one_second=[dict(second=i,**quantiles([p['callback_lateness_ns']/1e6 for p in ps if p['second']==i])) for i in range(101) if any(p['second']==i for p in ps)])
result=dict(timer_mapping=mapping,association_counts={p:dict(c) for p,c in pointer_directions.items()},queue_identity={str(k):v for k,v in queue_identity.items()},directions=summary,largest_callbacks=sorted(pairs,key=lambda p:p['callback_lateness_ns'],reverse=True)[:30],elapsed_s=time.monotonic()-started,limitations=['Direction inferred from same-CPU start then next null qdisc dequeue; inconsistent associations remain unknown','No per-skb programmedtime_to_send; callback pairing is per timer, not one callback per packet','No cancels or host scheduler; sender-active state does not establish global CPU availability'])
out.mkdir();(out/'timers.json').write_text(json.dumps(result,indent=2)+'\n');(out/'pairs.json').write_text(json.dumps(pairs)+'\n');(out/'associations.json').write_text(json.dumps(associations)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('directions','largest_callbacks')},indent=2));print({k:{n:v for n,v in r.items() if n!='one_second'} for k,r in summary.items()})
