import json
from pathlib import Path
import struct
import numpy as np

source=Path('results/verify/readiness/stage4/deep-review-v1/dependence/analyze.py').read_text()
ns=dict(np=np,struct=struct,LAGS=(500,1000,2000))
exec(source[source.index('def capture('):source.index('started = ')],ns)
capture=ns['capture']
root=Path('results/verify/diagnostic/calibration.lShojabe')
results=[]
for d in sorted(root.iterdir()):
 if not (d/'browser.pcap').exists():continue
 p=json.loads((d/'probe.json').read_text());replies={r['id']:r['rtt_ms'] for r in p['reply_records']}
 fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap')
 all_ids=np.array(sorted(replies));times=np.array([fw[int(i)] for i in all_ids]);rtt=np.array([replies[int(i)] for i in all_ids]);network=np.array([(rv[int(i)]-fw[int(i)])/1000 for i in all_ids]);residual=rtt-network
 bins=(times%1000000//10000).astype(int)
 rows={}
 for name,v in [('rtt',rtt),('router_round_span',network),('remaining',residual)]:
  medians=[float(np.median(v[bins==b])) if np.any(bins==b) else None for b in range(100)]
  counts=[int(np.sum(bins==b)) for b in range(100)]
  peaks=np.argsort([m if m is not None else -1 for m in medians])[-5:][::-1]
  rows[name]=dict(medians_ms=medians,counts=counts,largest_phase_bins=[dict(epoch_phase_ms=int(i)*10,median_ms=medians[int(i)]) for i in peaks])
 results.append(dict(name=d.name,first_forward_epoch_usec=fw[0],first_reverse_epoch_usec=rv.get(0),first_forward_epoch_phase_ms=fw[0]%1000000/1000,components=rows))
out=Path('results/verify/readiness/stage4/deep-review-v1/dependence/absolute-phase.json')
with out.open('x') as f:json.dump(dict(bin_ms=10,period_ms=1000,results=results,limitations=['Pcap timestamps are packet kernel capture times, not tcpdump open/wakeup times','Actual capture start per process is not recorded, so timeout phase cannot be exactly reconstructed','Epoch phase changes across series support a changing process-aligned pattern but cannot identify the observer as the cause']),f,indent=2);f.write('\n')
for r in results:print(r['name'],'first_fw_phase',r['first_forward_epoch_phase_ms'],'RTT peaks',r['components']['rtt']['largest_phase_bins'][:3],'networkpeaks',r['components']['router_round_span']['largest_phase_bins'][:3])
