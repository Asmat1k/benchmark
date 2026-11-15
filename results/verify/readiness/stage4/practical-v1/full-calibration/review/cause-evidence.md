# Episode audit of failed r80p1-after sender fidelity

Internal independent subagent audit after integrity passed and the new practical metric gate failed. No network, raw changes, RTT corrections or threshold changes. Original cause-evidence.json is retained; the additional cause-evidence-pcap-gaps.json records every actual browser-ingress gap as well. Reproducible cause-audit.py retains all10000slot-derived records, all20fixed500IDbins, all31late groups and summaries of all14series. Descriptive analysis is not a new acceptance report.

## What the measurements establish

r80p1-after has242/10000late slots(2.42%). Maximum sender lag432.064733ms occurs atID5530. This number is accumulated delay against the planned grid, not a single432ms scheduler pause. The largest actual inter-send timestamp gap is129.313667ms atID5508. Further timestamp gaps≈77.639ms at5523,73.431ms at5511 and62.459ms at5501 build backlog; the contiguous late group5481–5605contains125slots. Smaller episodes occur nearIDs3582–3603,5838–5851 and6207–6224. They remain in all reported distributions.

Router browser-ingress packet timestamps independently show deformed traffic: the corresponding gap at5508 is129.319ms, at5501 is62.462ms, and at5511 is73.425ms. Not every send-timestamp gap matches capture spacing: the77.639ms timestamp gap before5523 corresponds to only0.164ms in pcap, while5522has a77.442ms centered timestamp-to-capture residual. The source timestamps before sock.send; a pause between timestamp and actual ingress, or a relevant clock-mapping issue, can therefore affect this comparison. The irregular offered traffic is nonetheless visible in packet captures, not only in the sender's planned-grid accounting. A defect solely in the local numerical sender-lag summary does not explain the129ms/62ms/73ms packet gaps. A VM-wide clock/scheduling disturbance remains possible because both clocks/timestamps come from the same VM.

At worst-lagID5530 the forward capture span is54.033ms and actual RTT94.366625ms. Sender lateness432ms cannot be reinterpreted as that packet's network RTT or removed from RTT. At the largest-gapID5508 the forward span41.151ms is close to the observed40ms one-way profile while actual RTT114.7035ms also reflects other timing components.

The same series has forward capture-span median40.296ms,p99≈55.529ms,max144.596ms and actual RTT median80.681042ms,p99≈111.687292ms,max264.405417ms. Thus there are also real forward/server-echo/return/receive timing excursions, not exclusively a sender-grid deformation. The two router ingress capture points do not isolate netem delay: their difference includes forward queue/path and server handling before the echoed datagram re-enters the router. There is no packet capture of actual client receive scheduling. Do not attribute the entire span to the watchdog or subtract a supposed network constant.

The pcap walltime minus relative monotonic-send offset, centered across all10000packets, is not constant. Typical changes are submillisecond, but the maximum centered positive residual is≈77.443ms. This can include pre-send syscall delay, ingress/capture scheduling and realtime/monotonic mapping. Negative centered values are relative offsets, not negative physical delays. There is no saved absolute monotonic origin/wallclock anchor, so this trace cannot diagnose a VM clock jump versus scheduling by itself.

## What remains unproved

The executed sender source pins to the minimum allowed CPU; this collection stores no per-episode actual affinity/CPU trace, sender process runnable/on-CPU timeline, sender-cgroup CPU counters, VM scheduler/vCPU steal timeline or before/after monotonic/realtime clock pairs. Full calibration also lacks qualification-style endpoint resource traces. Source code success and clean capture/counter identities do not supply these missing observations.

The evidence supports the practical failure exactly as published: too much observed load deformation. It does not prove regression of the prior affinity fix, a host/vCPU-idle mechanism, pure monotonic-clock error, packet loss beyond qdisc, an external application's causal role, or a deterministic sender-code bug. The known source-side catchup behavior explains how lag persists after repeated delays; it does not explain why those delays happened.

## Minimal next step

Keep the failed full calibration and STOP; do not repeat it unchanged or alter budgets to admit2.42%. No corrective production patch is justified by this audit alone.

If investigating this remaining source is necessary, preregister one short diagnostic10000packet r80p1 run with the current pinned sender, same packet/capture setup and explicit observer-load status. Capture actual sender-probe cgroup CPU/throttle counters (not only network-namespace endpoint cgroups), actual affinity/CPU identity, low-rate external VM-clock pairs and router counters. To distinguish runnable scheduling delay from blocking in send/receive, targeted bounded sender scheduling/entry-exit timestamps or the already validated diagnostic trace mechanism may be necessary; clock pairs alone cannot prove a129ms scheduling mechanism. All traces should remain diagnostic, including an absence of the episode; no retry-until-reproduction and no new calibration qualification inferred from one clean diagnostic.

Choose the telemetry needed for a falsifiable question before launching, bound the run and trace size, and disclose that tracing can change scheduling. First inspect existing trace tools rather than building a broad new VM-jitter campaign. A unique source cause is not required to preserve the present failed decision, and no broader VM tuning or foreign-container stop follows from these observations.
