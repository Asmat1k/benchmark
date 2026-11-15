# Independent controlled-migration review

14November2026. Raw: results/verify/diagnostic/migration-causal.6itZemcx, two series r80p1-migrate and r80p1-fixed. No additional network collection, bootstrap, raw/seal edits or production edits. Independent raw trace parser executions each approximately2–3seconds with90second limits; exact initial commands, stdout/stderr and execution metadata retained here. This is a separate calculation within the Codex team, not external approval.

## Decision

The minimal **sender-only startup affinity** mitigation is justified for the demonstrated timer-service mechanism. This conclusion uses the natural migration observation plus both deliberate migrations and subsequent timer rebases; it does not rest only on the fixed candidate having clear process diagnostics. Pinning before the first network packet keeps the initial forward watchdog on the CPU already occupied by the poll0 sender, without another busy loop or more CPU allocation.

The simplified prediction that returning the sender immediately restores forward timing was wrong. Returning the sender initially strands the watchdog on the other CPU and creates another period of delay. The delay resolves after the watchdog itself rebases. Document that mixed prediction explicitly; do not call all stage4 problems fixed, hide A's sender failure, or substitute this experiment for source-bound qualification.

## Deliberate intervention and intermediate mechanism

Recorded actual masks: CPU0 atID0, CPU1 atID3000, CPU0 atID6000. Scheduling confirms the requested phases: sender residence CPU0/CPU1 approximately29981.199/.010ms, .009/29966.591ms and39975.064/0ms respectively. Affinity therefore changed where the sender ran; it did not directly pin the kernel timer.

Forward watchdog callback CPU sequence:

|Callback time from first forward queue|CPU|Count|
|---|---:|---:|
|.040258–36.142639s|0|3582|
|36.166246–68.652110s|1|3221|
|68.670160–100.032115s|0|3113|

The callback does not immediately follow either sender migration. During the middle senderCPU1 phase,613 callbacks still execute onCPU0 with median lateness2.806741ms and sampled-kernel-now lateness2.805891ms. After the watchdog rebases toCPU1,2363 callbacks have median lateness.002735ms while the sender remainsCPU1. During the final senderCPU0 phase,858 callbacks remainCPU1 with lateness1.872060ms and sampled-now lateness1.870975ms; after rebasingCPU0,3113callbacks have lateness.002640ms while sender remainsCPU0. No callbacks were excluded from these phase/CPU categories.

Forward residence medians in seconds30–35 are43.145/43.243/43.093/42.674/43.069/43.093ms; corresponding callback lateness2.912/2.913/2.912/2.528/2.826/2.780ms. Seconds36–39 return near40.245–40.249ms. Seconds60–67 again show42.094–42.172ms residence with1.852–1.931ms late callbacks. After rebasing, seconds69–72 return40.243–40.245ms and roughly.003ms callback lateness. Thus the late callback, not predominantly a deferred dequeue after timely callback, tracks the sustained residence regime.

These reversals identify sender/watchdog CPU co-location as a relevant condition for timely guest timer service. They do not prove CPU-idle, host-vCPU descheduling, a particular hypervisor defect, or the reason the watchdog rebases at those exact times. Kernel ABS_PINNED is per scheduling/rearm operation, not an immutable lifetime CPU assignment.

## Fixed candidate and negative evidence

FixedCPU0 series: all9921forward callbacks executeCPU0. Forward callback lateness median/p99 .003118/.011131ms; forward queue→xmit median/p99 40.244/40.257ms. All9802reverse callbacks executeCPU1. Sender occupies CPU0 approximately99955.517ms; no senderCPU1 residence during collection. These support the proposed low-cost mitigation.

Isolated stalls remain: fixed forward callback max24.005624ms, residence max64.364ms. Pinning does not eliminate all guest service delays. Independently read sent records confirm A maxlag50.531934ms in the middle phase; B maxlag25.876875ms. Primary assessment reports A sender/process failed and B sender/process passed; process diagnostics were not independently reimplemented in this review. Neither candidate qualification nor a future full calibration outcome is guaranteed.

Timer direction mapping is consistent for all19717starts in A and19723starts in B, using same-CPU next dequeue, including positive/bulk lookahead events. No contradictory pointer/direction mapping appears. All available timer pairs and all1s windows were retained. The phase summary bounds use recorded affinity timestamps, not selected favorable windows; the separate all-series summary includes the final drain. Common seeds are common-random-number controls, not independent loss realizations. Trace and server timing observation remain experimental load.

Outputs: per-series result.json and phase-summary.json; A timer-cpu-runs.json and colocation.json; source scripts and execution logs. No new numerical tolerance or cutoff was introduced.
