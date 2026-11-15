import hashlib,json,math,re,signal,statistics,struct,sys,time
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


def quantiles(values, probabilities):
    ordered=sorted(values)
    return {str(p):ordered[round((len(ordered)-1)*p)] for p in probabilities}


run=Path('results/verify/diagnostic/calibration.ew2u0ceD');seal=json.loads((run/'captured.json').read_text());assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in seal);assert (run/'exit').read_text().strip()=='0'
formal=('baseline-before','r20p0-latency','r20p1-latency','r80p0-latency','r80p1-latency','baseline-after')
loss_family=tuple(f'{profile}-{phase}' for phase in ('before','after') for profile in ('r20p0','r20p1','r80p0','r80p1'))
labels=('baseline-before','r20p0-before','r20p1-before','r80p0-before','r80p1-before','r20p0-latency','r20p1-latency','r80p0-latency','r80p1-latency','r20p0-after','r20p1-after','r80p0-after','r80p1-after','baseline-after');rows=[]
for label in labels:
    d=run/label;probe=json.loads((d/'probe.json').read_text());quality=evaluate(probe['sent_records'],10000);diag=process(probe);rtt={r['id']:r['rtt_ms'] for r in probe['reply_records']};assert len(rtt)==len(probe['reply_records']);F=capture(d/'browser.pcap');R=capture(d/'server.pcap');assert set(F)==set(range(10000));assert set(rtt)<=set(R)<=set(F);tag=hashlib.sha256(probe['collection_id'].encode()).digest()[:8].hex();assert all(r['tag']==tag and r['length']==298 for r in list(F.values())+list(R.values()));median=statistics.median(rtt.values());center=sorted(rtt.values());values=[rtt.get(i,median) for i in range(10000)];mean=statistics.mean(values);centered=[v-mean for v in values];variance=sum(v*v for v in centered);acf={str(lag):sum(centered[i]*centered[i+lag] for i in range(10000-lag))/variance if variance else 0. for lag in (1,10,50,100,200,500,1000,2000)};five=[]
    for first in range(0,10000,500):
        ids=[i for i in range(first,first+500) if i in rtt];spans=[(R[i]['epoch_us']-F[i]['epoch_us'])/1000 for i in ids];five.append(dict(first_s=first/100,returned=len(ids),rtt_quantiles=quantiles([rtt[i] for i in ids],[.05,.25,.49,.5,.51,.75,.95]),span_median_ms=statistics.median(spans),remaining_median_ms=statistics.median([rtt[i]-span for i,span in zip(ids,spans)])))
    q=[]
    for dev,entered,left in [('to_server',set(F),set(R)),('to_browser',set(R),set(rtt))]:
        a,b=[next(x for x in json.loads((d/f'qdisc-{phase}.json').read_text()) if x['kind']=='netem' and x['dev']==dev) for phase in ('before','after')];delta={key:b[key]-a[key] for key in ('packets','bytes','drops')};assert delta==dict(packets=len(left),bytes=len(left)*298,drops=len(entered-left));q.append(dict(dev=dev,entered=len(entered),drops=len(entered-left),loss_fraction=len(entered-left)/len(entered),formal_loss_series=label in loss_family))
    near_ties={str(radius):sum(abs(v-median)<=radius for v in rtt.values())/len(rtt) for radius in (0,.000001,.0001,.001)}
    rows.append(dict(label=label,sender=quality,process=diag,formal_process_series=label in formal,returned=len(rtt),rtt_quantiles=quantiles(list(rtt.values()),[0,.01,.05,.25,.49,.5,.51,.75,.95,.99,1]),median_neighborhood_fractions=near_ties,exploratory_rtt_acf=acf,five_second_windows=five,directional_losses=q))
previous=json.loads(Path('results/verify/readiness/stage4/calibration-poll0-v1/review/independent.json').read_text());result=dict(scope='Independent all14 sender/process and descriptive quantile/shape review; no bootstrap, no automatic review approval',run=str(run),commit=(run/'commit').read_text().strip(),seals_verified=len(seal),formal_process_series=list(formal),formal_loss_series=list(loss_family),sender_failed=[r['label'] for r in rows if r['sender']['status']!='passed'],formal_process_suspect=[r['label'] for r in rows if r['formal_process_series'] and r['process']['suspect']],broad_process_suspect=[r['label'] for r in rows if r['process']['suspect']],previous_formal_suspect=previous['formal_process_suspect'],previous_broad_suspect=previous['broad_process_suspect'],rows=rows,elapsed_s=time.monotonic()-started);print(json.dumps(result,indent=2))
