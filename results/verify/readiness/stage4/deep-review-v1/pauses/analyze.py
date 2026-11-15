import datetime
import hashlib
import json
from pathlib import Path
import statistics
import struct
import time

RUN = Path('results/verify/diagnostic/calibration.lShojabe')
OUTPUT = Path('results/verify/readiness/stage4/deep-review-v1/pauses')
EPISODES = [('r20p0-after', 5928), ('r20p1-after', 891)]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def pcap(path):
    data = path.read_bytes()
    assert data[:4] in (b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4')
    endian = '<' if data[:4] == b'\xd4\xc3\xb2\xa1' else '>'
    assert struct.unpack_from(endian+'I', data, 20)[0] == 1
    offset, records = 24, []
    while offset < len(data):
        seconds, micros, length, wire = struct.unpack_from(endian+'IIII', data, offset)
        offset += 16
        frame = data[offset:offset+length]
        offset += length
        assert len(frame) == length
        if frame[12:14] != b'\x08\x00':
            continue
        ip = frame[14:]
        if ip[9] != 17:
            continue
        assert int.from_bytes(ip[6:8], 'big') & 0x3fff == 0
        udp = ip[(ip[0] & 15)*4:]
        identity, tag = struct.unpack_from('!I8s', udp, 8)
        records.append(dict(id=identity, epoch_us=seconds*1000000+micros, tag=tag.hex()))
    assert len(records) == len({r['id'] for r in records})
    assert all(a['epoch_us'] <= b['epoch_us'] for a, b in zip(records, records[1:]))
    return records

started = time.monotonic()
inputs = {}
seal = json.loads((RUN/'captured.json').read_text())
for row in seal:
    assert digest(Path(row['path'])) == row['sha256']
inputs[str(RUN/'captured.json')] = digest(RUN/'captured.json')
results = []
for name, identity in EPISODES:
    directory = RUN/name
    for path in [directory/'probe.json', directory/'browser.pcap', directory/'server.pcap', directory/'qdisc-before.json', directory/'qdisc-after.json']:
        inputs[str(path)] = digest(path)
    probe = json.loads((directory/'probe.json').read_text())
    sends = {r['id']: r for r in probe['sent_records']}
    replies = {r['id']: r for r in probe['reply_records']}
    forward, reverse = pcap(directory/'browser.pcap'), pcap(directory/'server.pcap')
    expected_tag = hashlib.sha256(probe['collection_id'].encode()).digest()[:8].hex()
    assert all(p['tag'] == expected_tag for p in forward+reverse)
    fwd = {r['id']: r['epoch_us'] for r in forward}
    rev = {r['id']: r['epoch_us'] for r in reverse}
    assert set(fwd) == set(range(10000))
    assert set(replies) <= set(rev) <= set(fwd)
    forward_delay_ms = next(q['options']['delay']['delay']*1000 for q in json.loads((directory/'qdisc-before.json').read_text()) if q['dev']=='to_server' and q['kind']=='netem')
    gaps = {}
    for label, records in [('forward', forward), ('reverse', reverse)]:
        candidates = [(a, b) for a, b in zip(records, records[1:]) if identity-4 <= b['id'] <= identity+4]
        a, b = max(candidates, key=lambda pair: pair[1]['epoch_us']-pair[0]['epoch_us'])
        gaps[label] = dict(previous_id=a['id'], next_id=b['id'], start_epoch_us=a['epoch_us'], end_epoch_us=b['epoch_us'], duration_ms=(b['epoch_us']-a['epoch_us'])/1000)
    overlap = max(0, min(g['end_epoch_us'] for g in gaps.values())-max(g['start_epoch_us'] for g in gaps.values()))/1000
    timeline = []
    anchor_id = identity-8
    anchor_epoch_us = fwd[anchor_id]
    for i in range(identity-6, identity+9):
        planned = sends[i]['t_plan_ms']
        sent = sends[i]['t_send_ms']
        timeline.append(dict(id=i, planned_ms=planned, send_ms=sent, lag_ms=sent-planned, send_gap_ms=sent-sends[i-1]['t_send_ms'], forward_epoch_us=fwd[i], reverse_epoch_us=rev.get(i), forward_from_anchor_ms=(fwd[i]-anchor_epoch_us)/1000, reverse_from_anchor_ms=(rev[i]-anchor_epoch_us)/1000 if i in rev else None, rtt_ms=replies[i]['rtt_ms'] if i in replies else None, received_ms=sent+replies[i]['rtt_ms'] if i in replies else None, path_forward_reverse_ms=(rev[i]-fwd[i])/1000 if i in rev else None))
    slow_echo_id = gaps['reverse']['next_id']
    path_ms = (rev[slow_echo_id]-fwd[slow_echo_id])/1000
    ordinary = [(rev[i]-fwd[i])/1000 for i in range(identity-200, identity-20) if i in rev]
    results.append(dict(name=name, failed_sender_id=identity, gap=gaps, simultaneous_ingress_quiet_ms=overlap, forward_nominal_delay_ms=forward_delay_ms, slow_echo_id=slow_echo_id, slow_echo_path_ms=path_ms, slow_echo_extra_over_nominal_ms=path_ms-forward_delay_ms, ordinary_path_median_ms=statistics.median(ordinary), timeline=timeline, reply_order=[r['id'] for r in probe['reply_records'] if identity-8 <= r['id'] <= identity+9]))
result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),input_files=inputs,all_146_seal_entries_verified=len(seal),episodes=results,limitations=['Packet captures share guest realtime clock; timestamps are ingress observations, not final egress or endpoint application timestamps.', 'Sender times are relative monotonic; no absolute sender start is stored. No exact cross-clock epoch alignment is claimed.', 'Overlapping quiet intervals are consistent with common VM/kernel service interruption, but do not identify guest scheduling, vCPU descheduling or host process.', 'Sender GC or allocator pauses alone cannot account for excessive forward-netem-plus-server response time of an already sent packet. Independent coincident path and sender pauses are not logically excluded.', 'No CPU, scheduler, GC, timer or host trace was recorded during these two episodes.'],elapsed_s=time.monotonic()-started)
with (OUTPUT/'analysis.json').open('x') as handle:
    json.dump(result, handle, indent=2)
    handle.write('\n')
print(json.dumps({r['name']: dict(overlap_ms=r['simultaneous_ingress_quiet_ms'],slow_echo_id=r['slow_echo_id'],slow_echo_path_ms=r['slow_echo_path_ms'],extra_ms=r['slow_echo_extra_over_nominal_ms']) for r in results},indent=2))
