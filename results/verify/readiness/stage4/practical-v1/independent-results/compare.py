import collections
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

from calibration_observed import sender_check, observed_intervals


BASE = Path('results/verify/readiness/stage4/practical-v1/independent-results')
SHADOW = Path('results/verify/readiness/stage4/imperfection-policy-v1/sensitivity/shadow.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sliding(values):
    queue = collections.deque()
    total = 0
    result = []
    for value in values:
        queue.append(int(value))
        total += int(value)
        if len(queue) > 1200:
            total -= queue.popleft()
        if len(queue) == 1200:
            result.append(total)
    return result


sources = ['src/analysis/calibration_observed.py', 'src/analysis/sender_quality.py',
           'src/analysis/calibration_blocks.py', 'configs/plan.json', 'configs/thresholds.json',
           str(SHADOW), 'results/verify/readiness/stage4/imperfection-policy-v1/sensitivity/shadow.py',
           str(BASE/'compare.py')]
source_hashes = {path: digest(path) for path in sources}
discrepancies = []
runs = []
seal_count = 0
window_count = 0
for old_run in json.loads(SHADOW.read_text())['runs']:
    run = Path(old_run['run'])
    refs = json.loads((run/'captured.json').read_text())
    for ref in refs:
        assert digest(ref['path']) == ref['sha256'], ref
    seal_count += len(refs)
    rows = []
    echo = {}
    for old in old_run['series']:
        probe = json.loads((run/old['name']/'probe.json').read_text())
        lossy = 'p1-' in old['name']
        actual = sender_check(probe, lossy)
        reply = {r['id']:Decimal(str(r['rtt_ms'])) for r in probe['reply_records']}
        phases = []
        for phase in range(5):
            points = [r for r in probe['sent_records'] if r['id'] % 5 == phase]
            lag = [Decimal(str(r['t_send_ms']))-Decimal(str(r['t_plan_ms'])) >= 50 for r in points]
            known = [late or (r['id'] in reply and Decimal(str(r['t_send_ms']))+reply[r['id']] >
                              Decimal(str(r['t_plan_ms']))+100) for late,r in zip(lag,points)]
            unknown = [not late and r['id'] not in reply for late,r in zip(lag,points)]
            independent = dict(sender_overdue=sliding(lag), known_timing_bad=sliding(known),
                               unknown_reply=sliding(unknown),
                               bad_if_all_unknown_bad=sliding([a or b for a,b in zip(known,unknown)]))
            for metric, counts in independent.items():
                if counts != actual['shadow_phases'][phase]['counts'][metric]:
                    discrepancies.append(dict(run=str(run), series=old['name'], phase=phase, metric=metric,
                        windows=[i for i,(a,b) in enumerate(zip(counts,actual['shadow_phases'][phase]['counts'][metric])) if a!=b]))
                if max(counts) != old['phases'][phase]['max_'+metric]:
                    discrepancies.append(dict(run=str(run), series=old['name'], phase=phase,
                                               metric=metric, old_max=old['phases'][phase]['max_'+metric], new_max=max(counts)))
            window_count += len(independent['sender_overdue'])
            phases.append(dict(phase=phase, counts=independent))
        if actual['missing_reply_count'] != old['missing']:
            discrepancies.append(dict(run=str(run), series=old['name'], metric='missing'))
        rows.append(dict(name=old['name'], lossy=lossy, exploratory_sender_status=actual['status'],
            reasons=actual['reasons'], missing_reply_count=actual['missing_reply_count'],
            joint_deadline_complete=actual['joint_deadline_complete'], phases=phases))
        if old['name'].endswith('-latency'):
            echo[old['name'].removesuffix('-latency')] = probe
        elif old['name'] in ('baseline-before','baseline-after'):
            echo[old['name'].removeprefix('baseline-')] = probe
    bounds, diagnostics, observed = observed_intervals(echo, dict(observed_period_reviewed=True))
    for name,probe in echo.items():
        reply = {r['id']:r['rtt_ms'] for r in probe['reply_records']}
        for start in range(0,10000,500):
            values = [reply[i] for i in range(start,start+500) if i in reply]
            actual = observed['window_medians'][name][start//500]
            if actual['median_ms'] != statistics.median(values) or actual['returned_count'] != len(values):
                discrepancies.append(dict(run=str(run), series=name, window=start, metric='median'))
    runs.append(dict(run=str(run), sealed_inputs=len(refs), series=rows, observed_window_bounds=bounds))

synthetic = []
for pause in (499,500):
    previous = -10
    sends = []
    for i in range(10000):
        actual = max(i*10+(pause if i==5000 else 0),previous+2.5)
        sends.append(dict(id=i,t_plan_ms=i*10,t_send_ms=actual))
        previous = actual
    result = sender_check(dict(sent_records=sends,reply_records=[dict(id=i,rtt_ms=.6) for i in range(10000)]),False)
    maxima = [max(p['counts']['known_timing_bad']) for p in result['shadow_phases']]
    expected = [13,12,12,12,12] if pause==500 else [12]*5
    if maxima != expected or (result['status']=='failed') != (pause==500):
        discrepancies.append(dict(synthetic_pause_ms=pause, actual=maxima, expected=expected))
    synthetic.append(dict(kind='synthetic_counterexample_not_measurement',pause_ms=pause,maxima=maxima,
                          status=result['status'],reasons=result['reasons']))
assert all(digest(path)==value for path,value in source_hashes.items()), 'source changed during review'
derived = dict(status='exploratory_independent_results_comparison',confirmatory=False,
               historical_reports_modified=False,method='Decimal predicates, deque rolling counts, statistics.median',
               source_sha256=source_hashes,sealed_inputs=seal_count,collections=sum(len(r['series']) for r in runs),
               phase_windows=window_count,discrepancies=discrepancies,runs=runs,synthetic=synthetic)
with (BASE/'derived.json').open('x') as out:
    json.dump(derived,out,indent=2,allow_nan=False)
    out.write('\n')
print(json.dumps({k:derived[k] for k in ('status','collections','sealed_inputs','phase_windows','discrepancies','synthetic')},indent=2))
raise SystemExit(bool(discrepancies))
