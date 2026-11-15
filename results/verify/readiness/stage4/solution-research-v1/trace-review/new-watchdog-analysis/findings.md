# Independent watchdog and sender-CPU analysis

14 November2026. Input: results/verify/diagnostic/watchdog-trace.zk2E5PYS/r80p1-check. No network or additional collection. analyze.py and focus.py independently parsed the raw trace and saved timer pairs using stdlib; each has a90s alarm and completed in approximately2–3seconds. Raw files were not edited.

## Component localization

A sustained forward residence increase is present around24–26seconds. It coincides with **late actual programmed watchdog callbacks**, rather than primarily delay after a timely callback or server user execution.

|Second|Forward queue→xmit median,ms|Forward callback lateness median,ms|Forward sampled-now lateness median,ms|Sender CPU0 residence,ms|Sender CPU1 residence,ms|
|---|---:|---:|---:|---:|---:|
|21|40.244|.002922|—|999.925|0|
|22|40.244|.002963|—|999.511|0|
|23|40.863|.100170|—|452.688|538.999|
|24|42.125|1.883087|1.882059|0|999.864|
|25|42.173|1.957961|1.957058|0|997.661|
|26|41.850|1.623586|1.622642|145.984|852.607|
|27|40.244|.003044|—|999.939|0|
|28|40.244|.003189|—|999.939|0|

The distinction between callback trace timestamp and kernel sampled-now is small: forward entry−sampled-now median .862/.819/.694µs in24/25/26, compared with1.6–2.0ms lateness. This supports delayed kernel timer service, rather than a millisecond delay merely printing the trace event.

Forward watchdog runs onCPU0 in all9913callback pairs; reverse onCPU1 in all9794pairs. Sender migrates CPU0→CPU1 at23.460839seconds and returnsCPU0 at26.854010seconds, relative to first forward queue. In seconds24/25 the forward queues are100/100 onCPU1 but forward xmits99/99 onCPU0. Reverse queues are99/99 onCPU0, while reverse xmits97/95 onCPU1. Reverse residence median40.244ms and callback lateness.002754/.002753ms during those two seconds. Before/after, reverse residence is around40.31ms while sender occupiesCPU0.

Sender deadlines remain timely in the central interval: max lag .122594/.123720/.008845ms in24/25/26; medians approximately.0011ms. This rules out sender deadline misses as the source of these sustained excess milliseconds. It does not show CPU0 was idle or prove host scheduling: only the two target processes' scheduling events were captured.

Across the complete collection, temporal callback→next positive same-direction dequeue median/p99/max are .002/.006/.755ms forward and .003/.008/.440ms reverse. Forward callback lateness median/p99/max are .003055/2.050086/24.739723ms. Queue→xmit median/p99/max40.244/42.359/78.138ms. Callback→next dequeue is a temporal association, not established causal ownership of every later packet. The sustained callback-lateness result does not require attributing every packet to one timer expiry.

Sender cgroup usage delta100024560µs; server347696µs; both cgroup throttle counters remain zero. Scheduler-derived residence means the task is current in the guest trace, not uninterrupted host-vCPU execution. IRQ/softirq time while sender remains current is included.

## Pointer mapping and bulk lookahead

The proposed next-NULL-only association has only three direct anchors, all preserved in focus.json:

- forward timer00000000f3257659: start130125217215000ns, CPU0, next NULL dequeue130125217216000ns, ifindex14/handle0x806C0000;
- reverse timer000000003b2a1ee1: start130125257609000ns, CPU1, next NULL at the same displayed timestamp, ifindex13/handle0x806D0000;
- reverse same pointer: start130126933523000ns, CPU1, next NULL at the same displayed timestamp, same index/handle.

All19707starts associate consistently with the next **any** qdisc dequeue on the sameCPU:9913forward,9794reverse; zero contradictory associations. Only3 are NULL;19688 report1packet,9 report2,5 report3,1 reports5,1 reports6. Gap median0ns, p99 1000ns, max64000ns at displayed precision.

This reflects netem rearming during bulk lookahead before the enclosing positive dequeue event. Example raw lines277–282: callback .257455; rearm .257458; positive dequeue .257458; xmit; NULL dequeue .257462. Preserve ordinal event order when timestamps tie. This extends, rather than replaces, the three direct NULL anchors; it is corroboration and not a directly recorded timer→qdisc pointer field.

## Implication and limit

There is now direct evidence that sender CPU migration and late forward watchdog service coincide and reverse on return. A controlled sender migration/affinity experiment is more economical than changing server implementation, thread timer slack, bandwidth or thresholds. Previous affinity ABBA did not reproduce a transition; it did not test this newly observed migration-vs-pinned-watchdog condition. The present record supports a specific new hypothesis but does not itself prove host/vCPU idle, Linux scheduler root cause, or that all older transitions share this mechanism. No production fix or admission claim follows yet.

Outputs: result.json, focus.json, transition-windows.json. The initial stricter NULL-only computation was replaced by the documented next-any calculation after raw ordering exposed bulk lookahead; collection data and success thresholds were unchanged.
