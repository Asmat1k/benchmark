# Minimal fix research: late wakes and capture batching

Author: Codex subagent `/root/fix_research`. Read-only production investigation; no long experiment, traffic generation, source/threshold/resource change or foreign-resource stop performed. Agent intentionally did not run timing workloads in parallel with parent's paired test.

## Current strongest economical candidate

Add `--immediate-mode` to the diagnostic/calibration tcpdump invocation, keeping `-Q in -n -U -s96`, interface, payload and all numerical criteria unchanged. This targets a specific periodic observer mechanism rather than changing sender timing or statistical acceptance. It is a candidate until paired real observations support its effect.

Existing router image was queried in network-none containers for version/help only:

- tcpdump4.99.3, libpcap1.10.3(withTPACKET_V3), native existing router image.
- `--help` contains `--immediate-mode`.
- Exact outputs: tcpdump-version.txt and tcpdump-help.txt.

In tcpdump4.99.3 upstream source, default capture timeout is1000ms; `pcap_set_timeout(pc, timeout)` and `pcap_set_immediate_mode(pc,1)` are separate configuration calls. Current `-U` controls savefile packet flushing. It does not enable capture immediate mode. Linux libpcap>=1.5 defaults to buffered delivery. These facts establish that a1second kernel-to-userspace batching mechanism is present; they do not establish that it caused every RTT tail or the historical129ms pause.

Primary sources:

- https://raw.githubusercontent.com/the-tcpdump-group/tcpdump/tcpdump-4.99.3/tcpdump.c (default223; immediate1237–1243; timeout1272–1275).
- https://man7.org/linux/man-pages/man1/tcpdump.1.html (-U and --immediate-mode distinct).
- https://www.man7.org/linux/man-pages/man3/pcap_set_immediate_mode.3pcap.html (Linux default and immediate delivery).

Expected economic tradeoff: buffered delivery reduces capture wakeups but groups work in bursts. Immediate delivery spreads capture processing and adds wakeups. Existing -U already flushes each saved packet, so the candidate does not newly impose per-packet savefile flushing; it changes when the existing work occurs. CPU cost must still be measured. Lower periodic disturbance is plausible; lower total CPU is not promised. Packets are timestamped by capture before userspace delivery; do not interpret delayed file writes as a shift of saved packet timestamp.

## Fixed short A/B plan

Parent selected oneABBA test, four5000-ID baseline echo phases: buffered / immediate / immediate / buffered. At100Hz, each phase has50seconds send plus2second drain; fixed total208seconds probe workload, plus setup/capture transfer/cleanup. Parent's hard outer270second plus10second cleanup limit remains below5minutes. No repeats or candidate tuning after outcome. Existing sender,256byteframe/tag,2.5ms limiter, seeds, routing, permanent neighbors,images/resources/TLS unchanged. Observer flag is the only condition difference. No periodic CPU/resource polling during phases, matching calibration collection; record start/end counters instead.

Minimum evidence:

1. Complete ordered5000sent IDs and returnedIDs, exact grid, sender lag/gaps/burst; condition disclosed as diagnostic, not qualification10000 or full calibration.
2. Both ingress captures, full tag/ID/IP/UDP-length/accounting checks, identical route/qdisc snapshots and zero capture loss. Sender replies still validate full payload.
3. CPU usage by condition from capture processes' `/proc/PID/stat` or the corresponding isolated cgroup before/after, plus actual elapsedphase time. Read counters before processdeath. Counter scope must be disclosed, not mislabel routertotal as tcpdump-only.
4. Evidence that batching changed: temporal distribution of capture process wakeups/file delivery or proc scheduling trace, if available. Merely observing lower RTT is insufficient to prove buffering causation.
5. RTT and network/residual spans, distribution tails and fixed periodic diagnostics, preserving every sample. A flag-free result on5000 observations cannot establish10000-sample/full30minute acceptance.

CPU comparison: report `100*sum(cpu_delta_seconds)/sum(actual_phase_seconds)` in percentofonecore percondition, plus absolute percentagepoint difference. If only per-container cgroup exists, include server/router observer cost in scope and report it as such. ABBA mitigates simple monotone drift but does not eliminate transient VMconfounding or provide independent replicate-level precision.

