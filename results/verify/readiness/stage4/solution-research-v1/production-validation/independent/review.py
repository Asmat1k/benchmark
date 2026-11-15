import hashlib,json,math,signal,statistics,struct,sys,time
from pathlib import Path
signal.alarm(90)
started=time.monotonic()
sys.path.insert(0,"src/analysis")
from sender_quality import evaluate

def process(probe):
    observed = {r['id']: r['rtt_ms'] for r in probe['reply_records']}
    count = 10000
    median = statistics.median(observed.values())
    series = dict(survival=[float(i in observed) for i in range(count)], rtt=[observed.get(i, median) for i in range(count)])
    results = {}
    for name, values in series.items():
        mean = sum(values)/count
        centered = [value-mean for value in values]
        variance = sum(value*value for value in centered)
        correlations = {str(lag): sum(centered[i]*centered[i+lag] for i in range(count-lag))/variance if variance else 0. for lag in (500, 1000, 2000)}
        results[name] = dict(long_lag=correlations, suspect=any(abs(value) > 3.5/math.sqrt(count-int(lag)) for lag, value in correlations.items()))
    chunks = []
    for first in range(0, count, 500):
        values = [observed[i] for i in range(first, first+500) if i in observed]
        chunks.append(statistics.median(values) if values else None)
    drift = sum((i-9.5)*value for i, value in enumerate(chunks))/665*19 if all(value is not None for value in chunks) else None
    return dict(**results, chunk_medians_ms=chunks, fitted_drift_ms=drift, suspect=any(value['suspect'] for value in results.values()) or drift is None or abs(drift) > 2)


def capture(path):
    data=path.read_bytes();position=24;endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';records={}
    while position<len(data):
        sec,usec,count,length=struct.unpack_from(endian+'IIII',data,position);position+=16;frame=data[position:position+count];position+=count
        if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
        ip=frame[14:];udp=ip[(ip[0]&15)*4:];identity=int.from_bytes(udp[8:12],'big');assert identity not in records;records[identity]=dict(epoch_us=sec*1000000+usec,tag=udp[12:20].hex(),length=length)
    return records


def cpu(path):
    result={}
    for line in path.read_text().splitlines():
        fields=line.split()
        if len(fields)==2 and fields[0].endswith(('usec','periods','throttled','bursts')):
            result[fields[0]]=int(fields[1])
    return result


run=Path('results/verify/diagnostic/affinity-validation.83SwishH');seals=json.loads((run/'captured.json').read_text());assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in seals);assert (run/'exit').read_text().strip()=='0';rows=[]
for label in ('r80p0-check','r80p1-check'):
    d=run/label;probe=json.loads((d/'probe.json').read_text());quality=evaluate(probe['sent_records'],10000);diagnostics=process(probe);forward=capture(d/'browser.pcap');reverse=capture(d/'server.pcap');reply={r['id']:r['rtt_ms'] for r in probe['reply_records']};assert set(forward)==set(range(10000));assert set(reply)<=set(reverse)<=set(forward);tag=hashlib.sha256(probe['collection_id'].encode()).digest()[:8].hex();assert all(r['tag']==tag and r['length']==298 for r in list(forward.values())+list(reverse.values()));assert probe['sender_cpu_after']==[0]
    qdisc=[]
    for dev,entered,left in [('to_server',set(forward),set(reverse)),('to_browser',set(reverse),set(reply))]:
        a,b=[next(r for r in json.loads((d/f'qdisc-{phase}.json').read_text()) if r['kind']=='netem' and r['dev']==dev) for phase in ('before','after')];assert a['options']==b['options'];delta={key:b[key]-a[key] for key in ('packets','bytes','drops','requeues','overlimits')};assert delta['packets']==len(left) and delta['bytes']==len(left)*298 and delta['drops']==len(entered-left);assert all(r[k]==0 for r in (a,b) for k in ('qlen','backlog'));qdisc.append(dict(dev=dev,entered=len(entered),survived=len(left),dropped=len(entered-left),loss_fraction=len(entered-left)/len(entered),options=a['options'],delta=delta))
    duration=float((d/'cpu-after.txt').read_text().split()[0])-float((d/'cpu-before.txt').read_text().split()[0]);before=cpu(d/'sender-cpu-before.txt');after=cpu(d/'sender-cpu-after.txt');sender_delta={k:after[k]-before[k] for k in before};router_before=cpu(d/'cpu-before.txt');router_after=cpu(d/'cpu-after.txt');router_delta={k:router_after[k]-router_before[k] for k in router_before};logs={role:(d/f'{role}.log').read_text() for role in ('browser','server')};assert all('0 packets dropped by kernel' in value for value in logs.values());spans={i:(reverse[i]['epoch_us']-forward[i]['epoch_us'])/1000 for i in reply};five=[]
    for first in range(0,10000,500):
        ids=[i for i in range(first,first+500) if i in reply];five.append(dict(first_s=first/100,span_median_ms=statistics.median([spans[i] for i in ids]),remaining_median_ms=statistics.median([reply[i]-spans[i] for i in ids])))
    rows.append(dict(label=label,sender=quality,process=diagnostics,replies=len(reply),sender_cpu_after=probe['sender_cpu_after'],cpu_duration_s=duration,sender_cpu_delta=sender_delta,sender_cpu_pct_of_one_core=sender_delta['usage_usec']/duration/10000,router_cpu_delta=router_delta,qdisc=qdisc,capture_zero_drops=True,five_second_components=five,rtt_median_ms=statistics.median(reply.values())))
result=dict(scope='Independent short applied-affinity validation, no full calibration or gate approval',run=str(run),commit=(run/'commit').read_text().strip(),sealed_files_verified=len(seals),source_probe_sha256=hashlib.sha256((run/'tools/calibration_probe.py').read_bytes()).hexdigest(),rows=rows,all_sender_passed=all(r['sender']['status']=='passed' for r in rows),all_process_clear=all(not r['process']['suspect'] for r in rows),excluded_invalid_run='results/verify/diagnostic/affinity-validation.C9bJRLo6 (interrupted battery run, preserved; not analyzed as scientific data)',elapsed_s=time.monotonic()-started)
print(json.dumps(result,indent=2))
