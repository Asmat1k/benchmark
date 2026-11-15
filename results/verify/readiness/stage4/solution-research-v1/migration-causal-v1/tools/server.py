import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import time

mode, token, directory, count = sys.argv[1:]
out = Path(directory)
records = []

def stop(signum, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
with socket.socket(socket.AF_UNIX if mode == 'unix' else socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind('/tmp/echo-selftest' if mode == 'unix' else ('', 29543))
    (out/'server-ready.json').write_text(json.dumps(dict(pid=os.getpid(), mono_ns=time.monotonic_ns(), token=token)))
    while not (out/'server-go').exists():
        time.sleep(.01)
    try:
        while not int(count) or len(records) < int(count):
            before = time.monotonic_ns()
            data, peer = sock.recvfrom(65535)
            received = time.monotonic_ns()
            if len(data) != 256:
                raise ValueError('unexpected payload length')
            identity, tag = struct.unpack('!I8s', data[:12])
            sending = time.monotonic_ns()
            sent = sock.sendto(data, peer)
            after = time.monotonic_ns()
            if sent != 256:
                raise ValueError('short echo')
            records.append(dict(id=identity, tag=tag.hex(), before_recv_ns=before, received_ns=received, before_send_ns=sending, after_send_ns=after))
    finally:
        (out/'server-records.json').write_text(json.dumps(records)+'\n')

    if int(count):
        time.sleep(1)
