from collections import deque
from decimal import Decimal as D
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct


RUN = Path('results/verify/diagnostic/calibration.sFWOAzbo')
BASE = Path('results/verify/readiness/stage4/practical-v1/full-calibration')
OUT = BASE/'review/method-results.json'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
failures = []


def check(ok, identity):
    if not ok:
        failures.append(identity)


def rolling(values):
    queue = deque()
    total = 0
    result = []
    for value in values:
        queue.append(int(value)); total += int(value)
        if len(queue)>1200: total -= queue.popleft()
        if len(queue)==1200: result.append(total)
    return result


def summary(values):
    x = sorted(values)
    if not x: return dict(n=0)
    return dict(n=len(x),median_ms=statistics.median(x),mean_ms=statistics.mean(x),
        p95_ms=x[math.ceil(.95*len(x))-1],p99_ms=x[math.ceil(.99*len(x))-1],max_ms=x[-1])


def packets(path, tag, source, target):
    ids = []
    with path.open('rb') as f:
        magic = f.read(4)
        assert magic in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4')
        endian = '<' if magic==b'\xd4\xc3\xb2\xa1' else '>'
        header = f.read(20)
        assert struct.unpack_from(endian+'I',header,16)[0]==1
        while record:=f.read(16):
            assert len(record)==16
            _,_,captured,length = struct.unpack(endian+'IIII',record)
            frame=f.read(captured)
            assert len(frame)==captured
            if frame[12:14]!=b'\x08\x00': continue
            ip=frame[14:]; assert len(ip)>=20 and ip[0]>>4==4
            assert not int.from_bytes(ip[6:8],'big')&0x3fff
            if ip[9]!=17: continue
            assert ip[12:16]==source and ip[16:20]==target
            udp=ip[(ip[0]&15)*4:]
            sport,dport,size=struct.unpack_from('!HHH',udp)
            assert 29543 in (sport,dport) and size==264 and length==14+(ip[0]&15)*4+264
            identity,actual_tag=struct.unpack_from('!I8s',udp,8)
            assert actual_tag==tag
            ids.append(identity)
    assert len(set(ids))==len(ids)
    return set(ids)


