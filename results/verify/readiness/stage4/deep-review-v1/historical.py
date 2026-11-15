import hashlib,json,struct
from pathlib import Path
import numpy as np

run=Path('results/verify/diagnostic/calibration.lShojabe');out=Path('results/verify/readiness/stage4/deep-review-v1')
def capture(path):
 data=path.read_bytes();endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24;packets={}
 while pos<len(data):
  sec,usec,n,wire=struct.unpack_from(endian+'IIII',data,pos);pos+=16;f=data[pos:pos+n];pos+=n
  if f[12:14]!=b'\x08\x00' or f[23]!=17:continue
  ip=f[14:];udp=ip[(ip[0]&15)*4:];i=int.from_bytes(udp[8:12],'big');packets[i]=sec*1000000+usec
 return packets
results=[]
for d in sorted(run.iterdir()):
 if not (d/'probe.json').exists() or d.name.startswith('saturation'):continue
 p=json.loads((d/'probe.json').read_text());send=np.array([s['t_send_ms'] for s in p['sent_records']]);lag=send-np.arange(10000)*10
 rtt={r['id']:r['rtt_ms'] for r in p['reply_records']};fw,rv=capture(d/'browser.pcap'),capture(d/'server.pcap')
 values=np.full(10000,np.nan)
 for i,v in rtt.items():values[i]=v
 rows=[]
 for i in np.argsort(lag)[-3:][::-1]:
  i=int(i);rows.append(dict(id=i,lag_ms=float(lag[i]),send_gap_ms=float(send[i]-send[i-1]),ingress_gap_ms=(fw[i]-fw[i-1])/1000,previous_rtt_ms=rtt.get(i-1),after_previous_receive_ms=float(send[i]-send[i-1]-rtt[i-1]) if i-1 in rtt else None,rtt_ms=rtt.get(i),forward_reverse_ms=(rv[i]-fw[i])/1000 if i in rv else None))
 finite=np.isfinite(values);filled=np.where(finite,values,np.nanmedian(values));centered=filled-filled.mean();variance=centered@centered;correlations={};contributions={}
 for k in (500,1000,2000):
  terms=centered[:-k]*centered[k:];idx=np.argsort(np.abs(terms))[-10:][::-1]
  correlations[str(k)]=float(terms.sum()/variance)
  contributions[str(k)]=[dict(first=int(i),second=int(i+k),a=float(filled[i]),b=float(filled[i+k]),normalized_product=float(terms[i]/variance),lag_a=float(lag[i]),lag_b=float(lag[i+k])) for i in idx]
 tail=filled>np.quantile(filled,.99)
 burst_counts=[dict(index=int(i),rtt_ms=float(filled[i]),lag_ms=float(lag[i]),network_ms=(rv[i]-fw[i])/1000 if i in rv else None) for i in np.argsort(filled)[-10:][::-1]]
 results.append(dict(name=d.name,pause_details=rows,correlations=correlations,contributions=contributions,largest_rtts=burst_counts,median=float(np.nanmedian(values)),p95=float(np.nanquantile(values,.95)),p99=float(np.nanquantile(values,.99)),tail_modulo1000_counts=np.histogram(np.flatnonzero(tail)%1000,bins=np.arange(0,1001,100))[0].tolist(),input_sha256=hashlib.sha256((d/'probe.json').read_bytes()).hexdigest()))
with (out/'historical.json').open('x') as f:json.dump(results,f,indent=2);f.write('\n')
for r in results:
 if r['name'] in ('baseline-before','r20p0-latency','r20p0-after','r20p1-after'):
  print(r['name'],'pauses',r['pause_details'][:1]);print('corr',r['correlations']);print('1000 contributions',r['contributions']['1000'][:5]);print('largest rtt',r['largest_rtts'][:3])
