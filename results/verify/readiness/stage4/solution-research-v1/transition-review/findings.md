# Independent transition and clock review

14 November2026. Read-only investigation by Codex transition_review. No measurements, production edits, thresholds, exclusions or data corrections. Source raw: results/verify/diagnostic/calibration.gIdWLx7o. All14echo series decomposed; all source file SHA256s stored in analysis.json. This is exploratory causal review, not a gate or independent external approval.

Commands from /Users/dobrov/Desktop/Code/ITMO/benchmark:

- `python3 -B results/verify/readiness/stage4/solution-research-v1/transition-review/analyze.py > results/verify/readiness/stage4/solution-research-v1/transition-review/stdout.log`: exit0,0.739065s compute,0.831s command;90s alarm.
- `python3 -B results/verify/readiness/stage4/solution-research-v1/transition-review/clock-review.py > results/verify/readiness/stage4/solution-research-v1/transition-review/clock-stdout.log`: exit0,0.480844s compute,0.501s command;90s alarm.
- Follow-up selected packet/offset extraction: exit0,0.036s. Values below and full context are in clock-analysis.json; no measurement repetitions.

## Component distribution

All14five-second medians and span quantiles are stored, rather than selecting a favorable run. Most sustained inflation is forward ingress→reply ingress, which includes forward netem, server and intervening service:

- r20p0-before final15s: span10.292→12.118–12.143ms, RTT20.607→22.455–22.457ms. At90–95s span min/p5/p25/median/p75/p95/max=10.255/10.417/11.478/12.129/12.261/12.331/12.698ms.
- r80p0-latency15–60s and85–100s: span40.294→42.13–42.20ms. At20–25s span40.259/40.294/41.503/42.201/42.330/42.662/42.756ms. Residual mostly40.25–40.45ms. The apparent+1.84ms level is a broad variable distribution, not every packet receiving a fixed1.84ms addition.
- r80p0-after40–80s: span~42.13ms versus40.294ms before/after; residual~40.25–40.48ms.
- r80p1-before~75–80s: span43.110ms versus40.296; residual drops40.388→40.255ms.
- r80p1-latency35–100s: span~43.03–43.18ms, residual~40.84–40.96ms. At40–45s span min/p5/p25/median/p75/p95/max=40.277/40.703/42.199/43.179/43.609/44.132/45.056ms. Both the forward component and a smaller reverse/receive remainder change here.

Sender gaps remain essentially10ms during these sustained states. Formal process failures are not just late sender packets; adding more sender deadline instrumentation alone cannot establish cause.

## Capture timestamp discontinuity, not packet reordering

All14forward/reverse pcaps have strictly increasing ID record order. In r80p0-latency:

- Forward record9742,ID9742:epoch1794648751582625us; record9743,ID9743:1794648751574860us. Timestamp goes backwards7.765ms although sender interval+9.995958ms.
- Relative epoch-minus-monotonic offset changes from+0.4838ms to−17.2765ms, persisting throughID9999.
- Reverse record9738:1794648751582885us; record9739:1794648751575576us, backwards7.309ms. Reverse crossing is4IDs earlier, consistent with40ms forward flight; new reverse timestamp is716us after new forward timestamp.
- IDs9739..9742 consequently have implausibly short epoch spans22.959/24.421/23.277/24.359ms, while independent monotonic RTT remains82.293/82.854/82.109/82.398ms. After both packet endpoints use the new offset, spans return~42ms.

This supports a shared packet-timestamp epoch discontinuity of approximately−17.760ms, rather than a lone delayed forward packet. It does not establish the mechanism of a classic wall-clock adjustment: packets have no CPU metadata, so coordinated perCPU timestamp source/skew/migration cannot be eliminated from these data. Calling it simply a known global clock step would overstate evidence.

r80p1-latency has analogous persistent offset change−4.448541ms atID2358/23.58s; reverse-crossing IDs2354..2357 have spans35.902–37.639ms. The later sustained~3ms span state begins~35s, over11s later. In r80p0-latency the large discontinuity is97.43s, long after the15s state onset. These discontinuities contaminate isolated crossing packets and fine phase analysis but do not explain independently sustained monotonic RTT increases. Raw remains unchanged; no correction or exclusion proposed.

## Mechanisms and least-cost candidate

Echo serve() uses indefinite blocking recvfrom, not timed select/poll/recv; sender uses select0 during actual sends. There is no positive server receive timeout to shrink. Per-thread timer slack concerns timed waits and is a poor candidate for the measured phase; it does not directly control netem's own kernel watchdog. [PR_SET_TIMERSLACK manual](https://man7.org/linux/man-pages/man2/pr_set_timerslack.2const.html)

Ordinary rate overload is contradicted by298byte frames at100Hz and10Mbit/s: serialization0.2384ms,load2.384%; timing margins remain large. Prior detailed check of saved failed short r80p1 had core ingress9.983–10.017ms and exact shaped byte counts. Netem assigns release deadlines using enqueue time, propagation delay and prior assigned deadlines; actual delayed callbacks/service need separate evidence. [Linux6.12.76 sch_netem.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c)

The cheapest distinct intervention to test is **reduce only the synthetic echo sender's scheduler priority using nice+10, retaining poll0 and all packet timing contracts**, leaving server normal. No second busy CPU, code abstraction, global scheduler setting or extra privilege is required. This tests whether the persistently runnable polling sender competes with wake-sensitive echo processing. Linux EEVDF distinguishes latency-sensitive tasks and wake/preemption behavior; numerical1.84/2.84ms levels do not identify that mechanism. [Kernel scheduler documentation](https://www.kernel.org/doc/html/next/scheduler/sched-eevdf.html)

This is a candidate experiment, not an established repair. It may worsen sender lag and cannot directly cure a netem timer/kernel-service interruption. Predeclare sender/process tests unchanged, compare control/candidate with fixed run count and placement, inspect CPU cost and all failed controls; no adoption from one clean candidate with clean controls. The prior affinity ABBA separated sender0/server1, all controls also clear, and was inconclusive; it did not test niceness or establish that placements cannot matter. A second spin server would be a more expensive alternative and could increaseCPU/observer load; increasing priority or FIFO adds permission/execution-policy complexity.

The next targeted trace can make this candidate decision concrete rather than accumulate undifferentiated data: correlate actual programmed watchdog expiry→callback→positive dequeue and server runnable→running on common mono; add sender scheduling without senderpoll tracing. If queue/dequeue is timely but sustained delay is server runnable wait, the priority intervention directly targets the demonstrated component. If late callback/dequeue already accounts for the effect, do not call changing nice an echo-processing repair. Existing short trace showed both distinct isolated scheduler delays and shared bidirectional dequeue pauses; neither alone establishes the sustained state mechanism.

CPU-frequency, host power policy and VM coalescing remain hypotheses, not findings: packet data has no frequency/governor/host service record. Busy polling can changeCPU residency as well as wait semantics, so improved behavior cannot distinguish them. Any execution-policy change loses applicability of older gates and needs fresh source-bound checks before readiness claims. No production change is justified solely by this analysis.
