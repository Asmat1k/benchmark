import numpy as np

from calibration.calibration_blocks import process_diagnostics
from measurement.raw import read, require
from pathlib import Path
from calibration.sender_quality import evaluate, percentile


METHOD = 'observed-profile-check-v1'
CONTRACT = dict(method=METHOD, window_slots=500, loss_tolerance_pp=.5, shadow_phases=5,
                shadow_window_slots=1200, shadow_max_marked=12, sender_overdue_ms=50, deadline_ms=100)


def loss_fidelity(drops, count, target):
    return drops == 0 if target == 0 else count <= 200*drops <= 3*count


def rolling_counts(values):
    prefix = [0]
    for value in values:
        prefix.append(prefix[-1]+int(value))
    return [prefix[i+1200]-prefix[i] for i in range(len(values)-1199)]


def tail_summary(probe):
    replies = probe['reply_records']
    threshold = percentile([r['rtt_ms'] for r in replies], .99)
    tail = [r for r in replies if r['rtt_ms'] > threshold]
    def summary(rows):
        values = [r['rtt_ms'] for r in rows]
        return dict(n=len(values), median_ms=float(np.median(values)) if values else None,
                    mean_ms=float(np.mean(values)) if values else None,
                    p95_ms=percentile(values,.95) if values else None,
                    p99_ms=percentile(values,.99) if values else None, max_ms=max(values) if values else None)
    returned = {r['id'] for r in replies}
    return dict(p99_threshold_ms=threshold, all=summary(replies),
                body=summary([r for r in replies if r['rtt_ms'] <= threshold]), tail=summary(tail),
                tail_records=tail, tail_pct_returned=100*len(tail)/len(replies),
                tail_pct_planned=100*len(tail)/10000,
                missing_ids=[i for i in range(10000) if i not in returned])


def sender_check(probe, lossy):
    result = evaluate(probe['sent_records'], 10000, enforce_max_lag=False)
    result.update(criteria_version=METHOD, preliminary=False)
    result['limits'] = dict(result['limits'])
    result['limits'].pop('max_lag_ms')
    result['limits'].update(version=METHOD, min_spacing_ms=2.5, shadow_window_slots=1200, shadow_max_marked=12)
    phases = []
    replies = {r['id']:r['rtt_ms'] for r in probe['reply_records']}
    for phase in range(5):
        sends = probe['sent_records'][phase::5]
        overdue = [r['t_send_ms']-r['t_plan_ms'] >= 50 for r in sends]
        known = [late or (r['id'] in replies and r['t_send_ms']+replies[r['id']] > r['t_plan_ms']+100)
                 for late,r in zip(overdue,sends)]
        unknown = [not late and r['id'] not in replies for late,r in zip(overdue,sends)]
        counts = dict(sender_overdue=rolling_counts(overdue), known_timing_bad=rolling_counts(known),
                      unknown_reply=rolling_counts(unknown),
                      bad_if_all_unknown_bad=rolling_counts([a or b for a,b in zip(known,unknown)]))
        violations = [dict(start_phase_slot=i, start_id=sends[i]['id'], sender_overdue=counts['sender_overdue'][i],
                           known_timing_bad=counts['known_timing_bad'][i], unknown_reply=counts['unknown_reply'][i])
                      for i in range(801) if counts['sender_overdue'][i] > 12 or
                      (not lossy and (counts['known_timing_bad'][i] > 12 or counts['unknown_reply'][i] > 0))]
        phases.append(dict(phase=phase, denominator=1200, count_limit=12, counts=counts, violations=violations))
    if any(p['violations'] for p in phases):
        result['reasons'].append('observed shadow window budget or loss0 completeness violated')
    if result['metrics']['gap_ms']['min'] < 2.5-1e-8:
        result['reasons'].append('UDP sender minimum spacing < 2.5 ms')
    result.update(status='failed' if result['reasons'] else 'passed', shadow_phases=phases,
                  joint_deadline_complete=not lossy and len(replies)==10000,
                  missing_reply_count=10000-len(replies), tail=tail_summary(probe),
                  limitation='Observed 100Hz UDP proxy; loss1 joint counts are lower bounds, not complete deadline checks; no causal browser guarantee or maximum pause guarantee')
    return result


def observed_intervals(echo, review):
    require(read(Path('configs/plan.json'))['calibration'] == CONTRACT, 'fixed observed calibration contract')
    require(review.get('observed_period_reviewed') is True, 'explicit observed-period review required')
    bounds, diagnostics, windows = {}, {}, {}
    for label,probe in echo.items():
        values = np.full(10000, np.nan)
        for reply in probe['reply_records']:
            values[reply['id']] = reply['rtt_ms']
        diagnostics[label] = process_diagnostics(values)
        windows[label] = [dict(start_id=i, planned_count=500, returned_count=int(np.isfinite(values[i:i+500]).sum()),
                               median_ms=float(np.nanmedian(values[i:i+500])) if np.isfinite(values[i:i+500]).any() else None)
                          for i in range(0,10000,500)]
        medians = [w['median_ms'] for w in windows[label]]
        bounds[label] = [min(medians),max(medians)] if None not in medians else [None,None]
    return bounds, diagnostics, dict(method=METHOD, window_medians=windows,
        complete_windows=all(w['returned_count'] > 0 for rows in windows.values() for w in rows),
        limitation='Observed returned-RTT window range only; no confidence interval or future-process guarantee; ACF and drift are descriptive')
