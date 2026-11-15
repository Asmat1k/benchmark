import json,struct,signal,time
from pathlib import Path
signal.alarm(90);start=time.monotonic();run=Path('results/verify/diagnostic/calibration.gIdWLx7o');out=Path('results/verify/readiness/stage4/solution-research-v1/transition-review')
def records(path):
 b=path.read_bytes();E='<' if b[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24;o=[]
 while pos<len(b):
  s,u,n,l=struct.unpack_from(E+'IIII',b,pos);pos+=16;f=b[pos:pos+n];pos+=n
  if f[12:14]!=b'\x08\x00' or f[23]!=17:continue
  ip=f[14:];udp=ip[(ip[0]&15)*4:];o.append(dict(record=len(o),id=int.from_bytes(udp[8:12],'big'),epoch_us=s*1000000+u,tag=udp[12:20].hex()))
 return o
rows=[]
for d in sorted(run.iterdir()):
 if not d.is_dir() or d.name.startswith('saturation'):continue
 p=json.loads((d/'probe.json').read_text());S={r['id']:r['t_send_ms'] for r in p['sent_records']};F=records(d/'browser.pcap');R=records(d/'server.pcap');fm={r['id']:r for r in F};rm={r['id']:r for r in R};neg=[]
 for role,seq in [('forward',F),('reverse',R)]:
  for a,b in zip(seq,seq[1:]):
   if b['epoch_us']<a['epoch_us']:
    id=b['id'];context=[]
    for i in range(max(0,id-3),min(10000,id+7)):
     f=fm[i];r=rm.get(i);context.append(dict(id=i,forward_record=f['record'],forward_epoch_us=f['epoch_us'],sender_ms=S[i],relative_offset_ms=(f['epoch_us']-F[0]['epoch_us'])/1000-(S[i]-S[0]),reverse_record=r['record'] if r else None,reverse_epoch_us=r['epoch_us'] if r else None,span_ms=(r['epoch_us']-f['epoch_us'])/1000 if r else None))
    neg.append(dict(role=role,before=a,after=b,delta_ms=(b['epoch_us']-a['epoch_us'])/1000,context=context))
 jumps=[]
 offsets=[(r['epoch_us']-F[0]['epoch_us'])/1000-(S[r['id']]-S[0]) for r in F]
 for i in range(1,len(F)):
  step=offsets[i]-offsets[i-1]
  if abs(step)>.5:jumps.append(dict(id=F[i]['id'],delta_ms=step,before=offsets[i-1],after=offsets[i]))
 rows.append(dict(label=d.name,forward_ids_record_order_strict=all(a['id']<b['id'] for a,b in zip(F,F[1:])),reverse_ids_record_order_strict=all(a['id']<b['id'] for a,b in zip(R,R[1:])),negative_epoch_steps=neg,offset_jumps_over_half_ms=jumps))
result=dict(scope='Exploratory packet timestamp discontinuity check; offset-step candidate threshold diagnostic only, no admission or correction',run=str(run),results=rows,elapsed_s=time.monotonic()-start);(out/'clock-analysis.json').write_text(json.dumps(result,indent=2)+'\n');print('elapsed_s',result['elapsed_s'])
for r in rows:
 print(r['label'],'negative_steps',[(x['role'],x['after']['id'],x['delta_ms']) for x in r['negative_epoch_steps']],'offsetjumps',r['offset_jumps_over_half_ms'])
