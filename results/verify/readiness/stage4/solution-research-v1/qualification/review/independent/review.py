import hashlib,json,math,re,signal,statistics,struct,sys,time
from pathlib import Path
signal.alarm(90)
started=time.monotonic()
sys.path.insert(0,"src/analysis")
from sender_quality import evaluate

def capture(path):
    data=path.read_bytes();position=24;endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';records={}
    while position<len(data):
        sec,usec,count,length=struct.unpack_from(endian+'IIII',data,position);position+=16;frame=data[position:position+count];position+=count
        if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
        ip=frame[14:];udp=ip[(ip[0]&15)*4:];identity=int.from_bytes(udp[8:12],'big');assert identity not in records;records[identity]=dict(epoch_us=sec*1000000+usec,tag=udp[12:20].hex(),length=length)
    return records


def pairs(text):
    return {line.split()[0]:int(line.split()[1]) for line in text.splitlines() if len(line.split())==2}


def udp(text):
    lines=[line.split()[1:] for line in text.splitlines() if line.startswith('Udp:')]
    return dict(zip(lines[0],map(int,lines[1])))


run=Path('results/verify/diagnostic/sender-diagnostic.6uYg6iiy');seals=json.loads((run/'captured.json').read_text());assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in seals);assert (run/'exit').read_text().strip()=='0';sources=json.loads((run/'sources-before.json').read_text());assert sources==json.loads((run/'sources-after.json').read_text());assert all(hashlib.sha256((run/'sources'/name).read_bytes()).hexdigest()==sha for name,sha in sources.items());rows=[]
for label in ('baseline-q1','baseline-q2','baseline-q3'):
    d=run/label;probe=json.loads((d/'probe.json').read_text());quality=evaluate(probe['sent_records'],10000);saved=json.loads((d/'sender-quality.json').read_text());assert quality==saved;forward=capture(d/'browser.pcap');reverse=capture(d/'server.pcap');reply={r['id']:r['rtt_ms'] for r in probe['reply_records']};assert len(reply)==len(probe['reply_records'])==10000;assert set(forward)==set(reverse)==set(reply)==set(range(10000));tag=hashlib.sha256(probe['collection_id'].encode()).digest()[:8].hex();assert all(r['tag']==tag and r['length']==298 for r in list(forward.values())+list(reverse.values()));assert all('0 packets dropped by kernel' in (d/f'{role}.log').read_text() for role in ('browser','server'));qdisc=[]
    for dev in ('to_server','to_browser'):
        a,b=[next(r for r in json.loads((d/f'qdisc-{phase}.json').read_text()) if r['kind']=='netem' and r['dev']==dev) for phase in ('before','after')];assert a['options']==b['options'];delta={key:b[key]-a[key] for key in ('packets','bytes','drops','requeues','overlimits')};assert delta==dict(packets=10000,bytes=2980000,drops=0,requeues=0,overlimits=0);assert all(r[k]==0 for r in (a,b) for k in ('qlen','backlog'));qdisc.append(dict(dev=dev,delta=delta,options=a['options']))
    resources={}
    for role in ('browser','server'):
        samples=[json.loads(line) for line in (d/f'{role}-resources.jsonl').read_text().splitlines()];times=[r['wall_ns'] for r in samples];assert all(a<b for a,b in zip(times,times[1:]));first,last=samples[0],samples[-1];cpua,cpub=[pairs(r['/sys/fs/cgroup/cpu.stat']) for r in (first,last)];mem=[pairs(r['/sys/fs/cgroup/memory.events']) for r in samples];ua,ub=[udp(r['/proc/net/snmp']) for r in (first,last)];udelta={k:ub[k]-ua[k] for k in ua};assert udelta['InDatagrams']==udelta['OutDatagrams']==10000;assert all(udelta[k]==0 for k in ('InErrors','RcvbufErrors','SndbufErrors','InCsumErrors','MemErrors'));assert all(r['oom']==0 and r['oom_kill']==0 for r in mem);assert cpub['nr_throttled']==cpua['nr_throttled'] and cpub['throttled_usec']==cpua['throttled_usec'];resources[role]=dict(samples=len(samples),wall_start_ns=times[0],wall_end_ns=times[-1],duration_s=(times[-1]-times[0])/1e9,max_gap_s=max(b-a for a,b in zip(times,times[1:]))/1e9,cpu_usage_delta_usec=cpub['usage_usec']-cpua['usage_usec'],cpu_pct_onecore=(cpub['usage_usec']-cpua['usage_usec'])/(times[-1]-times[0])*100000,udp_delta=udelta,min_vm_memavailable_kib=min(int(re.search(r'^MemAvailable:\s+(\d+)',r['/proc/meminfo'],re.M)[1]) for r in samples),oom_zero=True,throttle_delta_zero=True)
    snapshots=[part.strip().splitlines() for part in (d/'router-resources.txt').read_text().split('snapshot-end') if part.strip()];firstq,lastq=[json.loads(x[1]) for x in (snapshots[0],snapshots[-1])];coverage={}
    for dev in ('to_browser','to_server'):
        a,b=[next(q for q in s if q['kind']=='netem' and q['dev']==dev) for s in (firstq,lastq)];coverage[dev]=b['packets']-a['packets'];assert coverage[dev]==10000
    rows.append(dict(label=label,sender=quality,replies=len(reply),median_rtt_ms=statistics.median(reply.values()),all_ids_tags_lengths_valid=True,capture_zero_drops=True,qdisc=qdisc,endpoint_resources=resources,router_samples=len(snapshots),router_duration_s=float(snapshots[-1][0])-float(snapshots[0][0]),router_first_last_coverage_packets=coverage))
result=dict(scope='Independent current-source 3x10000 UDP sender qualification checks; no external approval or full calibration claim',run=str(run),commit=(run/'commit').read_text().strip(),seals_verified=len(seals),source_snapshots_verified=len(sources),rows=rows,all_sender_passed=all(r['sender']['status']=='passed' for r in rows),elapsed_s=time.monotonic()-started);print(json.dumps(result,indent=2))
