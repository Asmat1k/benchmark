import hashlib
import json
import select
import socket
import struct
import sys
import time

PORT = 29543
FRAME_BYTES = 256
PERIOD_NS = 10_000_000
COUNT = 10_000
MIN_ECHO_GAP_NS = 2_500_000
MAX_ECHO_WAIT_NS = 1_000_000


def collection_tag(collection_id):
    return hashlib.sha256(collection_id.encode()).digest()[:8]


def packet(number, size, tag):
    return struct.pack("!I8s", number, tag) + bytes(size - 12)


def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("", PORT))
        print("ready", flush=True)
        while True:
            data, peer = sock.recvfrom(65535)
            if len(data) == FRAME_BYTES:
                sock.sendto(data, peer)


def receive(sock, sent, size, tag):
    data = sock.recv(65535)
    received = time.monotonic_ns()
    identity, = struct.unpack("!I", data[:4])
    if data != packet(identity, size, tag) or identity >= len(sent):
        raise ValueError("unexpected echo payload")
    return dict(id=identity, rtt_ms=(received-sent[identity])/1e6)


def send(peer, saturation, collection_id):
    tag = collection_tag(collection_id)
    period = 800_000 if saturation else PERIOD_NS
    count = 90_000 if saturation else COUNT
    size = 1200 if saturation else FRAME_BYTES
    sent, replies = [], []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((peer, PORT))
        first_uptime = float(open('/proc/uptime').read().split()[0]) if saturation else None
        start = time.monotonic_ns()
        for number in range(count):
            due = start + period * number
            if not saturation and sent:
                due = max(due, sent[-1] + MIN_ECHO_GAP_NS)
            while (remaining := due - time.monotonic_ns()) > 0:
                timeout_ns = remaining if saturation else min(remaining, MAX_ECHO_WAIT_NS)
                if select.select([sock], [], [], timeout_ns / 1e9)[0]:
                    replies.append(receive(sock, sent, size, tag))
            frame = packet(number, size, tag)
            timestamp = time.monotonic_ns()
            sock.send(frame)
            sent.append(timestamp)
        if not saturation:
            until = time.monotonic() + 2
            while (remaining := until - time.monotonic()) > 0 and select.select([sock], [], [], remaining)[0]:
                replies.append(receive(sock, sent, size, tag))
        last_uptime = float(open('/proc/uptime').read().split()[0]) if saturation else None
    if saturation:
        print(json.dumps(dict(collection_id=collection_id, sent=count, frame_bytes=size, first_ns=sent[0], last_ns=sent[-1],
                              first_uptime=first_uptime, last_uptime=last_uptime)))
    else:
        print(json.dumps(dict(collection_id=collection_id, sent=count, frame_bytes=size, frequency_hz=100, reply_records=replies,
                              rtt_ms=[r['rtt_ms'] for r in replies],
                              sent_records=[dict(id=i, t_plan_ms=i*10, t_send_ms=(t-start)/1e6)
                                            for i,t in enumerate(sent)])))


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        serve()
    elif sys.argv[1] in ("echo", "saturate"):
        send(sys.argv[2], sys.argv[1] == "saturate", sys.argv[3])
    else:
        raise SystemExit(2)
