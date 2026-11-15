# Independent final candidate review

Internal Codex subagent review,14November2026. Read final run.py, collect.sh and probe.py; no network or additional tests launched during this review. Production files unchanged.

Ready for the one bounded diagnostic, conditional on the real preflight passing. No blocking issue found in the final additions. Root wrapper includes preflight in its240s budget, rejects insufficient reserve before network, allocates20s for cleanup, stops the process group on timeout/interruption, permits only one prospective network start and preserves source/ENV/tool identity and final raw refs. Exit0 remains diagnostic collection only; no qualification or calibration pass is fabricated.

Partial retention is improved: actual candidate PID is saved before load; SIGTERM raises SystemExit; the exception branch writes a separate partial JSON before printing. Collector cleanup signals that actual PID and copies partial telemetry before removing helpers, while preserving interrupted captures. Hard SIGKILL or interrupted serialization can still lose incomplete in-memory telemetry; this disclosed limitation is not a guarantee of complete trace under every abort.

Read saved linux-offline.exit=0 and stderr:4tests in0.001s,OK. Saved offline counter selftest covers actual task schedstat/threadCPU access, not observer equivalence on the network. Per-send instrumentation remains only post-send; no per-select hook, kernel settings change, periodic Docker observer loop or production threshold change.

Counter interpretation constraints remain: disabled sched_schedstats zeros cannot disprove guest waiting; counter reads are not atomic and updates can lag; snapshot CPU cost excludes some bookkeeping; residual wall time cannot prove a host cause. Full ordered cumulative counters and every RTT/missing ID must be retained in result review. No recurrence yields inconclusive diagnostic, not a fix. Future interpretation still requires independent raw/counter/pcap review, including monotonic cumulative deltas.