assert (RUN/'exit').read_text().strip()=='0'
fixed = read(BASE/'FIXED-SHA256.json')
for path,digest in fixed.items(): check(sha(path)==digest,'fixed_hash:'+path)
refs=read(RUN/'captured.json')
for ref in refs: check(sha(ref['path'])==ref['sha256'],'seal:'+ref['path'])
plan=read(RUN/'collection-plan.json')
check(plan==read(BASE/'collection-plan.json'),'fixed_collection_plan')
check(read(RUN/'sources-before.json')==read(RUN/'sources-after.json'),'source_stability')
check(read(RUN/'context-before.json')==read(RUN/'context-after.json'),'environment_stability')
series=[]; windows={}; losses=[]
for item in plan['collections'][:14]:
    name=item['name']; folder=RUN/name; p=read(folder/'probe.json')
    assert p['collection_id']==RUN.name+'/'+name
    sends=p['sent_records']; replies=p['reply_records']
    assert [r['id'] for r in sends]==list(range(10000))
    assert len({r['id'] for r in replies})==len(replies)
    assert all(type(r['rtt_ms']) in (int,float) and math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in replies)
    reply={r['id']:r['rtt_ms'] for r in replies}
    assert set(reply)<=set(range(10000)) and p['rtt_ms']==[r['rtt_ms'] for r in replies]
    assert p['sent']==10000 and p['frequency_hz']==100 and p['frame_bytes']==256
    planned=[D(str(r['t_plan_ms'])) for r in sends]; actual=[D(str(r['t_send_ms'])) for r in sends]
    assert all(t==planned[0]+10*i for i,t in enumerate(planned))
    lag=[a-b for a,b in zip(actual,planned)]; gaps=[b-a for a,b in zip(actual,actual[1:])]
    assert min(lag)>=0 and min(gaps)>=0
    check(min(gaps)>=D('2.5'),name+':spacing')
    check(sum(v>=10 for v in lag)<=100,name+':late1pct')
    left=0; burst=0
    for right,t in enumerate(actual):
        while actual[left]<=t-10: left+=1
        burst=max(burst,right-left+1)
    check(burst<=4,name+':burst')
    phases=[]; lossy='p1-' in name
    for phase in range(5):
        ids=list(range(phase,10000,5))
        overdue=[lag[i]>=50 for i in ids]
        known=[bad or (i in reply and actual[i]+D(str(reply[i]))>planned[i]+100) for bad,i in zip(overdue,ids)]
        unknown=[not bad and i not in reply for bad,i in zip(overdue,ids)]
        counts=dict(sender_overdue=rolling(overdue),known_timing_bad=rolling(known),unknown_reply=rolling(unknown),
                    bad_if_all_unknown_bad=rolling([a or b for a,b in zip(known,unknown)]))
        assert all(len(v)==801 for v in counts.values())
        check(max(counts['sender_overdue'])<=12,name+':lagproxy:'+str(phase))
        if not lossy:
            check(max(counts['known_timing_bad'])<=12 and not any(counts['unknown_reply']),name+':jointproxy:'+str(phase))
        phases.append(dict(phase=phase,counts=counts,maxima={k:max(v) for k,v in counts.items()}))
    rtts=list(reply.values()); threshold=sorted(rtts)[math.ceil(.99*len(rtts))-1]
    body=[r for r in replies if r['rtt_ms']<=threshold]; tail=[r for r in replies if r['rtt_ms']>threshold]
    assert len(body)+len(tail)==len(replies)
    localwindows=[]
    for start in range(0,10000,500):
        values=[reply[i] for i in range(start,start+500) if i in reply]
        localwindows.append(dict(start_id=start,planned=500,returned=len(values),median_ms=statistics.median(values) if values else None))
    if name.startswith('baseline-') or name.endswith('-latency'):
        windows[name]=localwindows; check(all(w['returned'] for w in localwindows),name+':emptywindow')
    tag=hashlib.sha256(p['collection_id'].encode()).digest()[:8]
    fwd=packets(folder/'browser.pcap',tag,bytes([172,28,10,10]),bytes([172,28,20,10]))
    rev=packets(folder/'server.pcap',tag,bytes([172,28,20,10]),bytes([172,28,10,10]))
    assert fwd==set(range(10000)) and set(reply)<=rev<=fwd
    for direction,dev,entered,returned in [('forward','to_server',fwd,rev),('reverse','to_browser',rev,set(reply))]:
        dropped=entered-returned; counts=[]
        for when in ('before','after'):
            q=[q for q in read(folder/f'qdisc-{when}.json') if q['kind']=='netem' and q['dev']==dev]
            assert len(q)==1 and q[0]['backlog']==q[0]['qlen']==0
            counts.append(q[0]['drops'])
        assert counts[1]-counts[0]==len(dropped)
        formal=not name.startswith('baseline-') and not name.endswith('-latency')
        okay=(len(entered)<=200*len(dropped)<=3*len(entered)) if lossy else not dropped
        if formal: check(okay,name+':loss:'+direction)
        losses.append(dict(series=name,direction=direction,formal=formal,count=len(entered),drops=len(dropped),
                           pct=100*len(dropped)/len(entered),passed=okay,dropped_ids=sorted(dropped)))
    series.append(dict(name=name,lossy=lossy,missing_ids=sorted(set(range(10000))-set(reply)),
        late_count=sum(v>=10 for v in lag),max_lag_ms=float(max(lag)),min_gap_ms=float(min(gaps)),burst=burst,
        phases=phases,tail=dict(threshold_ms=threshold,all=summary(rtts),body=summary([r['rtt_ms'] for r in body]),
        tail=summary([r['rtt_ms'] for r in tail]),tail_records=tail,pct_returned=100*len(tail)/len(replies),pct_planned=len(tail)/100)))
