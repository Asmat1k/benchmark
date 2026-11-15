# Independent remaining-cause review after sender affinity

14November2026. Raw collection calibration.ew2u0ceD. Read-only targeted analysis of r20p1-before and r80p1-latency, with10input files checked against their existing seals. No network run, bootstrap, correction, threshold change or production edit. analyze.py completed0.1005seconds; execution.json records the bounded command and exit0. Outputs are derived separately from raw.

## Rare pause remains a service-path event, not merely late sender deadlines

r20p1-before worst lag isID4525,69.794312ms. The actual send gap4524→4525 is79.793375ms; forward ingress gap is79.827ms. This shows the delayed send reaches the router with the same large gap, but does not identify why the sender stopped making progress.

The two directions are **not both silent for the whole79.827ms**. Relative to forward ingress4524:

- reverse ingress4523 occurs at+.288ms;
- reverse ingress4524 occurs at+50.119ms;
- forward ingress4525 occurs at+79.827ms.

The common ingress quiet intervals are49.831ms and then29.708ms, separated by reverse4524. An interpretation of one uninterrupted80ms whole-VM freeze would overstate the evidence.

Already-outstanding echoes are also delayed. ID4523 has ordinary router-span10.288ms, yet RTT89.870792ms and residual79.582792ms, against neighboring residuals around10.31ms. It reached reverse router ingress before the long common quiet interval and was received at sender-relative45319.871354ms, immediately after sender resumed. Its excess delay therefore occurs beyond server echo execution, in reverse qdisc/client/kernel service. ID4524 additionally has router-span50.119ms, well above neighboring10.29ms, plus residual29.921125ms. Thus multiple portions of the service path are affected during the episode.

This resembles the previously observed rare shared-service pauses despite the sender-affinity mitigation. A sender-only GC or deadline explanation is insufficient for all components. The record does not distinguish delayed qdisc watchdog, guest scheduling/softirq, host-vCPU service, or several overlapping pauses. Pcap drops are checked in primary review; no capture loss is inferred from this silence. No absolute mapping between pcap epoch and sender monotonic clocks is used here.

## Remaining r80p1 step is in the residual half-path

All-survivor summaries in the first35seconds versus the last60seconds:

|Quantity|First35s|After40s|
|---|---:|---:|
|RTT median,ms|80.688480|80.555792|
|Router-span median,ms|40.298|40.299|
|Residual median,ms|40.389000|40.254916|
|Sender-lag median,ms|.001795|.001834|

The residual decreases.134084ms while forward-ingress→reverse-ingress span remains stable. The per-second record narrows the change: seconds35/36/37 residual medians40.388542/40.390958/40.388625ms; seconds38/39/40 are40.254938/40.253334/40.253708ms. Every1s window, not only these displayed summaries, is saved in analysis.json. These groupings describe the existing transition; they are not acceptance windows or exclusions.

This is compatible with a change in reverse watchdog CPU/residency or reverse-path client service. The prior controlled study demonstrated that watchdog CPU can rebase, and server scheduling can affect the CPU processing replies. However, these raw files contain no watchdog or server scheduler record: server migration, reverse timer rebase and host-idle causes cannot be asserted. The known large forward+3ms regime is not present in this particular component record. A stable forward span does not establish full process readiness; the unchanged formal process flag remains binding.

## Minimum next distinguishing evidence

Keep the two remaining phenomena separate; do not patch either on speculation. A prespecified short diagnostic should retain fixed sender affinity and existing packet geometry, and add the already validated event-based scheduler/watchdog records for both processes and both directions. It must provide:

1. Reverse net_dev_queue→net_dev_start_xmit, actual watchdog deadline→callback CPU/time and sender receive timing on the **same monotonic clock**, with packet-ID/lifecycle validation. Reusing the sender's existing monotonic receive timestamp and saving its absolute origin avoids an additional per-pselect observer. This separates a reverse timer step from post-qdisc/client-receive service.
2. Sender and server switch/wakeup state across any rare pause, both directions' watchdog callbacks and dequeue events. This tests whether the sender was runnable but unscheduled, whether callbacks were late, and which guest path resumed first. No sender select0 syscall trace or periodic sampler is needed.
3. Explicitly preserve the limit: target-process scheduling and guest timer events cannot prove a whole-host/vCPU pause. Event-based per-CPU idle records may add context if already available and validated, but absence of selected events is not evidence that both CPUs stopped.

If a rare pause does not recur, its cause remains inconclusive; do not rerun until it does. A short residual-step observation can still distinguish the reverse component if it recurs, but cannot clear the separate rare-pause sender failure. No speculative fix is proposed by this review.
