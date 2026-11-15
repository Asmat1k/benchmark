# Review of controlled migration and fixed-sender candidate

14 November2026. Read-only source/plan review, no experiments launched by this reviewer. Parent reports new watchdog raw shows sender predominantlyCPU0, but seconds24/25 execute senderCPU1 while forward timer staysCPU0: callback lateness≈1.883/1.958ms, queue residence≈42.125/42.173ms. SenderCPU0 before/after has callback lateness≈.003ms; reverse timerCPU1 remains timely. These numbers are supplied by parent's analyzer, not independently recomputed here.

## Why the timer can stay on the old CPU

Source-supported chain: qdisc_watchdog schedules NET_TX through per-CPU softnet_data. That CPU then dequeues the head and schedules the next queue-head watchdog. The pinned timer therefore rearms on the same CPU. New arrivals on the sender's new CPU need not move it: when they request the unchanged already-pending head expiry, qdisc_watchdog_schedule_range_ns(delta0) returns without restarting the timer. At100Hz and40ms+serialization, arrivals can regularly precede the next head deadline, preserving this cycle. This is a plausible persistent mechanism, rather than one40ms transient following migration. It remains an inference until trace shows the actual sequence.

Sources: [qdisc watchdog](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_api.c), [per-CPU NET_TX enqueue](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/core/dev.c), [netem head deadline](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c).

## Proposed A/B is distinct and justified

A:10000echo initiallyCPU0, move atID3000 toCPU1, return atID6000 toCPU0. B:10000echo fixedCPU0. Same r80p1 seeds and existing timing/payload/ID rules, trace both timers and sender. Whole budget270+10s. This explicitly intervenes on the mechanism with reversibility inside A; B validates the low-cost candidate without adding another busy CPU. It is not an unchanged retry of prior affinityABBA.

Predeclare causal criteria, not a newly tuned acceptance threshold:

- Verify initial forward timer actually starts onCPU0, sender actually executes requestedCPU throughout each assigned section, and callback timer pointer/direction mapping remains sound. Otherwise intervention semantics are invalid/inconclusive.
- Retain all packets, including migration boundaries and all tails. Show all prespecified1s/5s windows. Kernel trace must show whether the forward timer remainedCPU0 during senderCPU1, whether its callback became late, and whether lateness reverses when sender returnsCPU0.
- Do not require intentionally forced A to be processclear: its role is to reproduce sensitivity. Its expected mean shift is not a qualification result. B must pass unchanged sender-v2 AND full10000-sample process diagnostics, ID/tag/capture/timer loss checks.
- If A does not reproduce the predicted timer/CPU/lateness sequence, or B retains processsuspect, do not declare the fix established. No automatic retries under this plan.
- Report setaffinity call boundary overhead. Do not remove affected samples from any numeric quality check. Candidate B avoids mid-run affinity syscalls.
- Same loss seeds give shared loss IDs, not independent realizations. Comparison is a controlled mechanism test, not a statistical reliability claim.
- Check reverse timer separately. Pinning sender may solve the forward CPU mismatch yet leave reverse CPU idle/service or server runnable delays. One direction's success cannot stand for all RTT.

## Candidate implementation if evidence supports it

For echo-send only, before first packet, set affinity to min(os.sched_getaffinity(0)). Preserve poll0. No server pin, second busy helper, global scheduler/IRQ/kernel setting, or change to saturation unless separately justified. Setting a narrower task mask changes execution policy despite identical Docker numeric resource limits; disclose it and record effective masks. The minallowedCPU rule generalizes cleanly to limited cpusets and needs no user configuration.

Tests should verify that the selected CPU comes from the allowed mask and affinity is installed before the send grid begins, while fake timing/ID/payload contracts remain unchanged; saturation path must preserve its current behavior. Real candidate B and later full fixed calibration remain necessary. A passing two-profile diagnostic cannot prove all future rare pauses absent or make old source-bound gates applicable.
