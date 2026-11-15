# Independent observer factorial review

2026-11-14. Internal independent subagent review of observer-only.qlyu4b08 after exit0. Recomputed all8phases directly from all three complete resource logs; no phase selected or removed. Derived values/input hashes are in results/verify/readiness/stage4/practical-v1/timer-diagnostic/independent-factorial-review.json. No production changes or additional measurements made.

Each phase has11complete nominal sampler intervals perrole. Sampler indices/timestamps are consecutive; retained rows show no OOM or throttling. The actual observed phase bounds are11.90–12.02s, reflecting boundary dockerexec time rather than a perfectly exact12s in VM uptime. This does not change the predetermined selection rule; all phases contribute.

## Queue observer contribution is clear

|Mean CPU percent, mean of both phase means|Q0R0|Q1R0|Q0R1|Q1R1|
|---|---:|---:|---:|---:|
|router|1.245|7.556|1.336|7.606|
|browser|0.892|0.694|0.934|0.858|
|server|0.794|0.644|0.946|0.713|

Router queue-probe effect is+6.311percentagepoints without readback and+6.270with readback. Both Q repetitions have means7.49–7.68%, whereas Q0 repeats have1.21–1.34%. Queue-phase router peaks22.30–24.10% versus control3.30–3.96%. Matched control retains dockerexec/shell/sleep; this supports additional cost of the tc/jq query sequence itself, rather than merely Docker exec launch.

The effect is specific to router accounting. Browser/server means decrease in Q1 conditions in this finite sequence; do not invent a positive Q effect on every role or claim a VM scheduling mechanism from this run.

## Readback contribution is smaller

R1 minus R0 mean effects at Q0/Q1 are browser+.042/+.163, server+.152/+.069, router+.092/+.050percentagepoints. Browser readback-phase peaks1.46–2.76% exceed most control peaks1.09–1.42%; individual phase means vary, notably browserQ0R1 repeats1.041/0.827%. This supports a modest observer/readback contribution, but does not isolate a fixed universal increment or prove the cause of historical browser1.138% excess. No independent-sample significance calculation is justified from these dependent/short intervals.

Even Q0 controls exceed router's initial sampler-only baseline mean0.849%, so the matched shell/marker procedure has its own cost. No-probe here means no tc/jq, not a completely observer-free process.

## Proposed timestamp and quiet-interval correction

Strict CPU timestamp brackets plus external-cgroup quiet markers are applicable to the demonstrated measurement issue. Baseline and idle must use the same sampler and complete-interval selection rule. CPU usage is read before other snapshot fields in sample.sh, while the existing interval timestamp is read later; a nominal interval boundary alone does not precisely locate the CPU counter read. Record bounds immediately before/after each actual CPU counter snapshot. Accept an interval as quiet only if its entire possible counter-to-counter span fits inside the declared quiet window: the earlier snapshot's earliest bound is at/after quiet start and the later snapshot's latest bound is at/before quiet end.

Capture quiet start/end from a process outside the measured cgroup using the same VM clock as sampler brackets. A dockerexec marker inside the measured cgroup would itself contaminate the interval it declares quiet. Validate clock-domain equivalence explicitly, including any container time namespace offsets; do not subtract Mac monotonic time from Linux uptime.

Run expensive queue probes before the quiet interval, then require a full fresh CPU interval inside the window. Apply the same baseline observation procedure. Keep the existingceil CPU comparison,30s deadline,1s empty-queue requirement and all raw resource rows. Selected quiet intervals must be explicit in acceptance evidence; boundary/probe intervals stay in raw and resource diagnostics. Do not use quiet selection to remove actual workload or CPU tails from main scientific metrics. Missing/malformed brackets, no complete interval, stale sampler, residual sustained CPU or actual queue activity must still reject.

This corrects an identified observer/measurement problem without expanding CPU budget. It does not guarantee that a new timer passes: true idle variability can still cross the unchanged ceiling. A failed fixed validation must remain failed rather than trigger retries until a favorable sample occurs. The evidence provides a concrete reason to fix the observer; it provides no reason for a broad VM-jitter elimination campaign or stopping the unrelated qdrant container.
