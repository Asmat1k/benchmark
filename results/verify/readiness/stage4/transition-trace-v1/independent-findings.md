# Independent read-only review of targeted trace

14 November 2026. Codex subagent transition_review inspected the plan and mapping code before results, then analyzed raw only after the parent reported completion. No network experiments, production changes, raw edits, threshold changes or gates. The first exploratory parser exited1 in0.44s because net_dev_queue uses `dev`, not `name`; corrected parser completed in0.64s, and the saved repeat in<1s. Reproducible command: `python3 -B results/verify/readiness/stage4/transition-trace-v1/independent-review.py`; output `independent-review.json`. All event times in this independent parser are integer trace microseconds; application monotonic nanoseconds converted only for differences.

## Prior saved transition independently confirmed

All44 seals of profile-validation.73PKohD7 matched. Forward10000/reverse9925 unique IDs; tag a3bf536fd1451dd3 matched collection hash; reverse IDs strictly increasing. ID4200..4899 router-span median43.196ms,min40.274,max45.242, versus ID3500..3999 median40.294ms. Adjacent surviving reverse packets changed spacing median/min/max10.000/9.800/10.197ms to9.484/5.161/14.960ms. The core includes second48 (42<=t<49s). Both captures are ingress; no saved post-forward-qdisc point exists.

## New targeted result

Raw: results/verify/diagnostic/transition-trace.jNq2hqdS/r80p1-check. Trace checker reports9925server records, successful syscall pairs for all, zero trace loss, valid target/clock brackets. Target hostTID10838 maps to namespacePID1. The independent decomposition follows ordered queue events and server ID/xmit order; it is a cross-check of the primary analyzer, not an independent integrity/lifecycle validator.

The original multisecond transition did not reproduce. Across all100 prespecified one-second windows:

- Router-span median40.298–40.336ms.
- Queue→start_xmit median40.244–40.2495ms.
- Start_xmit→server userspace receive median0.036159–0.066494ms.
- Userspace receive→send invocation median0.001500–0.003229ms.
- Send invocation duration median0.008833–0.017188ms.
- RTT median80.683584–80.753063ms.

In seconds42..48, router-span medians40.300–40.3105ms. This is inconclusive for the historical multisecond cause; observer influence and different VM state remain possible. No causal repair is established.

There are separately localizable isolated outliers:

- ID8504: queue→start_xmit61.969ms, router-span62.542ms, RTT102.928166ms. Delay already exists at the forward-service boundary, before echo userspace; this does not distinguish netem timer/kernel service from host/vCPU availability.
- ID2035: start_xmit→userspace receive5.568985ms. Server wakeup126242.393467s→switch-in126242.399017s takes5.550ms; received timestamp126242.399031985s. This supports delayed scheduling of an already runnable echo server for this packet, not a claim about the original transition.
- Other largest observed wakeup→switch-in delays4.642/3.567/2.554/2.537ms correspond to individual events. Across9958 observed wakeup→switch-in pairs median3us. Startup and teardown wakeups are included; this is descriptive, not an admission statistic. A2.087s blocked interval occurs after measurement/end/drain and cannot be called starvation. Blocking recvfrom duration also includes ordinary network/loss waiting.

## Mapping review

Kernel-placement document correctly qualifies queue→start_xmit as qdisc residence plus surrounding service and avoids treating `-Q out` as guaranteed post-netem evidence. Before strengthening attribution, primary mapping must validate no intervening reuse of a matched skb and corroborate positive qdisc dequeue events/handle/index, as requested to the parent. Namespace-ambiguous ifindex alone is insufficient. Syscall checks establish record bracketing; scheduler evidence must be used to separate waiting from runnable execution delay. Guest events alone do not exclude host/vCPU descheduling. This reviewer did not create or approve a new gate.

## Synchronized isolated late service near126307.105s

Additional independent raw scan took0.56s, exit0. The primary analyzer subsequently reports skb lifecycle validation and positive bulk-aware dequeue associations for all9925 forward transmissions; the concerns above are addressed in that primary analysis. Bulk dequeue has packets3 here, so treating one qdisc_dequeue event as exactly one skb transmission would be incorrect.

- CPU0 last captured relevant event126307.073527s → first126307.105183s:31.656ms gap.
- CPU1 last126307.081025s → first126307.105296s:24.271ms gap.
- Common interval without any **filtered trace event** on either CPU:126307.081025→126307.105183,24.158ms. This is not an observation of complete CPU idleness or total kernel event silence.
- Forward positive dequeue at126307.105183 releases3 packets; start_xmit at.105192/.105195/.105196, with queue residences61.969/51.807/41.860ms.
- Reverse positive dequeue at126307.105339 releases3 packets (IDs8500/8501/8502); start_xmit at.105346/.105348/.105348, with residences61.674/51.291/41.241ms. First reverse transmit is154us after first forward transmit. These delayed releases occur on different CPUs, not just inside echo-server userspace.
- Echo server switched out sleeping (S) at126307.073805 and next switched in at126307.105622,31.817ms later. It became runnable at.105296, so wakeup→run here is0.326ms, rather than the full31.817ms blocked interval. ID8504 received at.105731473, after late forward dequeue.
- The parent reports sender IDs8508–8510 also late, max22.052ms, overlapping this interval. This independent report did not recompute sender quality.

The overlapping sender delay plus forward and reverse late dequeue support a shared service interruption as the economical hypothesis for this isolated event. They do not establish whether the interruption originated in VM/vCPU scheduling, guest kernel service, observer activity, or another source. No host-wide scheduler/timer events were recorded; the trace intentionally filters events. The original sustained42–49s transition remains unlocalized because it did not reproduce. A pure echo-server userspace processing stall cannot explain the demonstrated pre-server forward delay of ID8504.
