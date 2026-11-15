import hashlib
import math

import numpy as np
from pathlib import Path

from measurement.raw import read, require


METHOD = 'circular-block-medians-v1'
BLOCK_SLOTS = (100, 200, 500)
REPLICATES = 20000
LATENCY_ALPHA = .04
LOSS_ALPHA = .01
SEED = 20261113


def bootstrap_interval(values, block_slots, seed, replicates=REPLICATES):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    require(len(finite) > 0, 'no returned RTT')
    if len(finite) == len(values) and np.ptp(finite) == 0:
        return [float(finite[0]), float(finite[0])]
    rng = np.random.Generator(np.random.PCG64(seed))
    estimates = []
    blocks = math.ceil(len(values)/block_slots)
    for offset in range(0, replicates, 32):
        starts = rng.integers(0, len(values), (min(32, replicates-offset), blocks))
        indexes = (starts[:, :, None]+np.arange(block_slots)) % len(values)
        sample = values[indexes.reshape(len(starts), -1)[:, :len(values)]]
        if np.any(np.all(np.isnan(sample), axis=1)):
            return [None, None]
        estimates.extend(np.nanmedian(sample, axis=1).tolist())
    tail = LATENCY_ALPHA/6/2
    return np.quantile(estimates, [tail, 1-tail], method='inverted_cdf').tolist()


def process_diagnostics(values):
    values = np.asarray(values, dtype=float)
    available = np.isfinite(values)
    require(available.any(), 'no returned RTT')
    series = dict(survival=available.astype(float), rtt=np.where(available, values, np.nanmedian(values)))
    result = {}
    suspect = False
    for label, ordered in series.items():
        centered = ordered-np.mean(ordered)
        variance = float(centered @ centered)
        correlations = {str(lag): float(centered[:-lag] @ centered[lag:]/variance) if variance else 0.
                        for lag in (500, 1000, 2000)}
        flagged = any(abs(value) > 3.5/math.sqrt(len(values)-int(lag)) for lag, value in correlations.items())
        result[label] = dict(long_lag=correlations, suspect=flagged)
        suspect |= flagged
    chunks = [float(np.nanmedian(v)) if np.isfinite(v).any() else None for v in np.array_split(values, 20)]
    complete = all(v is not None for v in chunks)
    drift = float(np.polyfit(np.arange(20), chunks, 1)[0]*19) if complete else None
    return dict(**result, chunk_medians_ms=chunks, fitted_drift_ms=drift,
                suspect=bool(suspect or not complete or abs(drift) > 2),
                limitation='Diagnostics can reject assumptions; absence of flags does not establish stationarity or short memory')


def intervals(echo, review):
    configured = read(Path('configs/plan.json'))['calibration']
    from calibration.calibration_observed import CONTRACT as observed_contract
    require(configured == observed_contract or configured == dict(method=METHOD, block_slots=list(BLOCK_SLOTS), replicates=REPLICATES,
                              latency_alpha=LATENCY_ALPHA, loss_alpha=LOSS_ALPHA, seed=SEED),
            'fixed calibration method contract')
    require(all(type(review.get(key)) is bool for key in ('stationarity_reviewed', 'short_memory_reviewed', 'bernoulli_loss_reviewed')),
            'dependent process review required')
    bounds, diagnostics, details = {}, {}, {}
    for label in sorted(echo):
        probe = echo[label]
        require({r['id'] for r in probe['sent_records']} == set(range(10000)), 'ordered calibration slot IDs')
        values = np.full(10000, np.nan)
        for reply in probe['reply_records']:
            values[reply['id']] = reply['rtt_ms']
        diagnostics[label] = process_diagnostics(values)
        estimates = []
        seeds = []
        for block in BLOCK_SLOTS:
            seed = int.from_bytes(hashlib.sha256(f'{SEED}:{label}:{block}'.encode()).digest()[:8], 'big')
            seeds.append(seed)
            estimates.append(bootstrap_interval(values, block, seed))
        valid = all(bound[0] is not None for bound in estimates)
        bounds[label] = [min(b[0] for b in estimates), max(b[1] for b in estimates)] if valid else [-math.inf, math.inf]
        diagnostics[label]['suspect'] |= not valid
        details[label] = dict(block_intervals=estimates, seeds=seeds, median_ms=float(np.nanmedian(values)))
    uncertain = not all(review[k] for k in ('stationarity_reviewed', 'short_memory_reviewed', 'bernoulli_loss_reviewed')) or any(
        d['suspect'] for d in diagnostics.values())
    return bounds, diagnostics, dict(method=METHOD, replicates=REPLICATES, block_slots=list(BLOCK_SLOTS),
        latency_alpha=LATENCY_ALPHA, loss_alpha=LOSS_ALPHA, details=details,
        limitation='Approximate percentile intervals under stationary short-memory joint RTT/survival processes; no finite-sample coverage guarantee'), uncertain
