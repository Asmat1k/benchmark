# Event boundary semantics

Observed VM: Linux 6.12.76-linuxkit, native aarch64. Mandatory runtime trace formats stored in each raw trace. Upstream stable v6.12.76 inspected:

- https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/core/dev.c : __dev_queue_xmit emits net_dev_queue before enqueue; xmit_one calls dev_queue_xmit_nit then net_dev_start_xmit then driver transmit.
- https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_generic.c : dequeue_skb emits qdisc_dequeue after q->dequeue; sch_direct_xmit subsequently invokes dev_hard_start_xmit.
- https://raw.githubusercontent.com/torvalds/linux/v6.12/include/trace/events/qdisc.h : NULL dequeue attempts have packets=0; bulk possible, ifindex lacks namespace identity.

Thus queue->start_xmit on router to_server brackets forward qdisc residence plus surrounding service, including possible delayed timer/kernel service. It does not identify a pure netem computation time or establish a host/vCPU deschedule. Check actual positive qdisc dequeue associations by skb/handle/index as corroboration. skb pointer reuse requires lifecycle association, not a global one-pointer dictionary.

Outgoing packet tap normally occurs after dequeue on this path, but -Q out alone specifies direction. No added outgoing pcap is used here: mono trace events provide the boundary without assuming epoch-to-monotonic synchronization. LinuxKit patch differences remain a caveat; runtime formats/order/packet counts checked. Incoming pcaps remain useful independently for ID/tag and same-clock router span. Event timestamps have text microsecond precision, not nanosecond accuracy.

Observer limitations: 16MiB per vCPU ring buffers allocated; net events and server syscalls add kernel work; four monotonic clock reads/record allocation per server echo; disk serialization only after measurement; tracer stop-file polling at50ms adds its own wakeups. Buffered original tcpdump and foreign qdrant remain. This is an instrumented causal diagnostic, not an observer-free calibration comparison. No host-wide scheduling/timer tracing or macOS tracing is introduced. Common VM descheduling cannot be proved absent from guest observations alone.
