from collections import Counter

import numpy as np

from reporting.inference import nearest_rank


# Run metrics.
def run_metrics(slots, events, resources, deadline, horizon):
    completed = [
        s
        for s in slots
        if s["first_correct_echo_ms"] is not None
        and s["first_correct_echo_ms"] <= s["t_plan_ms"] + horizon
    ]
    rtts = [s["first_correct_echo_ms"] - s["t_send_ms"] for s in completed]
    timely = sum(
        s["first_correct_echo_ms"] <= s["t_plan_ms"] + deadline for s in completed
    )
    n = len(slots)
    sent = sum(s["t_send_ms"] is not None for s in slots)
    counts = Counter(
        e["type"] for e in events if e["id"] is None or e["id"]["phase"] == 1
    )
    states = Counter(s["send_state"] for s in slots)
    lags = [s["send_lag_ms"] for s in slots if s["send_lag_ms"] is not None]
    result = dict(
        count_planned=n,
        sent=sent,
        unsent=n - sent,
        completed=len(completed),
        timely=timely,
        late_within=len(completed) - timely,
        uncompleted=n - len(completed),
        horizon_unknown=n - len(completed),
        Q_ms=nearest_rank(rtts, 0.95),
        p50_ms=nearest_rank(rtts, 0.5),
        p99_ms=nearest_rank(rtts, 0.99),
        Q_reason=None if rtts else "no_completed_echo",
        S_pct=100 * timely / n,
        U_pct=100 * (n - len(completed)) / n,
        penalized_p95_ms=nearest_rank(
            rtts + [float("inf")] * (n - len(completed)), 0.95
        ),
        duplicates=counts["duplicate"],
        invalid=counts["invalid_frame"] + counts["unknown_ID"],
        framing_errors=counts["framing_error"],
        disconnects=counts["disconnect"],
        api_errors=counts["api_error"],
        write_rejections=counts["write_rejection"],
        late_after_horizon=counts["late_after_horizon"],
        scheduler_miss=states["scheduler_miss"],
        backpressure_errors=states["local_backpressure_error"],
        p99_lag_ms=nearest_rank(lags, 0.99),
        queue_observations=sum(s["queue_before_bytes"] is not None for s in slots),
        max_queue_bytes=max(
            (
                s["queue_before_bytes"]
                for s in slots
                if s["queue_before_bytes"] is not None
            ),
            default=None,
        ),
    )
    for role in ("browser", "server", "router"):
        samples = [r for r in resources if r["role"] == role]
        result[f"{role}_cpu_max_one_core_pct"] = max(
            (100 * r["cpu_usage_usec"] / r["interval_usec"] for r in samples),
            default=None,
        )
        result[f"{role}_throttled_usec"] = sum(r["throttled_usec"] for r in samples)
        result[f"{role}_memory_peak_bytes"] = max(
            (r["memory_current"] for r in samples), default=None
        )
    return result, rtts


# Compute descriptive.
def descriptive(values):
    available = [v for v in values if v is not None]
    return dict(
        n=len(values),
        n_available=len(available),
        n_null=len(values) - len(available),
        values=values,
        median=float(np.median(available)) if available else None,
        iqr=np.quantile(available, [0.25, 0.75], method="linear").tolist()
        if available
        else None,
    )
