from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import datetime
import hashlib
import json
from pathlib import Path
import re
import signal
import statistics
import time

signal.alarm(90)
started = time.monotonic()
raw = Path('results/verify/diagnostic/watchdog-trace.zk2E5PYS/r80p1-check')
out = Path(__file__).parent
read = lambda name: json.loads((raw / name).read_text())
def stats(values):
    values = sorted(values)
    if not values:
        return None
    return dict(n=len(values), min=min(values), median=statistics.median(values),
                p99=values[int((len(values)-1)*.99)], max=max(values))

events = []
for line in (raw / 'trace.txt').read_text().splitlines():
    m = re.search(r'\[(\d+)\].*? (\d+)\.(\d+): (\w+): (.*)', line)
    if m:
        cpu, sec, frac, kind, payload = m.groups()
        events.append((int(sec)*10**9+int(frac.ljust(9, '0')), int(cpu), kind,
                       dict(re.findall(r'(\w+)=(\S+)', payload))))
events.sort(key=lambda e: e[0])
sender = read('sender-target.json')['host_tid']
active = set()
active_at = {}
queue = {}
identities = defaultdict(set)
dequeues = defaultdict(list)
starts, callbacks, residence = {}, {}, defaultdict(list)
switches = []
for ns, cpu, kind, f in events:
    if kind == 'sched_switch':
        if int(f['prev_pid']) == sender:
            active.discard(cpu)
            switches.append(dict(ns=ns, cpu=cpu, edge='out', state=f['prev_state']))
        if int(f['next_pid']) == sender:
            active.add(cpu)
            switches.append(dict(ns=ns, cpu=cpu, edge='in'))
    if kind == 'net_dev_queue':
        queue[f['skbaddr']] = (ns, cpu, f['dev'])
    if kind == 'qdisc_enqueue' and f['skbaddr'] in queue:
        queued_ns, queued_cpu, dev = queue[f['skbaddr']]
        if cpu == queued_cpu:
            identities[(f['ifindex'], f['handle'])].add(dev)
    if kind == 'qdisc_dequeue':
        dequeues[cpu].append((ns, f))
    if kind == 'net_dev_start_xmit' and f['skbaddr'] in queue:
        queued_ns, queued_cpu, dev = queue.pop(f['skbaddr'])
        if dev == f['dev']:
            residence[dev].append((queued_ns, ns, cpu, (ns-queued_ns)/1e6))
    if kind in ('hrtimer_start', 'hrtimer_expire_entry'):
        active_at[(kind, f['hrtimer'], ns)] = sorted(active)
        (starts if kind == 'hrtimer_start' else callbacks)[(f['hrtimer'], ns)] = (cpu, f)
assert all(len(v) == 1 for v in identities.values())
devs = {key: next(iter(value)) for key, value in identities.items()}
directions = defaultdict(Counter)
null_gaps, unmapped, following_classes = [], [], Counter()
times = {cpu: [r[0] for r in rows] for cpu, rows in dequeues.items()}
following = {}
for ns, cpu, kind, f in reversed(events):
    if kind == 'qdisc_dequeue':
        following[cpu] = (ns, f)
    if kind != 'hrtimer_start':
        continue
    pointer = f['hrtimer']
    if cpu in following:
        qns, q = following[cpu]
        dev = devs.get((q['ifindex'], q['handle']))
        if dev:
            directions[pointer][dev] += 1
            following_classes[q['packets']] += 1
            null_gaps.append(qns-ns)
            continue
    unmapped.append(dict(pointer=pointer, ns=ns, cpu=cpu))
mapping = {pointer: next(iter(counts)) if len(counts) == 1 else None
           for pointer, counts in directions.items()}
positives = defaultdict(list)
for cpu, rows in dequeues.items():
    for ns, f in rows:
        if int(f['packets']) > 0:
            positives[(cpu, devs.get((f['ifindex'], f['handle'])))].append(ns)
pairs = read('timer-check.json')['pairs']
for p in pairs:
    cpu, _ = callbacks[(p['timer'], p['callback_ns'])]
    start_cpu, _ = starts[(p['timer'], p['start_ns'])]
    dev = mapping.get(p['timer'])
    positive = positives[(cpu, dev)]
    i = bisect_left(positive, p['callback_ns'])
    p.update(cpu=cpu, start_cpu=start_cpu, dev=dev,
             sender_cpus=active_at[('hrtimer_expire_entry', p['timer'], p['callback_ns'])],
             callback_to_next_positive_dequeue_ms=(positive[i]-p['callback_ns'])/1e6 if i<len(positive) else None)
first = min(r[0] for r in residence['to_server'])
summary = {}
for dev in ('to_server', 'to_browser'):
    subset = [p for p in pairs if p['dev'] == dev]
    summary[dev] = dict(callback_lateness_ms=stats([p['callback_lateness_ns']/1e6 for p in subset]),
                        callback_to_next_positive_dequeue_ms=stats([p['callback_to_next_positive_dequeue_ms'] for p in subset if p['callback_to_next_positive_dequeue_ms'] is not None]),
                        queue_to_xmit_ms=stats([r[3] for r in residence[dev]]),
                        callback_cpus=dict(Counter(p['cpu'] for p in subset)),
                        callbacks_on_sender_cpu=sum(p['cpu'] in p['sender_cpus'] for p in subset),
                        one_second=[dict(second=i,
                                         residence_ms=stats([r[3] for r in residence[dev] if i*10**9<=r[0]-first<(i+1)*10**9]),
                                         callback_lateness_ms=stats([p['callback_lateness_ns']/1e6 for p in subset if i*10**9<=p['callback_ns']-first<(i+1)*10**9])) for i in range(101)])
result = dict(timer_map=mapping, timer_map_counts={p:dict(c) for p,c in directions.items()},
              start_to_next_dequeue_ns=stats(null_gaps), following_dequeue_packets=dict(following_classes), unmapped_starts=unmapped,
              summaries=summary, largest_callbacks=sorted(pairs,key=lambda p:p['callback_lateness_ns'],reverse=True)[:30],
              sender_switch_ins_per_cpu=dict(Counter(s['cpu'] for s in switches if s['edge']=='in')),
              sender_switches=switches, elapsed_s=time.monotonic()-started,
              limitations=['same-CPU next-dequeue direction association is evidence, not direct timer-to-qdisc pointer recording; bulk lookahead can rearm before positive dequeue',
                           'next-positive dequeue interval is temporal association, not callback causal ownership',
                           'sender active means task current in sched trace, not uninterrupted host-vCPU execution',
                           'trace text precision approximately one microsecond'])
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('summaries','largest_callbacks','sender_switches','unmapped_starts')},indent=2))
print(json.dumps({dev:{k:v for k,v in values.items() if k!='one_second'} for dev,values in summary.items()},indent=2))
