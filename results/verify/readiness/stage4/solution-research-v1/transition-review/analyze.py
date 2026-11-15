import json,struct,statistics,signal,time,hashlib
from pathlib import Path
signal.alarm(90);start=time.monotonic();run=Path('results/verify/diagnostic/calibration.gIdWLx7o');out=Path('results/verify/readiness/stage4/solution-research-v1/transition-review')
def cap(path):
 b=path.read_bytes();pos=24;E='<' if b[:4]==b'\xd4\xc3\xb2\xa1' else '>';o={}
 while pos<len(b):
  s,u,n,l=struct.unpack_from(E+'IIII',b,pos);pos+=16;f=b[pos:pos+n];pos+=n
  if f[12:14]!=b'\x08\x00' or f[23]!=17:continue
  ip=f[14:];udp=ip[(ip[0]&15)*4:];i=int.from_bytes(udp[8:12],'big');assert i not in o;o[i]=s*1000000+u
 return o
med=statistics.median
quant=lambda a:[sorted(a)[round((len(a)-1)*p)] for p in (0,.05,.25,.5,.75,.95,1)]
rows=[]
for d in sorted(run.iterdir()):
 if not d.is_dir() or d.name.startswith('saturation'):continue
 p=json.loads((d/'probe.json').read_text());F=cap(d/'browser.pcap');R=cap(d/'server.pcap');S={r['id']:r['t_send_ms'] for r in p['sent_records']};RT={r['id']:r['rtt_ms'] for r in p['reply_records']};span={i:(R[i]-F[i])/1000 for i in RT};res={i:RT[i]-span[i] for i in RT};offset={i:(F[i]-F[0])/1000-(S[i]-S[0]) for i in F}
 windows=[]
 for first in range(0,10000,500):
  ids=[i for i in range(first,first+500) if i in RT];windows.append(dict(first_s=first/100,rtt=med([RT[i] for i in ids]),span=med([span[i] for i in ids]),remaining=med([res[i] for i in ids]),span_quantiles=quant([span[i] for i in ids]),offset=med([offset[i] for i in range(first,first+500)]),max_sender_lag=max(S[i]-i*10 for i in range(first,first+500))))
 row=dict(label=d.name,windows=windows,span_quantiles=quant(list(span.values())),remaining_quantiles=quant(list(res.values())),forward_gap_quantiles=quant([(F[i]-F[i-1])/1000 for i in range(1,10000)]),inputs=[dict(path=str(d/n),sha256=hashlib.sha256((d/n).read_bytes()).hexdigest()) for n in ['probe.json','browser.pcap','server.pcap']]);rows.append(row)
 print(d.name,[(w['first_s'],round(w['rtt'],3),round(w['span'],3),round(w['remaining'],3)) for w in windows])
result=dict(run=str(run),scope='Exploratory decomposition only; no correction or gate thresholds',quantile_probabilities=[0,.05,.25,.5,.75,.95,1],results=rows,elapsed_s=time.monotonic()-start);(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');print('elapsed_s',result['elapsed_s'])
