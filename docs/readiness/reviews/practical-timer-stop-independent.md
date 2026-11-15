# Independent investigation: practical timer stabilization STOP

2026-11-14. Read-only internal review of timer-timer.osubQW8s/quarantine/wswt-d3-wswt-measure-gxx9wylj and practical-v1/release/timer-execution.mrs87y9r. No retry, network measurement or production modification performed.

## Concrete trigger

Collection command exited1 after59.30s; it did not hit its130s wrapper limit. The shell reaches `test "$stable" = 1` after the30s stabilization deadline. `measure.sh` compares each role's latest fresh sample, rounded upward to integral CPU percent, against that role's maximum baseline sample rounded the same way. Baseline contains three approximately1s samples per role. Only the final idle sample is saved: every loop overwrites `ROLE-idle.jsonl`.

Final retained values reproduce a real rejection:

| Role | Baseline maximum CPU | Baseline ceiling | Final idle CPU | Idle ceiling | CPU predicate |
|---|---:|---:|---:|---:|---|
|browser|0.945940594%|1|1.137722772%|2|failed|
|server|1.052352941%|2|1.078217822%|2|passed|
|router|0.928712871%|1|0.659200000%|1|passed|

Thus the last browser CPU comparison alone prevents stable=true. Deadline expiry can also force stable=0; the original logs do not preserve each attempt's predicate/timestamp, so the entire attempt history cannot be reconstructed exactly. The generic STOP text incomplete_log/OOM/orchestration is the quarantine category, not evidence of actual OOM. All three sampler-error files are empty. Retained resource rows have zero OOM/throttled_usec,49samples perrole. qdisc-after has zero backlog/qlen/drops for both netem directions. No qdisc-stable/stabilization.json exists, correctly, and no accepted raw was published.

The first selected short timer run is WT-S, not an ordinary1200slot generator run: warmup1, measurement3. Presence of clock-samples.json does not mean timer gate passed; publication prerequisites failed.

## Measurement procedure issue

There is no src/analysis/stabilize.py in this repository. Stabilization lives inline in docker/measure.sh. Baseline is collected after sampler startup, while stabilization repeatedly invokes11 tc+jq reads at100ms spacing on router, sleeps2s, then invokes fresh-sample checks on all roles. These operations are part of the same cgroups whose idle CPU is being compared to a baseline without the repeated stabilization probes.

Retained router full samples show a repeating stabilization-time CPU pulse, e.g. samples30/34/38/42 at24.833/25.833/25.630/25.562%; baseline max0.929%. Browser samples also repeat approximately4s patterns, including1.604/1.602/1.757/1.702/1.757% at samples30/33/37/41/45. The shell's probes have enough work to perturb idle observations; the pattern is consistent with observer overhead. This is an inference from code and resource traces, not a causal experiment proving every browser increment comes from the observer. The final browser increment is real in the recorded accounting and must not be rounded away by adding a fitted tolerance.

This timer does not enable collect-backlog, so the prior fix moving backlog observer before baseline does not address this case. The transient timer/browser activity itself peaks104.804% CPU at sample5, but by the retained final samples the failed bound is the low baseline ceiling1 versus observed ceiling2; no sustained near-capacity residual browser workload is demonstrated.

## Minimal next work

Preserve STOP/raw and do not repeat unchanged until one passes. First make stabilization failures inspectable: save every attempt's queue-test start/end/result, CPU sample IDs/times, baseline ceilings, per-role predicate and deadline result instead of overwriting idle-only evidence. Do not change scientific Q/S/U or inflate CPU limits.

Then test the observer effect with a small deterministic shell/mock regression before another network attempt: establish whether the currently unmatched baseline/idle probe sequence rejects an otherwise identical idle process, and verify that a matched observation sequence passes while actual sustained excess CPU and nonempty queue still fail. A minimal production fix should match baseline and post-run CPU observation procedures and use complete sampler intervals after the expensive queue probe, keeping the existing30s bound and queue requirement. The exact scheduling change must be fixed before new data; do not choose a new CPU percentage to admit1.138%.

If the mock/code inspection cannot distinguish observer overlap from unexplained residual browser CPU, use one prospectively fixed short observer-only diagnostic (no science data) that records operation timestamps and all resource rows, comparing matched probe/no-probe phases. No need for a full calibration to diagnose this. New source/measurement behavior will require a new source-bound release/applicability review and fresh early checks; this STOP remains historical failed.
