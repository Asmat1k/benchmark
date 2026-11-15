import json,re,struct,statistics,time
from pathlib import Path
start=time.monotonic();run=Path('results/verify/diagnostic/transition-trace.jNq2hqdS');d=run/'r80p1-check';p=json.loads((d/'probe.json').read_text());s=json.loads((d/'server-records.json').read_text());tid=json.loads((d/'target.json').read_text())['host_tid'];trace=(d/'trace.txt').read_text();events=[]
for line in trace.splitlines():
 m=re.search(r'\[(\d+)\].*? (\d+\.\d+): (\w+): (.*)',line)
 if m:events.append((int(m[2].replace('.','')),m[3],m[4]))
events.sort()
def field(v,k):return re.search(r'(?:^|\s)'+k+r'=(\S+)',v)[1]
q=[t for t,k,v in events if k=='net_dev_queue' and field(v,'dev')=='to_server' and field(v,'len')=='298'];x=[t for t,k,v in events if k=='net_dev_start_xmit' and field(v,'dev')=='to_server' and field(v,'len')=='298'];assert len(q)==10000 and len(x)==len(s)
def cap(f):
 b=f.read_bytes();pos=24;o={};en='<' if b[:4]==b'\xd4\xc3\xb2\xa1' else '>'
 while pos<len(b):
  sec,us,n,l=struct.unpack_from(en+'IIII',b,pos);pos+=16;frame=b[pos:pos+n];pos+=n
  if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
  ip=frame[14:];udp=ip[(ip[0]&15)*4:];o[int.from_bytes(udp[8:12],'big')]=sec*1000000+us
 return o
fw=cap(d/'browser.pcap');rv=cap(d/'server.pcap');rtt={r['id']:r['rtt_ms'] for r in p['reply_records']};rows=[]
for r,t in zip(s,x):
 i=r['id'];rows.append(dict(id=i,q=(t-q[i])/1000,post=(r['received_ns']/1000-t)/1000,user=(r['before_send_ns']-r['received_ns'])/1e6,send=(r['after_send_ns']-r['before_send_ns'])/1e6,span=(rv[i]-fw[i])/1000,rtt=rtt.get(i)))
med=lambda a:statistics.median(a)
windows=[]
for lo in range(0,10000,100):
 ss=[r for r in rows if lo<=r['id']<lo+100];windows.append(dict(second=lo//100,**{k:med([r[k] for r in ss if r[k] is not None]) for k in ('q','post','user','send','span','rtt')}))
wake=None;wake_pairs=[];off=None;offpairs=[]
for t,k,v in events:
 if k=='sched_wakeup' and re.search(r'\bpid='+str(tid)+r'\b',v):wake=t
 if k=='sched_switch':
  if re.search(r'\bnext_pid='+str(tid)+r'\b',v):
   if wake is not None:wake_pairs.append((t-wake,wake,t));wake=None
   if off:offpairs.append((t-off[0],off[0],t,off[1]));off=None
  if re.search(r'\bprev_pid='+str(tid)+r'\b',v):off=(t,field(v,'prev_state'))
result=dict(one_second_ranges={k:(min(r[k] for r in windows),max(r[k] for r in windows)) for k in ('q','post','user','send','span','rtt')},highest_span_seconds=sorted(windows,key=lambda r:r['span'],reverse=True)[:10],seconds42to48=windows[42:49],wake_pairs=len(wake_pairs),wake_median_us=med([r[0] for r in wake_pairs]),wake_top10=sorted(wake_pairs,reverse=True)[:10],offcpu_top10=sorted(offpairs,reverse=True)[:10],component_maxima={k:max((r[k],r['id']) for r in rows if r[k] is not None) for k in ('q','post','user','send','span','rtt')},elapsed_s=time.monotonic()-start)
print(json.dumps(result,indent=2))
