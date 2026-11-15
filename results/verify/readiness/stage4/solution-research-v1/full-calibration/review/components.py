import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import numpy as np
sys.path[:0]=['docker','src/analysis']
from browser_bandwidth import load_rates,fractions
from calibration_report import rate
from admission import checked,sources

start=time.monotonic();base=Path('results/verify/readiness/stage4/solution-research-v1/full-calibration/review');run=Path('results/verify/diagnostic/calibration.ew2u0ceD')
def read(p):return json.loads(p.read_text())
def capture(p):
 b=p.read_bytes();pos=24;endian='<' if b[:4]==b'\xd4\xc3\xb2\xa1' else '>';result={}
 while pos<len(b):
  sec,us,n,_=struct.unpack_from(endian+'IIII',b,pos);pos+=16;frame=b[pos:pos+n];pos+=n
  if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
  ip=frame[14:];udp=ip[(ip[0]&15)*4:];i=int.from_bytes(udp[8:12],'big');assert i not in result;result[i]=sec*1000000+us
 return result
rows=[]
for item in read(run/'collection-plan.json')['collections'][:14]:
 d=run/item['name'];p=read(d/'probe.json');fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap');rtts={r['id']:r['rtt_ms'] for r in p['reply_records']}
 assert set(fw)==set(range(10000)) and set(rtts)<=set(rv)<=set(fw)
 data=[dict(id=i,rtt_ms=rtt,span_ms=(rv[i]-fw[i])/1000,residual_ms=rtt-(rv[i]-fw[i])/1000) for i,rtt in rtts.items()]
 windows=[]
 for first in range(0,10000,500):
  chunk=[r for r in data if first<=r['id']<first+500]
  windows.append(dict(start_s=first/100,**{k:float(np.median([r[k] for r in chunk])) for k in ('rtt_ms','span_ms','residual_ms')}))
 rows.append(dict(name=item['name'],windows=windows))
review=read(Path('results/verify/readiness/stage4/release-v4/browser-bandwidth-v4-raw-review.json'))
for r in review['evidence']+[review['environment']]:checked(r)
old=review['source_hashes'];current=sources();delta={p for p in old if old[p]!=current[p]};assert set(old)==set(current) and delta=={'docker/calibration_probe.py','docker/calibration_probe_test.py'}
bw=Path(review['BW_RUN']);assert read(bw/'context.json')==read(run/'context-before.json')==read(run/'context-after.json')
schedule=read(bw/'schedule.json');loads=[dict(mode=r['mode'],rates=load_rates(bw/'raw'/r['run_id'])) for r in schedule['runs']]
capacity=[rate(run/f'saturation-{loss}-{direction}',direction,loss/100) for loss in (0,1) for direction in ('forward','reverse')]
result=dict(scope='Historical validated browser byte counts with new capacity; applicability comparison, not new source-bound generator/bandwidth gate',historical_BW_RUN=str(bw),current_CAL_RUN=str(run),source_delta=sorted(delta),reason='Only auxiliary UDP calibration sender and its test changed; browser source, measurement collector and byte counters unchanged. Historical raw/review retain original hashes.',**fractions(loads,capacity))
(base/'bandwidth-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
(base/'components.json').write_text(json.dumps(dict(series=rows,elapsed_s=time.monotonic()-start),indent=2)+'\n')
print(json.dumps(result,indent=2));print('component data',base/'components.json','elapsed',time.monotonic()-start)
