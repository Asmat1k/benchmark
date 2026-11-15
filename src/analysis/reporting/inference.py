import math

import numpy as np
from scipy.stats import binom


def nearest_rank(values, quantile):
    ordered = sorted(values)
    return ordered[math.ceil(quantile * len(ordered)) - 1] if ordered else None


def sign_test(values):
    n = len(values)
    positive = sum(d > 0 for d in values)
    negative = sum(d < 0 for d in values)
    return dict(n=n, Nplus=positive, Nminus=negative, Nzero=n-positive-negative,
                p_raw=float(min(1, 2 * min(binom.sf(positive-1, n, .5), binom.sf(negative-1, n, .5)))))


def holm4(values):
    if len(values) != 4:
        raise ValueError("Holm requires all four profiles")
    result = [0.] * 4
    previous = 0.
    for rank, index in enumerate(sorted(range(4), key=lambda i: (values[i], i))):
        previous = min(1., max(previous, (4-rank)*values[index]))
        result[index] = previous
    return result


def rank_interval(values, alpha=.05):
    ordered = sorted(values)
    n = len(ordered)
    k = max(k for k in range((n+1)//2+1) if 2*binom.cdf(k-1, n, .5) <= alpha)
    return dict(bounds=[ordered[k-1] if k else -math.inf, ordered[n-k] if k else math.inf],
                ranks=[k, n-k+1], n=n, confidence=1-alpha,
                binomial_coverage=float(1-2*binom.cdf(k-1, n, .5)))


def bootstrap(values, indices, confidence=.9875, statistic="mean"):
    values = np.asarray(values, dtype=np.float64)
    if len(values) == 0 or indices.ndim != 2 or indices.shape[1] != len(values):
        raise ValueError("bootstrap requires complete blocks")
    if indices.dtype.kind not in "iu" or np.any(indices < 0) or np.any(indices >= len(values)):
        raise ValueError("invalid bootstrap block index")
    estimate = np.mean if statistic == "mean" else np.median
    resampled = estimate(values[indices], axis=1)
    tail = (1-confidence)/2
    return dict(estimate=float(estimate(values)), bounds=np.quantile(resampled, [tail, 1-tail], method="linear").tolist(),
                confidence=confidence, statistic=statistic, replicates=len(indices), unit="independent_block")


def decisions(interval, fullness, p_adjusted, available, complete, thresholds):
    if not available:
        practical, statistical = "unavailable", "unavailable"
    else:
        low, high = interval
        margin = thresholds["practical_ms"]
        practical = ("WT-S" if high < -margin else "WS" if low > margin else
                     "small_difference" if low >= -margin and high <= margin else "uncertain")
        statistical = "reject" if p_adjusted < .05 else "not_reject"
    tolerance = thresholds["fullness_tolerance_pp"]
    fullness_ok = (practical == "WT-S" and fullness[0] >= -tolerance or
                   practical == "WS" and fullness[1] <= tolerance)
    return dict(statistical_decision=statistical, practical_decision=practical,
                completeness_gate="passed" if complete else "failed", validity_gate="passed",
                useful_gain=practical if complete and available and fullness_ok and statistical == "reject" else None,
                conclusion_status="unavailable" if not available else "limited" if not complete else "available")
