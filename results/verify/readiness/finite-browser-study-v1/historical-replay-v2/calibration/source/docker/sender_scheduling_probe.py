import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace

import sender_diagnostic_probe as diagnostic


def wait_for(path):
    deadline = time.monotonic() + 60
    while not path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(str(path))
        time.sleep(.02)


if __name__ == '__main__':
    ready, go = map(Path, sys.argv[3:5])
    metadata = dict(pid=os.getpid(), tid=threading.get_native_id(),
                    monotonic_ns=time.monotonic_ns(), realtime_ns=time.time_ns())
    ready.write_text(json.dumps(metadata))
    wait_for(go)
    if sys.argv[1] == 'selftest':
        for _ in range(20):
            diagnostic.timed_select([], [], [], .005)
        left, right = socket.socketpair()
        with diagnostic.TimedSocket(fileno=left.detach()) as sender, right:
            sent = [time.monotonic_ns()]
            sender.send(diagnostic.probe.packet(0, 256, b'selftest'))
            diagnostic.timed_receive(right, sent, 256, b'selftest')
        print(json.dumps(dict(metadata=metadata, trace=diagnostic.trace)))
    else:
        probe = diagnostic.probe
        probe.COUNT = 1500
        probe.select.select = diagnostic.timed_select
        probe.receive = diagnostic.timed_receive
        probe.socket.socket = diagnostic.TimedSocket
        starts = []
        def monotonic_ns():
            value = time.monotonic_ns()
            if not starts:
                starts.append(value)
            return value
        probe.time = SimpleNamespace(monotonic_ns=monotonic_ns, monotonic=time.monotonic)
        before = diagnostic.usage()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            probe.send(sys.argv[1], False, sys.argv[2])
        result = json.loads(output.getvalue())
        result.update(diagnostic_only=True, start_ns=starts[0], metadata=metadata, usage_before=before,
                      usage_after=diagnostic.usage(), trace=diagnostic.trace)
        print(json.dumps(result))
