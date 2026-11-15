import hashlib
import json
from pathlib import Path
import statistics
import struct

RUN = Path('results/verify/diagnostic/calibration.sFWOAzbo')
OUT = Path('results/verify/readiness/stage4/practical-v1/full-calibration/review')
folder = RUN/'r80p1-after'
probe = json.loads((folder/'probe.json').read_text())
sent = probe['sent_records']
reply = {r['id']:r['rtt_ms'] for r in probe['reply_records']}


def capture(path):
    data = path.read_bytes()
    endian = '<' if data[:4] == b'\xd4\xc3\xb2\xa1' else '>'
    offset = 24
    result = {}
    while offset < len(data):
        sec,usec,size,wire = struct.unpack_from(endian+'IIII',data,offset)
        offset += 16
        frame = data[offset:offset+size]
        offset += size
        identity = struct.unpack_from('!I',frame,42)[0]
        result[identity] = sec*1000000+usec
    return result


def describe(values):
    ordered = sorted(values)
    return dict(count=len(ordered),min=ordered[0],median=statistics.median(ordered),
                p99=ordered[max(0,(99*len(ordered)+99)//100-1)],max=ordered[-1])


browser = capture(folder/'browser.pcap')
server = capture(folder/'server.pcap')
lags = [r['t_send_ms']-r['t_plan_ms'] for r in sent]
gaps = [sent[i]['t_send_ms']-sent[i-1]['t_send_ms'] for i in range(1,10000)]
offsets = [browser[i]-round(sent[i]['t_send_ms']*1000) for i in range(10000)]
center = statistics.median(offsets)
residuals = [(x-center)/1000 for x in offsets]
spans = {i:(server[i]-browser[i])/1000 for i in server}
groups = []
for i,lag in enumerate(lags):
    if lag >= 10:
        if not groups or i != groups[-1][-1]+1:
            groups.append([])
        groups[-1].append(i)
bins = []
for start in range(0,10000,500):
    ids = list(range(start,start+500))
    bins.append(dict(start_id=start,end_id=start+499,sender_lag_ms=describe([lags[i] for i in ids]),
                     sender_capture_relative_offset_ms=describe([residuals[i] for i in ids]),
                     forward_capture_span_ms=describe([spans[i] for i in ids if i in spans]),
                     actual_rtt_ms=describe([reply[i] for i in ids if i in reply]),missing=sum(i not in reply for i in ids)))
records = [dict(id=i,planned_ms=sent[i]['t_plan_ms'],actual_send_ms=sent[i]['t_send_ms'],sender_lag_ms=lags[i],
                previous_send_gap_ms=None if i == 0 else gaps[i-1],sender_capture_relative_offset_ms=residuals[i],
                previous_browser_capture_gap_ms=None if i == 0 else (browser[i]-browser[i-1])/1000,
                forward_capture_span_ms=spans.get(i),actual_rtt_ms=reply.get(i)) for i in range(10000)]
series = []
for item in json.loads((RUN/'collection-plan.json').read_text())['collections'][:14]:
    value = json.loads((RUN/item['name']/'probe.json').read_text())
    values = [r['t_send_ms']-r['t_plan_ms'] for r in value['sent_records']]
    series.append(dict(name=item['name'],late_slots=sum(v>=10 for v in values),late_pct=sum(v>=10 for v in values)/100,max_sender_lag_ms=max(values)))
result = dict(status='descriptive_cause_audit_no_causal_source_established',series='r80p1-after',inputs=[dict(path=str(folder/n),sha256=hashlib.sha256((folder/n).read_bytes()).hexdigest()) for n in ('probe.json','browser.pcap','server.pcap','qdisc-before.json','qdisc-after.json')],
              all14sender_summaries=series,late_groups=[dict(start_id=g[0],end_id=g[-1],count=len(g),max_lag_ms=max(lags[i] for i in g)) for g in groups],
              sender_lag_ms=describe(lags),actual_send_gap_ms=describe(gaps),forward_capture_span_ms=describe(list(spans.values())),actual_rtt_ms=describe(list(reply.values())),
              largest_send_gaps=[records[i+1] for i in sorted(range(9999),key=lambda i:gaps[i],reverse=True)[:20]],
              largest_lag=records[max(range(10000),key=lambda i:lags[i])],fixed500idbins=bins,all_slot_records=records,
              offset_definition='pcap walltime microseconds minus relative monotonic send microseconds, centered by median all10000offsets; no absolute monotonic-to-wall anchor exists',
              limitations=['No RTT correction or missing-slot exclusion','PCAP forward span includes router queue, forward path, server echo handling and pre-server-ingress scheduling','PCAP-to-send residual combines syscall/ingress timestamp delay and wall/monotonic clock mapping; negative centered values are not negative physical delays','No sender process CPU/affinity trace, sender cgroup resources, vCPU scheduler or clockevent telemetry in this collection','Largest sender lag is accumulated backlog and not one pause duration','Cause remains unidentified; observations do not prove VM clock failure or CPU scheduler cause'])
target = OUT/'cause-evidence-pcap-gaps.json'
assert not target.exists()
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(largest_lag=result['largest_lag'],largest_gap=result['largest_send_gaps'][0],sender_lag=result['sender_lag_ms'],span=result['forward_capture_span_ms'],rtt=result['actual_rtt_ms']),indent=2))
