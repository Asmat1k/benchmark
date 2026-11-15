# Independent kernel and least-cost hypothesis review

14 November 2026. Read-only research by Codex subagent kernel_hypotheses. No measurement, production edit, threshold change, bootstrap, or assumption approval. Read full post-poll0 report, current probe/network/compose and prior trace boundary documentation. One bounded stdlib scan of the saved38MiB trace completed in0.094s; no heavy workload.

## Most economical discriminating direction

A cheap execution-policy candidate is **sender-only CPU affinity**, conditional on evidence linking late watchdog callbacks to a CPU left behind by sender migration. This is not established and must not be applied because the previous shorter affinity trial happened to clear.

Netem watchdogs start in ABS_PINNED mode on the CPU issuing the start. The hrtimer implementation selects the current CPU for a pinned start; a still-running callback and a pending unchanged expiry complicate this simple picture. If poll0 sender moves CPU while an older watchdog is still pending on a now-idle vCPU, sender deadlines can remain precise while the old CPU's timed queue work is late. This is a concrete hypothesis consistent with the need to distinguish timer service from sender timing. Pinning just sender would cost no extra busy CPU and no kernel/image upgrade. Its applicability depends on the actual CPU/timer trace; the earlier both-helper split-affinity ABBA lacked a reproduced control transition, so it neither established nor disproved this mechanism.

Fresh read-only observation: in prior instrumented `transition-trace.jNq2hqdS`, all10000 forward `net_dev_queue` events ran on CPU0; there were **zero sender queue CPU changes**. That run lacked the sustained transition. Full failing `calibration.gIdWLx7o` has no CPU trace, so the contrast is compatible with the hypothesis but cannot test it causally.

Required new evidence: preserve CPU for hrtimer_start, expire_entry, positive dequeue, sender sched_switch and network queue; pair latest start of same timer pointer, not nearest packet. Track whether a delayed timer belongs to the CPU currently running poll0 sender, a previously used CPU, or neither. ABS_PINNED watchdogs make changing global kernel.timer_migration a poorly targeted fix.

[Stable qdisc watchdog implementation](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_api.c), [hrtimer CPU-base selection](https://raw.githubusercontent.com/torvalds/linux/v6.12/kernel/time/hrtimer.c). The latter is upstreamv6.12, not a complete LinuxKit patch audit.

## Timer-slack shortcut is unsupported

The current server waits in blocking recvfrom with no receive timeout, and sender uses select timeout0. PR_SET_TIMERSLACK controls expiry of timed process waits; it does not turn an arriving packet wake into a thread timeout. Netem has a separate monotonic pinned hrtimer, scheduled through a zero range. Therefore changing sender/server timerslack is not a direct fix for the qdisc deadline. A very large inherited process slack should still be recorded if one later introduces timed waits, but there is currently no reason to add prctl as a guessed solution.

[Linux timer-slack interface](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html), [netem dequeue/watchdog call](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c).

## Other candidates and costs

|Candidate|Cost and judgment|
|---|---|
|Sender-only pin after migration evidence|Small implementation, no additional full CPU. First candidate only if callback/CPU evidence supports it.|
|Server nonblocking polling|Small code delta but near another full vCPU and potential contention. It can prevent an idle-vCPU/timer issue as well as accelerate server receive, so needs a controlled comparison and explicit CPU disclosure. Less attractive than a supported affinity policy.|
|SO_BUSY_POLL socket option|Not a universal recv fast path: tied to kernel NET_RX_BUSY_POLL/NAPI support; veth no-GRO/no-NAPI flow can make it ineffective. Inspect SO_INCOMING_NAPI_ID before considering; do not assume option acceptance means active polling.|
|Nice/RT priority|Does not service an unavailable timer CPU. Server runnable delays exist separately, but blanket RT risks starving capture/other helpers and is not justified by sustained spans.|
|Remove CPU quota / add CPUs|No evidence of relevant throttling; helper containers are not the router service cgroup. Higher resource cost and changed ENV, not first choice.|
|Replace Python with C|No shared GIL between sender and server processes; existing server work is microseconds in instrumented runs. Language rewrite does not repair late pre-server dequeue.|
|Change netem delay/rate/limit or statistics|Changes the experiment or acceptance, not a causal remedy; do not do this.|

[Kernel socket options and incoming NAPI ID](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/core/sock.c).

## Precise short test and success criteria

The prepared event-based watchdog test is the right first discriminator. Keep one10000echo r80p1 collection, same seeds, original two ingresspcaps and sender, with hrtimer start/expire plus sender/server scheduling. No polling syscalls, no periodic sample. Record programmed expires and softexpires independently of callback trace time; callback.now is sampled timer-base time and should be retained separately. Runtime mode must show ABS|PINNED; configured slot delay is zero. Associate timer to qdisc conservatively and report ambiguity.

- Late callback relative to actual programmed expiry: timed service issue before NET_TX. CPU association tests the cheap affinity hypothesis; it does not establish host scheduling as cause.
- Timely callback, late positive dequeue: callback only schedules work, so focus on deferred NET_TX/softirq execution.
- Timely xmit but server runnable waiting: server scheduling issue, distinct from netem.
- An absent sustained transition is inconclusive for that historical mechanism; do not declare a fix or repeat unchanged to obtain success.

The actual time_to_send of each packet remains useful if the trace can access it cheaply, but reading netem internal skb control-block layout with hard-coded offsets is more fragile than observing the already exported watchdog events. Programmed timer expiry is a queue-head deadline, not one callback per packet. Neither nominal40ms subtraction nor counting all dequeue events as one packet is sufficient.

No existing evidence proves one universally working fix. The proposed order minimizes implementation and runtime cost while preserving an honest stop if causal evidence is absent.
