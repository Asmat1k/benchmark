import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'docker'))
from calibration_report import directions

run = Path(sys.argv[1])
out = Path(__file__).parent


def summary(values):
    values = sorted(values)
    return dict(n=len(values), p50=values[len(values)//2], p99=values[math.ceil(len(values)*.99)-1], max=values[-1])


def fields(value):
    return {k:int(v) for k,v in (line.split() for line in value.splitlines())}


def arp_count(path):
    count = 0
    with path.open('rb') as f:
        endian = '<' if f.read(4) == b'\xd4\xc3\xb2\xa1' else '>'
        f.read(20)
        while record := f.read(16):
            size = struct.unpack(endian+'IIII', record)[2]
            frame = f.read(size)
            count += frame[12:14] == b'\x08\x06'
    return count


result = dict(run=str(run), diagnostic_only=True, collections={})
for path in sorted(run.glob('*/probe.json')):
    probe = json.loads(path.read_text())
    lag = [r['t_send_ms']-r['t_plan_ms'] for r in probe['sent_records']]
    traces = probe.get('trace', [])
    grouped = {kind:[t for t in traces if t['kind']==kind] for kind in ('send','select','receive')}
    row = dict(lag_ms=summary(lag), late_slots=sum(x>=10 for x in lag),
               early_slots=sum(x<0 for x in lag), rtt_ms=summary(probe['rtt_ms']),
               send_ids=len({r['id'] for r in probe['sent_records']}),
               reply_ids=len({r['id'] for r in probe['reply_records']}), replies=len(probe['reply_records']),
               send_duration_s=(probe['sent_records'][-1]['t_send_ms']-probe['sent_records'][0]['t_send_ms'])/1000,
               cpu_s=(probe['usage_after']['cpu_ns']-probe['usage_before']['cpu_ns'])/1e9 if traces else None,
               accounting=directions(path.parent,probe),
               arp={role:arp_count(path.parent/f'{role}.pcap') for role in ('server','browser')})
    row['accounting']=[dict(direction=r['direction'],entered=len(r['entered_ids']),drops=len(r['dropped_ids'])) for r in row['accounting']]
    for kind, events in grouped.items():
        if not events:
            continue
        row[kind] = dict(wall_ms=summary([(t['after']['wall_ns']-t['before']['wall_ns'])/1e6 for t in events]),
                         cpu_ms=summary([(t['after']['cpu_ns']-t['before']['cpu_ns'])/1e6 for t in events]),
                         runnable_wait_ms=summary([(t['after']['schedstat'][1]-t['before']['schedstat'][1])/1e6 for t in events]))
    if traces:
        row['select']['timeout_overshoot_ms'] = summary([(t['after']['wall_ns']-t['before']['wall_ns']-t['timeout_ns'])/1e6 for t in grouped['select']])
        row['select']['over_10ms_beyond_timeout'] = sum(t['after']['wall_ns']-t['before']['wall_ns']-t['timeout_ns']>=10e6 for t in grouped['select'])
    late_details=[]
    events=[]
    slot=0
    for t in traces:
        if t['kind'] != 'send':
            events.append(t)
            continue
        if lag[slot]>=10:
            late_details.append(dict(id=slot, lag_ms=lag[slot], preceding_events=events,
                                     send=t))
        slot+=1
        events=[]
    (out/f'{path.parent.name}-late-details.json').write_text(json.dumps(late_details,indent=2)+'\n')
    resources={}
    for role in ('browser','server'):
        samples=[json.loads(line) for line in (path.parent/f'{role}-resources.jsonl').read_text().splitlines()]
        a,b=samples[0],samples[-1]
        cpu_a,cpu_b=[fields(s['/sys/fs/cgroup/cpu.stat']) for s in (a,b)]
        events_a,events_b=[fields(s['/sys/fs/cgroup/memory.events']) for s in (a,b)]
        vm_a,vm_b=[list(map(int,s['/proc/stat'].splitlines()[0].split()[1:])) for s in (a,b)]
        delta=[y-x for x,y in zip(vm_a,vm_b)]
        resources[role]=dict(cpu_delta={k:cpu_b[k]-v for k,v in cpu_a.items()},
                            cpu_max=a['/sys/fs/cgroup/cpu.max'].strip(),
                            memory_peak_sampled=max(int(s['/sys/fs/cgroup/memory.current']) for s in samples),
                            memory_events_delta={k:events_b[k]-v for k,v in events_a.items()},
                            vm_busy_fraction=1-(delta[3]+delta[4])/sum(delta),
                            vm_available_kib_min=min(int(s['/proc/meminfo'].split('MemAvailable:')[1].split()[0]) for s in samples))
    row['resources']=resources
    result['collections'][path.parent.name]=row
neighbors={}
for path in run.glob('*neighbors*.json'):
    records=json.loads(path.read_text())
    neighbors[path.name]=records
    assert len(records)==1 and records[0]['state']==['PERMANENT']
result['neighbors']=neighbors
(out/f'{run.name}-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({name:{k:v for k,v in row.items() if k not in ('accounting',)} for name,row in result['collections'].items()},indent=2))
