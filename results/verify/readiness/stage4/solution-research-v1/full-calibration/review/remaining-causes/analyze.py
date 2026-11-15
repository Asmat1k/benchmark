import datetime
import hashlib
import json
from pathlib import Path
import signal
import statistics
import struct
import time

signal.alarm(90)
started=time.monotonic()
run=Path('results/verify/diagnostic/calibration.ew2u0ceD')
out=Path(__file__).parent
manifest={r['path']:r['sha256'] for r in json.loads((run/'captured.json').read_text())}
def read(p):return json.loads(p.read_text())
def capture(path):
    data=path.read_bytes();assert data[:4] in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4')
    endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>'
    offset=24;rows={}
    while offset<len(data):
        sec,usec,length,wire=struct.unpack_from(endian+'IIII',data,offset);offset+=16
        frame=data[offset:offset+length];offset+=length
        if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
        ip=frame[14:];udp=ip[(ip[0]&15)*4:];identity=int.from_bytes(udp[8:12],'big')
        assert identity not in rows;rows[identity]=sec*10**6+usec
    return rows
def load(name):
    directory=run/name
    for filename in ('probe.json','browser.pcap','server.pcap','browser.log','server.log'):
        p=directory/filename;assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest[str(p)]
    probe=read(directory/'probe.json')
    return probe,capture(directory/'browser.pcap'),capture(directory/'server.pcap')

probe,fw,rv=load('r20p1-before')
sent=probe['sent_records'];replies={r['id']:r['rtt_ms'] for r in probe['reply_records']}
worst=max(sent,key=lambda r:r['t_send_ms']-r['t_plan_ms']);identity=worst['id'];anchor=fw[identity-1]
timeline=[]
for i in range(identity-10,identity+15):
    send=sent[i]['t_send_ms'];rtt=replies.get(i)
    span=(rv[i]-fw[i])/1000 if i in rv else None
    timeline.append(dict(id=i,lag_ms=send-sent[i]['t_plan_ms'],send_monotonic_relative_ms=send,
                         forward_epoch_relative_ms=(fw[i]-anchor)/1000,
                         reverse_epoch_relative_ms=(rv[i]-anchor)/1000 if i in rv else None,
                         rtt_ms=rtt,receive_monotonic_relative_ms=send+rtt if rtt is not None else None,
                         router_span_ms=span,residual_ms=rtt-span if rtt is not None and span is not None else None))
union=sorted([(timestamp,'forward',i) for i,timestamp in fw.items()]+[(timestamp,'reverse',i) for i,timestamp in rv.items()])
quiet=[dict(gap_ms=(b[0]-a[0])/1000,before=dict(epoch_us=a[0],direction=a[1],id=a[2]),after=dict(epoch_us=b[0],direction=b[1],id=b[2]))
       for a,b in zip(union,union[1:]) if anchor<=a[0]<fw[identity]]
pause=dict(worst_id=identity,worst_lag_ms=worst['t_send_ms']-worst['t_plan_ms'],
           sender_gap_ms=sent[identity]['t_send_ms']-sent[identity-1]['t_send_ms'],
           forward_capture_gap_ms=(fw[identity]-fw[identity-1])/1000,
           quiet_intervals=quiet,timeline=timeline)

probe,fw,rv=load('r80p1-latency')
replies={r['id']:r['rtt_ms'] for r in probe['reply_records']}
rows=[dict(id=i,rtt_ms=rtt,span_ms=(rv[i]-fw[i])/1000,residual_ms=rtt-(rv[i]-fw[i])/1000,
           lag_ms=probe['sent_records'][i]['t_send_ms']-probe['sent_records'][i]['t_plan_ms']) for i,rtt in replies.items()]
def summarize(selected):
    return dict(n=len(selected),**{key:statistics.median(r[key] for r in selected) for key in ('rtt_ms','span_ms','residual_ms','lag_ms')},max_lag_ms=max(r['lag_ms'] for r in selected))
windows=[dict(second=i,**summarize([r for r in rows if i*100<=r['id']<(i+1)*100])) for i in range(100)]
result=dict(pause=pause,residual_step=dict(one_second=windows,
                                        first_35_seconds=summarize([r for r in rows if r['id']<3500]),
                                        last_60_seconds=summarize([r for r in rows if r['id']>=4000])),
            sealed_input_checks=10,elapsed_s=time.monotonic()-started,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            limitations=['pcap epoch and sender monotonic are separate clocks; no absolute conversion or RTT correction',
                         'both pcap are ingress, no reverse dequeue or receiver kernel timestamp',
                         'no scheduler/syscall/softirq/watchdog trace in this full collection'])
(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({**{k:v for k,v in pause.items() if k!='timeline'},'residual_step_blocks':{k:v for k,v in result['residual_step'].items() if k!='one_second'},'elapsed_s':result['elapsed_s']},indent=2))
