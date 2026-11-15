import json
import math
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def policy():
    return json.loads((ROOT/'configs/thresholds.json').read_text())['udp_sender']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values)*fraction)-1]


def window_peak(times, width):
    times = [Decimal(str(time)) for time in times]
    width = Decimal(str(width))
    left = 0
    peak = 0
    for right, time in enumerate(times):
        while times[left] <= time-width:
            left += 1
        peak = max(peak, right-left+1)
    return peak


def evaluate(records, expected_count, enforce_max_lag=True):
    limits = policy()
    require(isinstance(expected_count, int) and expected_count >= 2 and len(records) == expected_count,
            'UDP sender incomplete send records')
    require([r['id'] for r in records] == list(range(expected_count)), 'UDP sender ordered complete IDs')
    require(all(type(r[k]) in (int, float) and math.isfinite(r[k])
                for r in records for k in ('t_plan_ms', 't_send_ms')), 'UDP sender nonfinite timestamps')
    start = records[0]['t_plan_ms']
    times = [r['t_send_ms'] for r in records]
    require(all(r['t_plan_ms'] == start+i*10 for i,r in enumerate(records)), 'UDP sender 100Hz plan grid')
    require(all(a <= b for a,b in zip(times, times[1:])), 'UDP sender clock/order')
    lags = [r['t_send_ms']-r['t_plan_ms'] for r in records]
    require(min(lags) >= 0, 'UDP sender early send')
    late = [v >= 10 for v in lags]
    gaps = [b-a for a,b in zip(times, times[1:])]
    groups = []
    for i, value in enumerate(late):
        if value:
            if i == 0 or not late[i-1]:
                groups.append([])
            groups[-1].append(i)
    metrics = dict(count=expected_count, late_slots=sum(late), late_pct=100*sum(late)/expected_count,
                   lag_ms=dict(p50=percentile(lags,.5), p99=percentile(lags,.99), max=max(lags)),
                   gap_ms=dict(min=min(gaps), p50=percentile(gaps,.5), p99=percentile(gaps,.99), max=max(gaps)),
                   late_groups=groups, late_group_count=len(groups),
                   peak_packets_1ms=window_peak(times,1),
                   peak_packets_window=window_peak(times,limits['burst_window_ms']),
                   observed_hz=(expected_count-1)*1000/(times[-1]-times[0]) if times[-1]>times[0] else None)
    reasons = []
    if metrics['late_pct'] > limits['max_late_pct']:
        reasons.append(f"late slots {metrics['late_pct']:.6g}% > {limits['max_late_pct']}%")
    if enforce_max_lag and max(lags) > limits['max_lag_ms']:
        reasons.append(f"maximum lag {max(lags):.6g} ms > {limits['max_lag_ms']} ms")
    if metrics['peak_packets_window'] > limits['max_burst_packets']:
        reasons.append(f"burst {metrics['peak_packets_window']} packets/{limits['burst_window_ms']} ms > {limits['max_burst_packets']}")
    return dict(criteria_version=limits['version'], preliminary=True, status='failed' if reasons else 'passed',
                reasons=reasons, limits=limits, historical_every_slot_pass=not any(late), metrics=metrics)


def assess(records, expected_count):
    try:
        return evaluate(records, expected_count)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return dict(criteria_version=policy()['version'], status='inconclusive', reasons=[str(error)])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('probe', type=Path)
    parser.add_argument('--count', type=int, required=True)
    args = parser.parse_args()
    result = assess(json.loads(args.probe.read_text())['sent_records'], args.count)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result['status']=='passed' else 1 if result['status']=='failed' else 2)
