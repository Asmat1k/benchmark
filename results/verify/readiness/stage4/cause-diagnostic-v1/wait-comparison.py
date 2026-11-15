import json
from pathlib import Path
import random
import select
import time

output=Path('results/verify/readiness/stage4/cause-diagnostic-v1/wait-comparison.json')
assert not output.exists()
policies=['select','poll-1ms','hybrid-500us']
order=[p for _ in range(10) for p in random.Random(20261113+_).sample(policies,3)]
results={p:dict(lag_ns=[],cpu_ns=0,elapsed_ns=0,calls=0) for p in policies}
for policy in order:
 record=results[policy];start=time.monotonic_ns();cpu=time.process_time_ns();previous=start
 for i in range(100):
  due=max(start+(i+1)*10000000,previous+2500000)
  while (remaining:=due-time.monotonic_ns())>0:
   if policy=='hybrid-500us' and remaining<=500000:
    continue
   timeout=remaining/1e9
   if policy=='poll-1ms':timeout=min(timeout,.001)
   if policy=='hybrid-500us':timeout=(remaining-500000)/1e9
   select.select([],[],[],timeout);record['calls']+=1
  previous=time.monotonic_ns();record['lag_ns'].append(previous-due)
 record['elapsed_ns']+=time.monotonic_ns()-start;record['cpu_ns']+=time.process_time_ns()-cpu
for p,r in results.items():
 values=sorted(r['lag_ns']);r['summary']=dict(n=len(values),median_ms=values[len(values)//2]/1e6,p99_ms=values[989]/1e6,max_ms=max(values)/1e6,cpu_core_pct=100*r['cpu_ns']/r['elapsed_ns'])
result=dict(diagnostic_only=True,design='30 prespecified interleaved1second blocks;1000ticks per policy; no network, real guest monotonic/select; no qualification claim',order=order,results=results,limitations=['No packet/receive path','Rare-tail reliability cannot be established from1000ticks','Serial policies may carry different transient VM conditions; descriptive comparison only'])
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({p:r['summary'] for p,r in results.items()},indent=2))
