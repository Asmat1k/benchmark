# Independent mechanism and parked-tracer review

14 November 2026. Codex trace_review subagent. Bounded read-only research except the two newly requested diagnostic files listed below. No Docker operations, measurement, calibration, production change, threshold change or external reviewer approval.

## Evidence and economical order

The full post-poll0 collection still has formal RTT process flags in r20p0-latency, r80p0-latency and r80p1-latency, while all 14 senders pass. Saved independent review reports r80p1-latency drift3.663525ms and late5s medians83.88–84.03ms. The earlier targeted trace separated a server runnable-wait outlier from a forward queue→xmit outlier; it did not reproduce the sustained transition. Neither observation establishes that all sustained changes share one mechanism.

The cheapest useful next step is completing the already scoped watchdog diagnostic, rather than introducing a speculative production fix. It can distinguish late programmed timer service from delay after the callback. It cannot establish host descheduling from guest silence alone. Preserve current CPU counts, thresholds, samples and seeds; one diagnostic result remains an instrumented observation.

## Candidate fixes and why several are premature

1. **Thread timer slack is a weak candidate.** Linux applies PR_SET_TIMERSLACK to timed waits; the documented initial slack is50µs and inheritance can alter it. Production echo-server uses an untimed blocking recvfrom, and active sender uses select0. Therefore reducing server or sender thread slack does not directly shorten the awaited network event. More decisively, netem's qdisc watchdog is a separate kernel absolute CLOCK_MONOTONIC timer, not a Python thread sleep. A cheap startup read of actual per-thread timerslack can document context, but does not justify applying prctl. If ever tested, value0 restores the default; it does not request zero slack. [Linux manual](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html).

2. **Netem timer coalescing has an observable prediction, not an identified patch.** In Linux6.12.76 netem schedules its queue head's time_to_send through qdisc_watchdog_schedule_ns; qdisc watchdog init uses monotonic ABS_PINNED. The watchdog callback schedules TX work and returns. Trace the actual programmed softexpires/expires, callback entry and dequeue instead of assuming enqueue+40ms is the timer deadline. With range0, systematic millisecond lateness is not explained by intentional userspace timer slack. Late callback points to timer/kernel/vCPU service; timely callback followed by late dequeue points to deferred TX service. LinuxKit source differences remain a limitation. [Stable sch_api.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_api.c), [stable sch_netem.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c).

3. **Nonblocking server polling is a small conditional intervention.** If the sustained transition lands after timely driver start and consists predominantly of server runnable-wait, polling the server socket is a plausible minimal experimental alternative. It also keeps the second vCPU busy, so any improvement would confound avoiding server sleep with CPU/VM residency. Expect roughly one additional occupied vCPU, on top of the sender's existing approximately one vCPU. It could increase network/scheduler contention. Do not apply it merely because sender poll0 helped, and do not treat a clean short run as proof that the rare transition is fixed.

4. **Python GIL/GC changes have insufficient evidence.** Sender and echo-server are separate processes; the simple server has one thread. A5ms Python thread-switch interval is not evidence of cross-process GIL contention. No per-packet logging occurs in production server. GC disabling or a C rewrite would add an intervention before locating the delay. Retain these only if user execution, rather than queue/timer/runnable wait, actually grows.

5. **Docker Resource Saver does not fit an active collection.** Docker documents VM shutdown when no containers run, whereas these collections have active containers and an occupied sender vCPU. Disabling that feature is not a supported explanation for sustained millisecond extra latency during collection. Other host/VM timer mechanisms remain unmeasured; do not change Docker backend, CPU count or scheduling policy under an unchanged ENV identity. [Docker documentation](https://docs.docker.com/desktop/use-desktop/resource-saver/).

Prior immediate-mode and affinity ABBA did not support those fixes. Do not introduce SCHED_FIFO, a global CPU-idle policy, or wider network budgets as an economical first fix: they alter scheduling or environment without localizing the observed component.

## Parked tool audit

The original watchdog-trace-v1 is preparation only; its STATUS says stopped before selftest. It is not runnable as-is: selftest.sh and tools/timer_check.py are missing; network.sh requires a single successful selftest and calls the missing checker. Its inherited check.py verifies server syscall brackets but omits sender PID binding and timer evidence. These are actual readiness gaps, not measurement failures.

The tracer correctly uses server-only syscalls, two-process scheduler filters, a unique nonzero kallsyms address for numeric watchdog function filtering, mono clock, loss counters and blocked SIGUSR1/sigwait with one alarm. Function filtering covers all guest watchdogs, so timer pointer→direction association must stay explicit. hrtimer_start records may replace older starts; cancel and expire_exit lack function fields and are not collected. Callback now is sampled timer-base time; save both now−softexpires and trace timestamp−softexpires. Timer trace definitions were reviewed against upstream6.12; actual runtime formats must be verified on LinuxKit. [Definitions](https://raw.githubusercontent.com/torvalds/linux/v6.12/include/trace/events/timer.h).

## New preparation delivered, not executed

Only in solution-research-v1/watchdog-service:

- tools/timer_check.py: sender namespace-PID binding; mono/filter/loss checks; same-pointer latest-start pairing; replacement and final-pending records; both lateness measurements; explicit cancellation and direction limitations. At least one pair required; no invented physical-lateness acceptance threshold.
- selftest.sh: isolated network-none loopback namespace,10ms netem/rate10Mbit,20UDP echoes, server/sender ready barriers, signal-based tracer stop, inherited syscall check plus timer check, cleanup of own containers. A readiness barrier prevents racing the loopback-qdisc setup. There is no periodic observation during the packet sequence.

Python AST parsing and shell syntax checks passed. These do not prove runtime access, loopback-qdisc traversal, numeric filter support, callback coverage, or the hard-budget cleanup path. A failed capability selftest must stop the dependent network run; preserve its output and repair the instrumentation with an explicit reason before proceeding.
