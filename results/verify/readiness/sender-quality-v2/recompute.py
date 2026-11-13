import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/analysis'))
from sender_quality import assess, percentile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return dict(mean=sum(values)/len(values),p50=percentile(values,.5),p95=percentile(values,.95),
                p99=percentile(values,.99),max=max(values))


def queue(times, service):
    end=0
    waits=[]
    for t in times:
        waits.append(max(0,end-t))
        end=max(t,end)+service
    return waits


result={}
for run in sorted((ROOT/'results/verify/diagnostic').iterdir()):
    probes=sorted(run.glob('*/probe.json'))
    probes=[p for p in probes if 'sent_records' in json.loads(p.read_text())]
    if not probes: continue
    inventory={str(p.relative_to(ROOT)):digest(p) for p in run.rglob('*') if p.is_file()}
    source_files=[run/f'sources-{when}.json' for when in ('before','after')]
    sources_stable=(json.loads(source_files[0].read_text())==json.loads(source_files[1].read_text())) if all(p.exists() for p in source_files) else None
    seal=run/'captured.json'
    integrity=None
    if seal.exists():
        entries=json.loads(seal.read_text())
        integrity=all((ROOT/r['path']).is_file() and digest(ROOT/r['path'])==r['sha256'] for r in entries)
        if not integrity: raise ValueError('raw seal mismatch: '+str(run))
    for p in probes:
        d=json.loads(p.read_text()); rows=d['sent_records']; n=10000 if run.name.startswith('calibration.') or p.parent.name.startswith('baseline-q') else 1500
        quality=assess(rows,n)
        replies=d['reply_records']; ids=[r['id'] for r in replies]
        valid=len(ids)==len(set(ids)) and set(ids)<=set(range(n)) and all(math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in replies)
        times=[r['t_send_ms'] for r in rows]; lags=[r['t_send_ms']-r['t_plan_ms'] for r in rows]
        rtts=[r['rtt_ms'] for r in replies]
        models=[]
        for rate in (9,10):
            actual=queue(times,298*8/rate/1000)
            ideal=queue([r['t_plan_ms'] for r in rows],298*8/rate/1000)
            models.append(dict(rate_mbit_s=rate,extra_two_direction_wait_ms=summary([2*(a-b) for a,b in zip(actual,ideal)])))
        sensitivity={}
        for fraction in (.005,.01,.02):
            sensitivity[str(fraction)]=dict(p95_rank_envelope_ms=[percentile(rtts,.95-fraction),percentile(rtts,.95+fraction)],
                                           mean_if_affected_add_50ms=fraction*50)
        fast=[]
        for i in range(len(times)-1):
            if times[i+1]-times[i]<1:
                if not fast or fast[-1][-1]!=i: fast.append([i])
                fast[-1].append(i+1)
        result[str(p.relative_to(ROOT))]=dict(sender_quality=quality,seal_verified=integrity,sources_stable=sources_stable,
            collector_exit=(run/'exit').read_text().strip() if (run/'exit').exists() else None,
            reply_ids_valid=valid,replies=len(replies),rtt_ms=summary(rtts),queue_models=models,
            fast_groups=[dict(ids=g,count=len(g),span_ms=times[g[-1]]-times[g[0]]) for g in fast],
            sensitivity=sensitivity,lag_rtt_mean_difference_ms=(sum(r['rtt_ms'] for r in replies if lags[r['id']]>=10)/sum(l>=10 for l in lags)
                -sum(r['rtt_ms'] for r in replies if lags[r['id']]<10)/sum(l<10 for l in lags)) if any(l>=10 for l in lags) else None)
    assert inventory=={str(p.relative_to(ROOT)):digest(p) for p in run.rglob('*') if p.is_file()}
output=dict(criteria_version='udp-sender-v2',diagnostic_only=True,
    limitations='FCFS fixed 298B frames, constant 9/10Mbit service, double one-link wait; not a netem/transport model. Rank envelopes assume at most the specified fraction of arbitrary contaminated responses, not established by late fraction. No causal tracing comparison.',
    collections=result)
Path(__file__).with_name('evaluation.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