Decision: choose immediate-mode only if captures remain complete, periodic burst mechanism is changed in expected direction, observed jitter/dependence improves without material CPU pressure, and no contrary evidence. If results mixed, preserve inconclusive rather than selecting lucky phases. Rare historical129ms episode may not recur in208seconds; no claim of eliminating it is justified by absence alone. A failure then requires a new documented decision, not another unchangedABBA untilpassed.

## Other options considered

|Candidate|Why not first choice|
|---|---|
|Timer slack1ns|Existing comparable process was50000ns=.05ms; reducing coalescing does not remove arbitrary guest/host scheduling delays. Not a sufficient explanation for53/129ms.|
|Nonblocking receive/MSG_DONTWAIT|Guards documented Linux readiness/read race or discarded packets; no evidence this mechanism caused recorded pauses. Worth functional hardening only after an actual reproduction, not an asserted fix of late timeout wakes.|
|Busy poll0|Avoids sleeps but can consume one fullvCPU, changing calibration load substantially; does not prevent host preemption or server sleep. Costly fallback, not economical first option.|
|Shorter cap than1ms|Already1ms; repeated cap selection after outcomes risks tuning to noise. Cannot guarantee wakeup bounds.|
|Active final500us|Historical same-environment short test was inferior to existing1ms cap and added spin without removing oversleep.|
|Native sender/clock_nanosleep|More implementation/verification work; current sender already maintains absolute grid. Native sleep also waits for scheduler.|
|Separate sender/receiver|Removes processing coupling but current historical trace dominated sleeping, not expensive receiveCPU. Adds clocks/thread/shared-state/provenance work.|
|SCHED_FIFO/priority/affinity|Primarily changes runnable selection; historical wakes often already late before runnable. Adds privileges or resource contention and cannot control host scheduling.|
|AdditionalCPU/RAM|No demonstrated quota throttling/OOM/currentmemory shortage; changesENV and broad gate applicability without a proven mechanism.|
|DisableGC|Previous GC28events max2.11ms and no overlap with85longgaps; cannot infer that GCcaused current failures.|
|DockerResourceSaver|Official idle mode stopsVM when no containers; runningmeasurementcontainers exclude ordinary idle transition. Not proof about other VMpauses.|
|Stopqdrant/changehostVMM|Foreignresource stop not authorized; qdrantcausation absent. VMMchange broadENVreset and higher effort.|

These options are not impossible improvements. They are deprioritized because direct mechanism/economic support is weaker than capture batching.

Other primary references:

- https://man7.org/linux/man-pages/man2/pr_set_timerslack.2const.html
- https://man7.org/linux/man-pages/man2/select.2.html
- https://man7.org/linux/man-pages/man2/clock_nanosleep.2.html
- https://man7.org/linux/man-pages/man2/sched_setscheduler.2.html
- https://docs.docker.com/desktop/settings-and-maintenance/settings/
- https://www.kernel.org/doc/html/latest/virt/kvm/halt-polling.html (general energy/latency tradeoff only; KVM knobs are NOT applicable macOSVMMinstructions).

## Meaningful implementation checks after selection

- Mock capture launch commands and assert immediate-mode is passed with existing direction/snaplen/unbuffering for each captured endpoint. Do not test just a stringconstant with no launchbehavior.
- Ensure interrupted capture still drains/finishes and reports kernel-drop counters before sealing; negativecapture-loss fixture must remainrejected.
- Existing pcap parsing tests: repeated/foreigntag/ID/fragmentation/incompletecapture/drop correspondence must remainrejected.
- Existing sender tests prove unchanged100Hzgrid,IDpayload,2.5mscatch-up and strictv2boundaries; do not replace production criteria with5000-IDdiagnostic outcome.
- Source-change inventory: collector flags change executable hashes. Preserve historicalcalibration/qualificationraw and hashes. Newrelease/gateapplicability must explicitly account for changed observation, and fullcalibration remains required beforegenerator despite a successful shorttest.
