import json
import math
from pathlib import Path
import signal
import statistics
import sys
import time

signal.alarm(90)
started = time.monotonic()
sys.path.insert(0, 'src/analysis')
from sender_quality import evaluate

labels = ('baseline-before', 'r20p0-before', 'r20p1-before', 'r80p0-before', 'r80p1-before', 'r20p0-latency', 'r20p1-latency', 'r80p0-latency', 'r80p1-latency', 'r20p0-after', 'r20p1-after', 'r80p0-after', 'r80p1-after', 'baseline-after')
formal = ('baseline-before', 'r20p0-latency', 'r20p1-latency', 'r80p0-latency', 'r80p1-latency', 'baseline-after')


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


def inspect(root, label):
    probe = json.loads((root/label/'probe.json').read_text())
    quality = evaluate(probe['sent_records'], 10000)
    metrics = quality['metrics']
    lags = [row['t_send_ms']-row['t_plan_ms'] for row in probe['sent_records']]
    maximum = max(lags)
    return dict(label=label, sender_status=quality['status'], sender_reasons=quality['reasons'], late_pct=metrics['late_pct'], lag=metrics['lag_ms'], maximum_lag_ids=[i for i, value in enumerate(lags) if value == maximum], peak_packets_window=metrics['peak_packets_window'], replies=len(probe['reply_records']), rtt_median_ms=statistics.median(probe['rtt_ms']), process=process(probe))


root = Path('results/verify/diagnostic/calibration.gIdWLx7o')
rows = [inspect(root, label) for label in labels]
historical = [inspect(Path('results/verify/diagnostic/calibration.lShojabe'), label) for label in ('baseline-before', 'r20p0-latency', 'r20p0-after', 'r20p1-after')]
print(json.dumps(dict(scope='Independent all14 sender and stdlib equivalent process diagnostics; no bootstrap or review flags', new=rows, historical_comparison=historical, sender_failed=[r['label'] for r in rows if r['sender_status'] != 'passed'], broad_process_suspect=[r['label'] for r in rows if r['process']['suspect']], formal_process_labels=list(formal), formal_process_suspect=[r['label'] for r in rows if r['label'] in formal and r['process']['suspect']], elapsed_s=time.monotonic()-started), indent=2))
