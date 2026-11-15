import contextlib
import io
import json
import resource
import sys
import time

import calibration_probe as probe


# Compute usage.
def usage():
    value = resource.getrusage(resource.RUSAGE_SELF)
    with open("/proc/self/schedstat") as handle:
        scheduler = list(map(int, handle.read().split()))
    return dict(
        wall_ns=time.monotonic_ns(),
        cpu_ns=time.process_time_ns(),
        schedstat=scheduler,
        voluntary=value.ru_nvcsw,
        involuntary=value.ru_nivcsw,
        maxrss_kib=value.ru_maxrss,
    )


trace = []
original_select = probe.select.select
original_receive = probe.receive
original_socket = probe.socket.socket


# Compute timed select.
def timed_select(read, write, error, timeout):
    before = usage()
    result = original_select(read, write, error, timeout)
    after = usage()
    trace.append(
        dict(
            kind="select",
            timeout_ns=round(timeout * 1e9),
            ready=bool(result[0]),
            before=before,
            after=after,
        )
    )
    return result


# Compute timed receive.
def timed_receive(*args):
    before = usage()
    result = original_receive(*args)
    trace.append(dict(kind="receive", id=result["id"], before=before, after=usage()))
    return result


class TimedSocket(original_socket):
    # Send the supplied test data.
    def send(self, data):
        before = usage()
        result = super().send(data)
        trace.append(dict(kind="send", before=before, after=usage()))
        return result


if __name__ == "__main__":
    probe.COUNT = 1500
    probe.select.select = timed_select
    probe.receive = timed_receive
    probe.socket.socket = TimedSocket
    before = usage()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        probe.send(sys.argv[1], False, sys.argv[2])
    result = json.loads(output.getvalue())
    result.update(
        diagnostic_only=True, usage_before=before, usage_after=usage(), trace=trace
    )
    print(json.dumps(result))
