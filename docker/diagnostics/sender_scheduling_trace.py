import json
from pathlib import Path
import subprocess
import sys
import time


# Save the supplied data.
def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


# Run the diagnostic command.
def main():
    token, output = sys.argv[1], Path(sys.argv[2])
    mount = Path("/tmp/sender-tracefs")
    mount.mkdir()
    subprocess.run(["mount", "-t", "tracefs", "tracefs", str(mount)], check=True)
    instance = mount / "instances" / token
    try:
        candidates = []
        for process in Path("/proc").glob("[0-9]*"):
            try:
                args = (process / "cmdline").read_bytes().split(b"\0")
                if (
                    b"/diagnostic/sender_scheduling_probe.py" in args
                    and token.encode() in args
                ):
                    candidates.append(process)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if len(candidates) != 1:
            raise RuntimeError(f"expected one sender, found {candidates}")
        process = candidates[0]
        pid = int(process.name)
        save(
            output / "target.json",
            dict(
                host_tid=pid,
                status=(process / "status").read_text(),
                cmdline=(process / "cmdline").read_bytes().decode().split("\0"),
            ),
        )
        instance.mkdir()

        # Write the supplied value as JSON.
        def write(name, value):
            (instance / name).write_text(str(value))

        write("tracing_on", 0)
        write("trace_clock", "mono")
        write("buffer_size_kb", 8192)
        write("options/overwrite", 0)
        events = {
            "sched/sched_switch": f"prev_pid == {pid} || next_pid == {pid}",
            "sched/sched_wakeup": f"pid == {pid}",
            "sched/sched_waking": f"pid == {pid}",
        }
        for syscall in ("pselect6", "recvfrom", "sendto"):
            for edge in ("enter", "exit"):
                events[f"syscalls/sys_{edge}_{syscall}"] = f"common_pid == {pid}"
        for name, predicate in events.items():
            event = instance / "events" / name
            (event / "filter").write_text(predicate)
            (event / "enable").write_text("1")
            (output / (name.replace("/", "-") + ".format")).write_text(
                (event / "format").read_text()
            )
        save(
            output / "trace-config.json",
            dict(
                events=events,
                clock=(instance / "trace_clock").read_text(),
                buffer_kb_per_cpu=8192,
                overwrite=False,
            ),
        )
        save(
            output / "stats-before.json",
            {p.parent.name: p.read_text() for p in instance.glob("per_cpu/cpu*/stats")},
        )
        write("tracing_on", 1)
        before = time.monotonic_ns()
        write("trace_marker", "sender-trace-ready")
        save(
            output / "trace-ready.json",
            dict(
                before_ns=before,
                after_ns=time.monotonic_ns(),
                realtime_ns=time.time_ns(),
            ),
        )
        deadline = time.monotonic() + 60
        while not (output / "trace-stop").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("trace-stop")
            time.sleep(0.05)
        write("trace_marker", "sender-trace-stop")
        write("tracing_on", 0)
        stats = {
            p.parent.name: p.read_text() for p in instance.glob("per_cpu/cpu*/stats")
        }
        save(output / "stats-after.json", stats)
        (output / "trace.txt").write_text((instance / "trace").read_text())
        losses = {}
        for cpu, content in stats.items():
            counters = dict(
                line.split(":", 1) for line in content.splitlines() if ":" in line
            )
            losses[cpu] = {
                key: int(counters[key])
                for key in ("overrun", "commit overrun", "dropped events")
            }
        save(output / "trace-loss.json", losses)
        if any(value for row in losses.values() for value in row.values()):
            raise RuntimeError("lost trace events")
    finally:
        if instance.exists():
            (instance / "tracing_on").write_text("0")
            (instance / "events/enable").write_text("0")
            instance.rmdir()
        subprocess.run(["umount", str(mount)], check=True)


if __name__ == "__main__":
    main()