envelopes=[]
for profile in ('r20p0','r20p1','r80p0','r80p1'):
    target=20 if profile.startswith('r20') else 80
    pv=[w['median_ms'] for w in windows[profile+'-latency']]
    for baseline in ('before','after'):
        bv=[w['median_ms'] for w in windows['baseline-'+baseline]]
        low=min(pv)-max(bv); high=max(pv)-min(bv)
        okay=target-2<=low<=high<=target+2
        check(okay,profile+':envelope:'+baseline)
        envelopes.append(dict(profile=profile,baseline=baseline,low_ms=low,high_ms=high,target_ms=target,passed=okay))
capacity=[]
for item in plan['collections'][14:]:
    name=item['name']; folder=RUN/name; text=(folder/'window.txt').read_text().splitlines()
    assert len(text)==6
    a,b=json.loads(text[2]),json.loads(text[5]); duration=D(text[3])-D(text[0])
    offered=int(text[4])-int(text[1]); forwarded=b['bytes']-a['bytes']
    p=read(folder/'probe.json')
    assert p['frame_bytes']==1200 and D(str(p['first_uptime']))<D(text[0])<D(text[3])<D(str(p['last_uptime']))
    assert D(p['last_ns']-p['first_ns'])/D(10**9)>=duration>=60 and offered>=forwarded>0
    rate=D(forwarded)*8/duration/D(1000000)
    okay=9<=rate<=11;check(okay,name+':capacity')
    capacity.append(dict(series=name,direction=name.rsplit('-',1)[1],loss=int(name.split('-')[1])/100,
                         duration_s=float(duration),forwarded_bytes=forwarded,offered_bytes=offered,mbit_s=float(rate),passed=okay))
bridge=read(BASE.parent/'applicability/qualification-and-bw-bridge-v2.json')
ratios=[]
for mode in bridge['bandwidth_loads']:
    for load in mode['rates']:
        minimum=min(r['mbit_s'] for r in capacity if r['direction']==load['direction'])
        fraction=load['mbit_s_upper']/minimum
        check(fraction<.1,mode['mode']+':bandwidth:'+load['direction'])
        ratios.append(dict(mode=mode['mode'],direction=load['direction'],load_mbit_s=load['mbit_s_upper'],
                           conservative_capacity_mbit_s=minimum,fraction=fraction))
result=dict(status='passed_independent_numeric_review' if not failures else 'failed_independent_numeric_review',
    scope='Observed numeric profile/sender/loss/capacity review only; explicit integration/network reviews remain required',
    collection=RUN.name,failures=failures,sealed_inputs=len(refs),formal_loss_checks=sum(r['formal'] for r in losses),
    total_shadow_windows=14*4005,median_windows=windows,envelopes=envelopes,series=series,loss=losses,capacity=capacity,
    new_bandwidth_ratios=ratios,max_bandwidth_fraction=max(r['fraction'] for r in ratios),
    reviewer_script_sha256=sha(__file__),contract=plan['method'],
    source_ref=dict(path=str(RUN/'sources-before.json'),sha256=sha(RUN/'sources-before.json')),
    captured_ref=dict(path=str(RUN/'captured.json'),sha256=sha(RUN/'captured.json')),
    limitation='No future-process confidence guarantee; loss1 known joint counts lower bounds; tails retained and not a causal footprint')
with OUT.open('x') as out: json.dump(result,out,indent=2,allow_nan=False);out.write('\n')
print(json.dumps({k:result[k] for k in ('status','failures','sealed_inputs','formal_loss_checks','total_shadow_windows','envelopes','capacity','max_bandwidth_fraction')},indent=2))
raise SystemExit(bool(failures))
