# Dynamic watchdog rebase in causal migration control

14 November2026. Read-only inspection of saved `migration-causal.6itZemcx/r80p1-migrate`, no experiments or production changes. First bounded source/trace scan0.597s; second targeted event scan0.295s. Derived trace-review CPU runs independently read, then exact raw events checked.

## Observed sequence

Saved callback CPU runs show forward watchdog CPU0 until relative36.142639s; CPU1 from36.166246 through68.652110s; thenCPU0 from68.670160s. Thus migration atID3000/6000 does not imply a permanently stranded watchdog or instantaneous reversal at the second switch. Describing all30–60s as timerCPU0, or all60–100s as timerCPU0, would be false.

The raw trace identifies the rebase mechanism without assuming an empty queue:

|Step|First rebase0→1, monotonic seconds|Second rebase1→0, monotonic seconds|
|---|---:|---:|
|Last old-CPU callback|130634.287734|130666.797205|
|Old-CPU rearm|130634.287777|130666.797209|
|Programmed old expiry|130634.295223301|130666.805256606|
|New-CPU sender queue arrival|130634.295321|130666.805806|
|New same-pointer timer start|130634.295326|130666.805814|
|New programmed expiry|130634.305228593|130666.815252231|
|Positive forward dequeue|130634.295328|130666.805816|

The arriving packet is ~97.7us/~549.4us after the pending old head deadline. There is no intervening callback for that old deadline; the same watchdog pointer is restarted on the new senderCPU for the next head deadline. The trace immediately records positive dequeue on the newCPU. This supports incoming enqueue/qdisc-run servicing the already-due head and replacing its overdue watchdog with the next head's expiry, rebasing the chain. An empty queue or a37.7s pause is not required and is not claimed.

## Source interpretation

Netem dequeue returns due heads directly; when the next head is not due it requests that head's watchdog expiry. An unchanged already-pending expiry can be retained, sustaining the oldCPU chain. A changed expiry is restarted pinned on the callerCPU, permitting rebase. Bulk dequeue's outer trace may follow the new timer-start event: the first packet was due and the attempted next packet scheduled the future timer before the aggregate positive-dequeue trace was emitted. This is consistent with observed start-before-positive-dequeue ordering.

Primary sources: [sch_netem.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c), [sch_api.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_api.c), [sch_generic.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_generic.c). Source explains mechanism; LinuxKit callback lateness source (host/guest idle/timer service) is still not identified at the host level.

## Qualification of candidate conclusion

Parent reports A forced migration processsuspect/maxlag50.532ms and B fixed0 processclear/maxlag25.877ms. Those outcomes support a sender-only fixed-CPU policy together with the natural migration event, but A's failure must stay visible. A had intentional nonstationarity and is causal-control evidence, not a successful qualification series. The predeclared simple immediate-return prediction was incomplete: the actual oldCPU/watchdog mismatch persists until a later rebase, and the delay regime must be described using real timerCPU periods, not just requested affinity phases.

Pinning sender before first send removes these migration-induced mismatches without an extra busy core, server affinity, global scheduler setting, or changed thresholds. It does not prove every rare pause is eliminated or guarantee full calibration success. A meaningful regression can establish affinity installed before first packet, minallowedCPU chosen, poll0 and saturation unchanged. A fresh post-fix short validation and later applicable full calibration/source-bound gates remain necessary.
