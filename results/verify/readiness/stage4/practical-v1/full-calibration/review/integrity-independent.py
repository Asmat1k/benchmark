import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import time

START = time.monotonic()
RUN = Path('results/verify/diagnostic/calibration.sFWOAzbo')
BASE = Path('results/verify/readiness/stage4/practical-v1/full-calibration')
EXECUTION = BASE/'execution.trv5h_3g'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
head = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head == (RUN/'commit').read_text().strip() == 'acce5946499b7471bc35965919f3cdc910a7922c'
assert (RUN/'exit').read_text().strip() == (EXECUTION/'exit').read_text().strip() == '0'
assert read(EXECUTION/'identity-before.json') == read(EXECUTION/'identity-after.json')
identity = read(EXECUTION/'identity-after.json')
assert all(sha(Path(p)) == h for p,h in identity.items())
sources = read(RUN/'sources-before.json')
assert sources == read(RUN/'sources-after.json')
assert all(sha(Path(p)) == h for p,h in sources.items())
seals = read(RUN/'captured.json')
assert len(seals) == 146 and all(sha(Path(r['path'])) == r['sha256'] for r in seals)
actual = {str(p) for p in RUN.rglob('*') if p.is_file() and 'publication' not in p.relative_to(RUN).parts}
assert actual-{str(RUN/n) for n in ('captured.json','ended','exit')} == {r['path'] for r in seals}
context = read(RUN/'context-before.json')
assert context == read(RUN/'context-after.json') == read(Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json'))
assert context['config'] == {k:read(Path('configs')/(k+'.json')) for k in ('plan','profiles','thresholds')}
plan = read(RUN/'collection-plan.json')
assert plan == read(BASE/'collection-plan.json') and plan['method'] == context['config']['plan']['calibration']
assert len(plan['collections']) == 18 and len({x['name'] for x in plan['collections']}) == 18
assert {p.name for p in RUN.iterdir() if p.is_dir() and p.name != 'publication'} == {x['name'] for x in plan['collections']}
features = ('tcp-segmentation-offload','generic-segmentation-offload','generic-receive-offload','large-receive-offload')
for role,peer,route in [('browser','20','172.28.20.10 via 172.28.10.2'),('server','10','172.28.10.10 via 172.28.20.2')]:
    text = (RUN/(role+'-route.txt')).read_text()
    assert route in text and all(f+': off' in text for f in features)
assert all((RUN/'router-links.txt').read_text().count(f+': off') == 2 for f in features)
assert hashlib.sha256(context['leaf'].encode()).hexdigest() == 'ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9'
neighbors = {}
for role in ('browser','server'):
    for prefix in ('','router-'):
        label = prefix+role
        entries = read(RUN/(label+'-neighbors.json'))
        assert len(entries) == 1 and 'PERMANENT' in entries[0]['state']
        neighbors[label] = entries[0]['lladdr'].replace(':','')


def capture(path,source,destination,tag):
    with path.open('rb') as f:
        magic = f.read(4)
        assert magic in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4')
        endian = '<' if magic == b'\xd4\xc3\xb2\xa1' else '>'
        header = f.read(20)
        assert len(header) == 20 and struct.unpack_from(endian+'I',header,16)[0] == 1
        ids = []
        macs = set()
        while block := f.read(16):
            assert len(block) == 16
            sec,usec,size,wire = struct.unpack(endian+'IIII',block)
            frame = f.read(size)
            assert len(frame) == size == 96 and wire == 298 and frame[12:14] == b'\x08\x00'
            ip = frame[14:]
            assert ip[0] == 0x45 and ip[9] == 17 and not (int.from_bytes(ip[6:8],'big') & 0x3fff)
            assert ip[12:16] == source and ip[16:20] == destination and int.from_bytes(ip[2:4],'big') == 284
            sport,dport,length = struct.unpack_from('!HHH',ip,20)
            assert 29543 in (sport,dport) and length == 264
            identity,observed = struct.unpack_from('!I8s',ip,28)
            assert 0 <= identity < 10000 and observed == tag and frame[54:] == bytes(42)
            ids.append(identity)
            macs.add((frame[6:12].hex(),frame[:6].hex()))
    assert len(ids) == len(set(ids))
    return set(ids),sorted(macs)


def queues(path):
    return {r['dev']:r for r in read(path) if r['kind'] == 'netem'}


echo = []
saturation = []
for index,item in enumerate(plan['collections']):
    assert time.monotonic()-START < 110
    name = item['name']
    folder = RUN/name
    profile = name.rsplit('-',1)[0]
    profile = profile if index < 14 else 'r20p'+name.split('-')[1]
    probe = read(folder/'probe.json')
    assert probe['collection_id'] == RUN.name+'/'+name
    profile_rows = [json.loads(line.split(' ',1)[1])[0] for line in (folder/'profile.txt').read_text().splitlines()]
    assert len(profile_rows) == 2
    for q,direction in zip(profile_rows,('forward','reverse')):
        opt = q['options']
        assert opt['limit'] == 1000 and opt['rate']['rate'] == 1250000
        assert opt['seed'] == item[direction+'_seed']
        assert opt.get('delay',{}).get('delay',0) == (0 if profile == 'baseline' else .01 if profile.startswith('r20') else .04)
        assert opt.get('loss-random',{}).get('loss',0) == (.01 if profile.endswith('p1') else 0)
    if index < 14:
        assert (probe['sent'],probe['frame_bytes'],probe['frequency_hz']) == (10000,256,100)
        sent = probe['sent_records']
        replies = probe['reply_records']
        assert [r['id'] for r in sent] == list(range(10000))
        assert all(r['t_plan_ms'] == 10*i and math.isfinite(r['t_send_ms']) and r['t_send_ms'] >= r['t_plan_ms'] for i,r in enumerate(sent))
        assert all(a['t_send_ms'] <= b['t_send_ms'] for a,b in zip(sent,sent[1:]))
        returned = {r['id'] for r in replies}
        assert len(returned) == len(replies) and returned <= set(range(10000))
        assert all(math.isfinite(r['rtt_ms']) and r['rtt_ms'] >= 0 for r in replies)
        assert probe['rtt_ms'] == [r['rtt_ms'] for r in replies]
        tag = hashlib.sha256(probe['collection_id'].encode()).digest()[:8]
        forward,fmacs = capture(folder/'browser.pcap',bytes([172,28,10,10]),bytes([172,28,20,10]),tag)
        reverse,rmacs = capture(folder/'server.pcap',bytes([172,28,20,10]),bytes([172,28,10,10]),tag)
        assert forward == set(range(10000)) and returned <= reverse <= forward
        first,last = queues(folder/'qdisc-before.json'),queues(folder/'qdisc-after.json')
        detail = []
        for role,dev,entered,delivered,macs in [('browser','to_server',forward,reverse,fmacs),('server','to_browser',reverse,returned,rmacs)]:
            assert '0 packets dropped by kernel' in (folder/(role+'.log')).read_text()
            assert str(len(entered))+' packets captured' in (folder/(role+'.log')).read_text()
            a,b = first[dev],last[dev]
            assert macs == [(neighbors['router-'+role],neighbors[role])]
            assert a['handle'] == b['handle'] and a['options'] == b['options']
            assert all(q['backlog'] == q['qlen'] == 0 for q in (a,b))
            assert all(q['overlimits'] == q['requeues'] == 0 for q in (a,b))
            assert b['drops']-a['drops'] == len(entered-delivered)
            assert b['packets']-a['packets'] == len(delivered)
            assert b['bytes']-a['bytes'] == 298*len(delivered)
            detail.append(dict(direction='forward' if role == 'browser' else 'reverse',entered=len(entered),delivered=len(delivered),drops=len(entered-delivered),macs=macs))
        if not profile.endswith('p1'):
            assert len(returned) == 10000
        echo.append(dict(name=name,sent=len(sent),returned=len(returned),directions=detail))
    else:
        window = (folder/'window.txt').read_text().splitlines()
        assert len(window) == 6 and probe['frame_bytes'] == 1200 and probe['sent'] == 90000
        duration = float(window[3])-float(window[0])
        a,b = json.loads(window[2]),json.loads(window[5])
        assert duration >= 60 and a['dev'] == b['dev'] and a['options'] == b['options'] and a['handle'] == b['handle']
        assert probe['first_uptime'] < float(window[0]) < float(window[3]) < probe['last_uptime']
        assert (probe['last_ns']-probe['first_ns'])/1e9 >= duration
        offered = int(window[4])-int(window[1])
        forwarded = b['bytes']-a['bytes']
        assert offered >= forwarded > 0 and forwarded == 1242*(b['packets']-a['packets'])
        stable = queues(folder/'qdisc-stable.json')
        assert all(q['backlog'] == q['qlen'] == 0 for q in stable.values())
        saturation.append(dict(name=name,duration_s=duration,offered_bytes=offered,forwarded_bytes=forwarded,mbit_s=8*forwarded/duration/1e6,window_drops=b['drops']-a['drops'],accounting='dequeued skb Ethernet+IPv4+UDP+1200payload=1242bytes; intentional saturated drops retained'))
stderr = (EXECUTION/'stderr.log').read_text()
assert all('wswt-'+RUN.name.replace('.','-').lower()+'-'+r+'-1 Removed' in stderr for r in ('browser','server','router'))
output = dict(status='passed_internal_independent_integrity_review',source_commit=head,run=str(RUN),execution=str(EXECUTION),sealed_files=len(seals),sealed_inventory_complete=True,source_count=len(sources),echo=echo,saturation=saturation,context_current_timer_equal=True,cleanup_removed_in_log=True,elapsed_s=time.monotonic()-START,inputs=[dict(path=str(p),sha256=sha(p)) for p in (RUN/'captured.json',RUN/'collection-plan.json',RUN/'context-before.json',EXECUTION/'identity-after.json',EXECUTION/'stderr.log')],limitations=['Integrity review is not observed metric acceptance or stage4completion','Pcap snaplen96 covers IDs/tags/headers and prefix, not full256payload; exact receive validation is source-enforced','MTU1500 enforced by executed setup source; no separate MTU text readback saved in this collector','No endpoint UDP/resource sampler in this full collector; loss identity/capture/qdisc checks exclude unexplained missing echo, not all possible CPU pauses','Saturation intentionally fills queues and drops packets; those drops are not fidelity-loss samples','Cleanup verified from logs; no separate actual live Docker inventory queried'])
target = BASE/'review/integrity-independent-with-neighbors.json'
assert not target.exists()
target.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(dict(output=str(target),sealed_files=len(seals),echo_count=len(echo),saturation=saturation,elapsed_s=output['elapsed_s']),indent=2))
