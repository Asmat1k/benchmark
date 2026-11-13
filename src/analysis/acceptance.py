import math

import numpy as np
from scipy.stats import beta, binom

from inference import bootstrap, nearest_rank, rank_interval
from raw import require
from schedule import MODES, PROFILES, block_runs, make_schedule, seeds


def exact_binomial(drops, count, confidence=.99):
    require(isinstance(count, int) and isinstance(drops, int) and 0 <= drops <= count and count > 0,
            "invalid binomial counts")
    tail = (1-confidence)/2
    return [0. if drops == 0 else float(beta.ppf(tail, drops, count-drops+1)),
            1. if drops == count else float(beta.ppf(1-tail, drops+1, count-drops))]


def dependence(values):
    values = np.asarray(values, dtype=float)
    require(len(values) >= 5 and np.isfinite(values).all(), "insufficient/nonfinite independent units")
    centered = values - np.mean(values)
    variance = float(centered @ centered) if np.ptp(values) > 0 else 0.
    lag1 = float(centered[:-1] @ centered[1:] / variance) if variance else 0.
    trend = float(np.polyfit(np.arange(len(values)), values, 1)[0])
    return dict(lag1=lag1, linear_trend_per_unit=trend,
                suspect=abs(lag1) > 2/math.sqrt(len(values)),
                limitation="diagnostic cannot establish independence; inspect traces and independent units")


def timer_gate(timer):
    require(timer['count'] == 100000, 'timer requires 100000 calls')
    return bool(timer['monotonic'] and timer['step_ms'] is not None and
                0 < timer['step_ms'] <= .1 and 0 <= timer['p99_overhead_ms'] <= .1)



def probe_records(probe):
    sent,reply=probe['sent_records'],probe['reply_records']
    require(len(sent)==10000 and len({r['id'] for r in sent})==10000, 'complete 10000 probe IDs required')
    start=sent[0]['t_plan_ms']
    for i,row in enumerate(sent):
        require(row['t_plan_ms']==start+i*10 and row['t_plan_ms']<=row['t_send_ms']<row['t_plan_ms']+10, '100Hz probe grid/send')
    require(len({r['id'] for r in reply})==len(reply) and {r['id'] for r in reply}<={r['id'] for r in sent}, 'probe reply IDs')
    require(all(math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in reply), 'probe RTT')
    return {r['id'] for r in sent},{r['id'] for r in reply}


