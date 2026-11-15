import hashlib,json,struct
from pathlib import Path
import numpy as np

root=Path('results/verify/diagnostic/profile-validation.73PKohD7');out=Path('results/verify/readiness/stage4/deep-review-v1/dependence/profile-validation-breakdown')
source=Path('results/verify/readiness/stage4/deep-review-v1/dependence/analyze.py').read_text();ns=dict(np=np,struct=struct,LAGS=(500,1000,2000));exec(source[source.index('def capture('):source.index('started = ')],ns);capture=ns['capture'];correlations=ns['correlations']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();seal=json.loads((root/'captured.json').read_text());assert all(sha(r['path'])==r['sha256'] for r in seal)
results=[]
for label in ('r20p0-check','r80p1-check'):
 d=root/label;p=json.loads((d/'probe.json').read_text());replies={r['id']:r['rtt_ms'] for r in p['reply_records']};fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap')
 send=np.array([r['t_send_ms'] for r in p['sent_records']]);lag=send-np.arange(10000)*10
 assert set(fw)==set(range(10000));assert set(replies)<=set(rv)<=set(fw)
 rtt=np.full(10000,np.nan);network=np.full(10000,np.nan)
 for i,v in replies.items():rtt[i]=v;network[i]=(rv[i]-fw[i])/1000
 residual=rtt-network
 chunks=[]
 for first in range(0,10000,500):
  last=first+500;idx=np.arange(first,last);observed=idx[np.isfinite(rtt[first:last])]
  row=dict(start_s=first/100,end_s=last/100,replies=len(observed),forward_loss=len(set(map(int,idx))-set(rv)),reverse_loss=len((set(map(int,idx))&set(rv))-set(replies)),max_send_lag_ms=float(np.max(lag[first:last])),components={})
  for name,v in [('rtt',rtt),('network_span',network),('remaining_rtt',residual)]:
   a=v[first:last];row['components'][name]=dict(median=float(np.nanmedian(a)),p95=float(np.nanquantile(a,.95)),p99=float(np.nanquantile(a,.99)))
  chunks.append(row)
 components={}
 for name,v in [('rtt',rtt),('network_span',network),('remaining_rtt',residual)]:
  filled=np.where(np.isfinite(v),v,np.nanmedian(v));components[name]=dict(correlation=correlations(filled).tolist(),all_quantiles=np.nanquantile(v,[.5,.95,.99]).tolist())
 receive=[(send[i]+v,i) for i,v in replies.items()];ordered=sorted(receive)
 reordered=sum(b[1]<a[1] for a,b in zip(ordered,ordered[1:]));recv_times=np.array([r[0] for r in ordered]);receivegaps=np.diff(recv_times)
 capture_latencies=np.array([(fw[i]-fw[0])/1000-(send[i]-send[0]) for i in range(10000)])
 qdisc={}
 for dev in ('to_server','to_browser'):
  a,b=[next(q for q in json.loads((d/f'qdisc-{phase}.json').read_text()) if q['kind']=='netem' and q['dev']==dev) for phase in ('before','after')]
  qdisc[dev]=dict(options_before=a['options'],options_after=b['options'],delta={k:b[k]-a[k] for k in ('packets','bytes','drops')},boundary_queues=[a['qlen'],a['backlog'],b['qlen'],b['backlog']])
 results.append(dict(name=label,replies=len(replies),components=components,chunks=chunks,reordered_replies=reordered,receivegap_ms_quantiles=np.quantile(receivegaps,[.5,.95,.99,1]).tolist(),sender_timestamp_to_forward_relative_offset_ms=dict(min=float(capture_latencies.min()),max=float(capture_latencies.max()),chunk_medians=np.median(capture_latencies.reshape(20,500),axis=1).tolist()),qdisc=qdisc,inputs=[dict(path=str(d/n),sha256=sha(d/n)) for n in ('probe.json','browser.pcap','server.pcap','qdisc-before.json','qdisc-after.json')]))
result=dict(run=str(root),sealed_files=len(seal),scope='Read-only decomposition of fixed two-profile diagnostic',results=results,limitations=['No continuous qdisc/CPU sampler: cannot prove absence of transient backlog or identify exact scheduler/host mechanism','Router-span combines forwardnetem/serverprocessing/replyingress, remainingRTT reverseqdisc/clientreceive plus initialsendtocapture offset','Chunkandcorrelationdecompositions are diagnostic; no primaryRTT adjustment or threshold change','The r80p1transient is observed under newpoll0; successful sender timing does not imply stationary RTT process'])
with (out/'analysis.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for r in results:
 print(r['name'],'components',r['components'],'reordered',r['reordered_replies'],'recvgaps',r['receivegap_ms_quantiles'])
 for c in r['chunks']:print(c['start_s'],c['end_s'],{k:round(v['median'],6) for k,v in c['components'].items()},c['replies'],c['forward_loss'],c['reverse_loss'],c['max_send_lag_ms'])
 print('offset',r['sender_timestamp_to_forward_relative_offset_ms'])
