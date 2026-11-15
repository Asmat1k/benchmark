import contextlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time
import calibration_probe

mode, token, peer, collection, directory = sys.argv[1:]
out=Path(directory)
(out/'sender-ready.json').write_text(json.dumps(dict(pid=os.getpid(),token=token,mono_ns=time.monotonic_ns())))
while not (out/'sender-go').exists():
    time.sleep(.01)
with (out/'probe.json').open('x') as output, contextlib.redirect_stdout(output):
    if mode=='udp':
        calibration_probe.send(peer,False,collection)
    else:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.settimeout(2)
            for i in range(20):
                data=struct.pack('!I8s',i,b'selftest')+bytes(244)
                sock.sendto(data,(peer,29543))
                assert sock.recv(1024)==data
(out/'sender-done').write_text('0\n')
