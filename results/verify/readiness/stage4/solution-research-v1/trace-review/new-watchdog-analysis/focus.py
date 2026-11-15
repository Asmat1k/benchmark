import json
from pathlib import Path
import re
import signal
import statistics

signal.alarm(90)
root=Path('results/verify/diagnostic/watchdog-trace.zk2E5PYS/r80p1-check')
out=Path(__file__).parent
read=lambda n:json.loads((root/n).read_text())
events=[]
for line in (root/'trace.txt').read_text().splitlines():
    m=re.search(r'\[(\d+)\].*? (\d+)\.(\d+): (\w+): (.*)',line)
    if m:
        cpu,sec,frac,kind,payload=m.groups()
        events.append((int(sec)*10**9+int(frac.ljust(9,'0')),int(cpu),kind,dict(re.findall(r'(\w+)=(\S+)',payload))))
first=next(ns for ns,c,k,f in events if k=='net_dev_queue' and f['dev']=='to_server')
following={};anchors=[]
for ns,c,k,f in reversed(events):
    if k=='qdisc_dequeue':following[c]=(ns,f)
    if k=='hrtimer_start' and c in following:
        qns,q=following[c]
        if q['packets']=='0':anchors.append(dict(start_ns=ns,cpu=c,timer=f['hrtimer'],following_dequeue_ns=qns,fields=q))
anchors.sort(key=lambda r:r['start_ns'])
pairs=read('timer-check.json')['pairs']
probe=read('probe.json');rows=[]
for i in range(21,30):
    ps=[p for p in pairs if i*10**9<=p['callback_ns']-first<(i+1)*10**9]
    lag=[r['t_send_ms']-r['t_plan_ms'] for r in probe['sent_records'] if i*1000<=r['t_plan_ms']<(i+1)*1000]
    row=dict(second=i,sender_lag_max_ms=max(lag),sender_lag_median_ms=statistics.median(lag),timers={})
    for pointer in sorted({p['timer'] for p in ps}):
        these=[p for p in ps if p['timer']==pointer]
        row['timers'][pointer]=dict(n=len(these),callback_lateness_median_ms=statistics.median(p['callback_lateness_ns'] for p in these)/1e6,
                                      sampled_now_lateness_median_ms=statistics.median(p['timer_now_lateness_ns'] for p in these)/1e6,
                                      callback_minus_now_median_us=statistics.median(p['callback_minus_sampled_now_ns'] for p in these)/1e3)
    for kind in ('net_dev_queue','net_dev_start_xmit'):
        row[kind]={}
        for dev in ('to_server','to_browser'):
            row[kind][dev]={str(cpu):sum(1 for ns,c,k,f in events if k==kind and f['dev']==dev and c==cpu and i*10**9<=ns-first<(i+1)*10**9) for cpu in (0,1)}
    rows.append(row)
(out/'focus.json').write_text(json.dumps(dict(null_anchors=anchors,windows=rows),indent=2)+'\n')
print(json.dumps(dict(null_anchors=anchors,central_windows=rows[3:6]),indent=2))