def calibration(data):
    require(set(data['echo']) == {'before', 'after', *PROFILES}, 'calibration membership')
    intervals, diagnostics = {}, {}
    for key, probe in data['echo'].items():
        require(probe['sent'] == 10000 and probe['frame_bytes'] == 256 and probe['frequency_hz'] == 100,
                'calibration probe contract')
        probe_records(probe)
        require(probe['rtt_ms']==[r['rtt_ms'] for r in probe['reply_records']], 'survivor RTT correspondence')
        require(0 < len(probe['rtt_ms']) <= probe['sent'], 'echo survivor count')
        require(all(v >= 0 and math.isfinite(v) for v in probe['rtt_ms']), 'invalid RTT')
        ordered = sorted(probe['rtt_ms'])
        n = len(ordered)
        candidates = np.arange((n+1)//2+1)
        k = int(candidates[2*binom.cdf(candidates-1,n,.5) <= .025][-1])
        intervals[key] = [ordered[k-1],ordered[n-k]] if k else [-math.inf,math.inf]
        diagnostics[key] = dependence(probe['rtt_ms'])
    shifts = {}
    passed = True
    for profile in PROFILES:
        target = 20 if profile.startswith('r20') else 80
        shifts[profile] = {}
        for base in ('before', 'after'):
            low, high = intervals[profile][0]-intervals[base][1], intervals[profile][1]-intervals[base][0]
            shifts[profile][base] = [low, high]
            passed &= target-2 <= low <= high <= target+2
    loss = []
    require(len(data['egress']) == 16, 'four profiles, before/after, two egresses required')
    identities = set()
    for egress in data['egress']:
        identity = (egress['profile'], egress['when'], egress['direction'])
        require(identity not in identities and identity[0] in PROFILES and identity[1] in ('before','after') and
                identity[2] in ('forward','reverse'), 'egress membership')
        identities.add(identity)
        entered, dropped = egress['entered_ids'], egress['dropped_ids']
        require(len(entered) == len(set(entered)) and len(dropped) == len(set(dropped)) and
                set(dropped) <= set(entered), 'egress ID denominator')
        interval = exact_binomial(len(dropped), len(entered))
        p = .01 if egress['profile'].endswith('p1') else 0.
        okay = (len(dropped) == 0) if p == 0 else interval[0] <= p <= interval[1]
        loss.append(dict(identity=list(identity), CI99=interval, count=len(entered), drops=len(dropped), passed=okay))
        passed &= okay
    for profile in PROFILES:
        for when in ('before','after'):
            forward=next(e for e in data['egress'] if (e['profile'],e['when'],e['direction'])==(profile,when,'forward'))
            reverse=next(e for e in data['egress'] if (e['profile'],e['when'],e['direction'])==(profile,when,'reverse'))
            require(forward['collection_id']==reverse['collection_id'], 'egress paired collection')
            sent,returned=probe_records(forward['probe'])
            require(set(forward['entered_ids'])==sent, 'forward ingress probe completeness')
            require(set(reverse['entered_ids'])==sent-set(forward['dropped_ids']), 'reverse denominator must be actually delivered forward IDs')
            require(returned==set(reverse['entered_ids'])-set(reverse['dropped_ids']), 'impossible echo survivors/counters')
    require(len(data['saturation']) == 4, 'loss0/lossy in both directions required')
    require({(r['loss'],r['direction']) for r in data['saturation']} ==
            {(p,d) for p in (0,.01) for d in ('forward','reverse')}, 'saturation membership')
    for sample in data['saturation']:
        require(sample['duration_s'] >= 60 and sample['accounting_level'] and
                sample['offered_bytes'] >= sample['forwarded_bytes'] > 0, 'saturation accounting')
        rate = sample['forwarded_bytes']*8/sample['duration_s']/1e6
        sample['mbit_s'] = rate
        passed &= 9 <= rate <= 11
    require(data['trace_review']['independent_units'] in (True,False), 'independence assessment required')
    passed &= all(data['trace_review'][key] is True for key in
                  ('mtu_1500','no_fragmentation','no_unexpected_overflow','headers_accounted','survivor_bias_reviewed',
                   'reverse_denominator_reviewed','independent_direction_seeds','backlog_reviewed'))
    require(0 <= data['trace_review']['main_bandwidth_fraction'], 'negative bandwidth fraction')
    passed &= data['trace_review']['main_bandwidth_fraction'] < .1
    uncertain = not data['trace_review']['independent_units'] or any(d['suspect'] for d in diagnostics.values())
    return dict(status='inconclusive' if uncertain else 'passed' if passed else 'failed',
                intervals=intervals, shifts=shifts, dependence=diagnostics, loss=loss,
                saturation=data['saturation'], expected_echo_loss=.0199,
                survivor_bias='RTT intervals condition on returned echoes; loss0 and traces required')


def generator_gate(data):
    if any('mode' in r for r in data):
        require(sorted((r.get('mode', ''), r['frequency_hz']) for r in data) ==
                [('WS',20),('WS',100),('WT-S',20),('WT-S',100)], 'both modes at 20/100 Hz required')
    else:
        require({r['frequency_hz'] for r in data} == {20,100} and len(data) == 2, '20/100 Hz runs required')
    passed = True
    for run in data:
        slots=run['slots']
        require(len(slots)==run['measurement_slots'] and all(s['t_plan_ms']==slots[0]['t_plan_ms']+i*1000/run['frequency_hz'] for i,s in enumerate(slots)), 'generator frequency grid')
        require(run['miss']==sum(s['send_state']=='scheduler_miss' for s in slots), 'generator miss count')
        require(all((s['t_send_ms'] is not None)==(s['send_state'] in ('sent','local_api_error')) for s in slots), 'generator slot/send state')
        sent=[s for s in slots if s['t_send_ms'] is not None]
        passed &= len(sent)==len(slots) and all(s['send_state']=='sent' for s in slots)
        require(len(sent)>=2 and sent[-1]['t_send_ms']>sent[0]['t_send_ms'], 'generator send coverage')
        observed=(len(sent)-1)*1000/(sent[-1]['t_send_ms']-sent[0]['t_send_ms'])
        require(abs(observed-run['observed_hz'])<=1e-10 and all(s['t_send_ms'] is None or s['t_plan_ms']<=s['t_send_ms']<s['t_plan_ms']+1000/run['frequency_hz'] for s in slots), 'observed generator frequency')
        for key in ('lag_p99_ms','browser_cpu_pct_limit','server_cpu_pct_limit','browser_throttling_pct','server_throttling_pct','oom'):
            require(math.isfinite(run[key]) and run[key]>=0, 'negative/nonfinite generator observation')
        lags=[s['t_send_ms']-s['t_plan_ms'] for s in sent]
        require(run['lag_p99_ms']==nearest_rank(lags,.99), 'generator lag primary correspondence')
        samples=run['resource_samples']
        from resources import validate_resources
        require(run['resource_window']['end_usec']-run['resource_window']['start_usec'] >= len(slots)*1000000/run['frequency_hz'], 'generator load resource coverage')
        validate_resources(samples,run['resource_window'])
        require(run['oom']==sum(r['oom'] for r in samples), 'generator OOM correspondence')
        for role in ('browser','server'):
            role_samples=[r for r in samples if r['role']==role]
            require(all(r['cpu_limit']>0 and r['cpu_usage_usec']>=0 and r['throttled_usec']>=0 for r in role_samples), 'invalid CPU primary sample')
            cpu=max(100*r['cpu_usage_usec']/r['interval_usec']/r['cpu_limit'] for r in role_samples)
            throttle=100*sum(r['throttled_usec'] for r in role_samples)/sum(r['interval_usec'] for r in role_samples)
            require(abs(cpu-run[f'{role}_cpu_pct_limit'])<1e-10 and abs(throttle-run[f'{role}_throttling_pct'])<1e-10, 'generator resource correspondence')
        require(run['profile'] == 'baseline' and run['measurement_slots'] >= 1200, 'loss0 generator contract')
        require(run['resources_complete'] and run['router_backlog_reviewed'], 'generator coverage')
        passed &= run['miss'] == 0 and run['oom'] == 0
        passed &= all(run[f'{role}_cpu_pct_limit'] < 70 and run[f'{role}_throttling_pct'] < 1
                      for role in ('browser','server'))
        if run['frequency_hz'] == 20:
            passed &= run['lag_p99_ms'] <= 5 and abs(run['observed_hz']-20) <= .1
    return dict(status='passed' if passed else 'failed', runs=data)


def paired_schedule(kind, identity, datagrams=False, blocks=20):
    require(kind in ('aa','monitoring') and blocks >= 20, 'fixed minimum 20 pairs')
    schedule = make_schedule('verify', identity, blocks, 4, datagrams)
    rng = seeds('verify', identity, 8 if kind == 'aa' else 9)
    old = schedule['blocks']
    schedule['blocks'], schedule['runs'] = [], []
    for original in old:
        for mode in MODES if datagrams else MODES[:2]:
            index = len(schedule['blocks'])
            block = dict(original, block_id=f'b{index}', attempt_id=f'b{index}-a0', order_index=index,
                         modes=[mode,mode], design=kind)
            if kind == 'monitoring':
                block['monitoring_order'] = [str(v) for v in rng.permutation(["on","off"])]
            schedule['blocks'].append(block)
    schedule['blocks'] = [block for session in range(4) for block in rng.permutation([b for b in schedule['blocks'] if b['session_id']==f's{session}'])]
    for index,block in enumerate(schedule['blocks']):
        block['order_index'] = index
        schedule['runs'].extend(block_runs(schedule,block,index))
    return schedule


def equivalence(pairs, kind, identity, datagrams=False):
    require(kind in ('aa','monitoring'), 'unknown equivalence design')
    groups, shifts = [], []
    expected = {(m,p) for m in (MODES if datagrams else MODES[:2]) for p in PROFILES}
    require({(p['mode'],p['profile']) for p in pairs} == expected, 'equivalence group membership')
    require(len({p['attempt_id'] for p in pairs}) == len(pairs), 'duplicate pair')
    for index,(mode,profile) in enumerate(sorted(expected)):
        members = [p for p in pairs if (p['mode'],p['profile']) == (mode,profile)]
        require(len(members) >= 20, 'minimum 20 independent pairs')
        require(all(p['fresh_processes'] and p['independence_reviewed'] for p in members), 'pair independence/freshness')
        effects, fullness = [], []
        complete = True
        for pair in members:
            a,b = pair['sides']
            require(a['run_id'] != b['run_id'] and a['mode'] == b['mode'] == mode, 'pair sides')
            require(a['seeds'] == b['seeds'] if kind == 'monitoring' else a['seeds'] != b['seeds'], 'pair seeds')
            if kind == 'monitoring':
                require({a['monitoring'],b['monitoring']} == {True,False}, 'on/off order')
                if a['monitoring']: a,b = b,a
            effects.append(None if a['Q_ms'] is None or b['Q_ms'] is None else b['Q_ms']-a['Q_ms'])
            fullness.append(b['S_pct']-a['S_pct'])
            complete &= all(s['U_pct'] <= 1 and s['disconnects'] == 0 for s in (a,b))
        rng = seeds('verify',identity,10,index)
        indices = rng.integers(0,len(members),size=(10000,len(members)))
        q = rank_interval(effects)['bounds'] if None not in effects else None
        s = bootstrap(fullness,indices,.95)
        okay = q is not None and -2 <= q[0] <= q[1] <= 2 and -1 <= s['bounds'][0] <= s['bounds'][1] <= 1
        drift = dependence(fullness)
        q_drift = dependence(effects) if None not in effects else None
        okay &= not drift['suspect'] and q_drift is not None and not q_drift['suspect']
        status = 'failed' if not complete else 'passed' if okay else 'inconclusive'
        groups.append(dict(mode=mode,profile=profile,n=len(members),status=status, Q_CI95=q,S_CI95=s,
                           U_and_disconnects=[[(v['U_pct'],v['disconnects']) for v in p['sides']] for p in members],
                           bootstrap_indices=indices.tolist(), drift=drift, latency_dependence=q_drift))
        shifts.extend([qv,sv] for qv,sv in zip(effects,fullness) if qv is not None)
    status = 'failed' if any(g['status']=='failed' for g in groups) else 'inconclusive' if any(g['status']!='passed' for g in groups) else 'passed'
    return dict(status=status,groups=groups,shifts=shifts,
                repeat_effect_ms=max(2,float(np.percentile([abs(v[0]) for v in shifts],95))) if shifts else None,
                repeat_fullness_pp=max(1,float(np.percentile([abs(v[1]) for v in shifts],95))) if shifts else None)
