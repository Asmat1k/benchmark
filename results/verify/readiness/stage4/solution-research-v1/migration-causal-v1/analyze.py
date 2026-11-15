from bisect import bisect_right
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time
import numpy as np

sys.path[:0]=['docker','src/analysis']
from calibration_probe import collection_tag
from calibration_report import directions
from calibration_blocks import process_diagnostics
from sender_quality import evaluate

started=time.monotonic()
run=Path(sys.argv[1]);out=Path(sys.argv[2]);d=run/sys.argv[3]
read=lambda p:json.loads(p.read_text())
seal=read(run/'captured.json');assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in seal)
assert (run/'exit').read_text().strip()=='0'
p=read(d/'probe.json');server=read(d/'server-records.json');assert read(d/'trace-check.json')['status']=='passed'
flows=directions(d,p)
assert [r['id'] for r in server]==sorted(flows[1]['entered_ids'])
assert all(r['tag']==collection_tag(p['collection_id']).hex() for r in server)
events=[]
for line in (d/'trace.txt').read_text().splitlines():
    m=re.search(r'\[(\d+)\].*? (\d+\.\d+): (\w+): (.*)',line)
    if m:events.append((round(float(m[2])*1e9),m[3],m[4],int(m[1])))
events.sort(key=lambda r:r[0])
field=lambda text,key:re.search(r'(?:^|\s)'+key+r'=(\S+)',text)[1]
queues=[e for e in events if e[1]=='net_dev_queue' and field(e[2],'dev')=='to_server' and field(e[2],'len')=='298']
xmits=[e for e in events if e[1]=='net_dev_start_xmit' and field(e[2],'dev')=='to_server' and field(e[2],'len')=='298']
assert len(queues)==10000,len(queues)
assert len(xmits)==len(server),(len(xmits),len(server))
assert [r['id'] for r in server]==sorted(r['id'] for r in server)
queue_by_id=dict(enumerate(queues));forward=[]
ptrqueues=defaultdict(list);dequeues=defaultdict(list);enqueues=defaultdict(list)
for e in events:
    if e[1]=='net_dev_queue':ptrqueues[field(e[2],'skbaddr')].append(e[0])
    if e[1]=='qdisc_dequeue' and field(e[2],'packets')!='0':dequeues[field(e[2],'skbaddr')].append(e)
    if e[1]=='qdisc_enqueue':enqueues[field(e[2],'skbaddr')].append(e)

first_enqueue=enqueues[field(xmits[0][2],'skbaddr')]
first_enqueue=next(e for e in first_enqueue if queues[0][0]<=e[0]<=xmits[0][0])
forward_index=field(first_enqueue[2],'ifindex');forward_handle=field(first_enqueue[2],'handle')
active={};batch_by_xmit={}
for e in events:
    if e[1]=='qdisc_dequeue' and field(e[2],'ifindex')==forward_index and field(e[2],'handle')==forward_handle and field(e[2],'packets')!='0':
        assert e[3] not in active or active[e[3]][1]==0
        active[e[3]]=[e,int(field(e[2],'packets')),True]
    if e[1]=='net_dev_start_xmit' and field(e[2],'dev')=='to_server' and field(e[2],'len')=='298':
        batch=active[e[3]];assert batch[1]>0
        if batch[2]:assert field(batch[0][2],'skbaddr')==field(e[2],'skbaddr')
        batch_by_xmit[(e[0],field(e[2],'skbaddr'))]=batch[0]
        batch[1]-=1;batch[2]=False
assert all(b[1]==0 for b in active.values())
for r,x in zip(server,xmits):
    q=queue_by_id[r['id']]
    assert field(q[2],'skbaddr')==field(x[2],'skbaddr'),(r['id'],q,x)
    assert q[0]<=x[0]<=r['received_ns']+2000
    ptr=field(x[2],'skbaddr')
    assert bisect_right(ptrqueues[ptr],x[0])-bisect_right(ptrqueues[ptr],q[0])==0
    deq=[batch_by_xmit[(x[0],ptr)]]
    assert q[0]<=deq[0][0]<=x[0]
    enq=[e for e in enqueues[ptr] if q[0]<=e[0]<=x[0]]
    assert len(deq)==1 and len(enq)==1,(r['id'],deq,enq)
    assert field(deq[0][2],'ifindex')==field(enq[0][2],'ifindex')
    assert field(deq[0][2],'handle')==field(enq[0][2],'handle')
    forward.append(dict(id=r['id'],queue_ns=q[0],xmit_ns=x[0],queue_to_xmit_ms=(x[0]-q[0])/1e6,xmit_to_received_ms=(r['received_ns']-x[0])/1e6,server_received_to_send_ms=(r['before_send_ns']-r['received_ns'])/1e6,server_send_ms=(r['after_send_ns']-r['before_send_ns'])/1e6,skb=field(x[2],'skbaddr'),qdisc_ifindex=field(deq[0][2],'ifindex'),qdisc_handle=field(deq[0][2],'handle'),dequeue_to_xmit_ms=(x[0]-deq[0][0])/1e6))
rows={r['id']:r for r in forward}
rt={r['id']:r['rtt_ms'] for r in p['reply_records']}
def capture(path):
    data=path.read_bytes();endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24;result={}
    while pos<len(data):
        sec,usec,n,length=struct.unpack_from(endian+'IIII',data,pos);pos+=16;frame=data[pos:pos+n];pos+=n
        if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
        ip=frame[14:];udp=ip[(ip[0]&15)*4:];i=int.from_bytes(udp[8:12],'big');assert i not in result;result[i]=sec*1000000+usec
    return result
fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap')
for i,r in rows.items():r['router_span_ms']=(rv[i]-fw[i])/1000
for i,v in rt.items():rows[i]['rtt_ms']=v
metrics=['queue_to_xmit_ms','xmit_to_received_ms','server_received_to_send_ms','server_send_ms','router_span_ms','rtt_ms']
def summary(subset):
    return {k:dict(zip(['median','p95','p99','max'],map(float,np.quantile([r[k] for r in subset if k in r],[.5,.95,.99,1])))) for k in metrics}
windows={str(step):[dict(start_s=first/100,end_s=(first+step)/100,count=sum(first<=r['id']<first+step for r in forward),metrics=summary([r for r in forward if first<=r['id']<first+step])) for first in range(0,10000,step)] for step in (100,500)}
values=np.full(10000,np.nan)
for i,v in rt.items():values[i]=v
quality=evaluate(p['sent_records'],10000)
result=dict(scope='one instrumented causal diagnostic, no calibration gate',run=str(run),sealed_files=len(seal),sender=quality,process=process_diagnostics(values),all=summary(forward),windows=windows,mapping=dict(forward_queues=len(queues),forward_xmits=len(xmits),server_records=len(server),same_skb_per_id=True,server_id_order=True),loss=[dict(direction=f['direction'],entered=len(f['entered_ids']),dropped=len(f['dropped_ids'])) for f in flows],elapsed_s=time.monotonic()-started)
out.mkdir();(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');(out/'per-id.json').write_text(json.dumps(forward)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('windows','sender')},indent=2));print('sender',quality)
