import contextlib
import gc
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from array import array

import calibration_probe as probe

ready, go = map(Path, sys.argv[3:5])
metadata = dict(pid=os.getpid(), tid=threading.get_native_id(),
                monotonic_ns=time.monotonic_ns(), realtime_ns=time.time_ns())
ready.write_text(json.dumps(metadata))
deadline = time.monotonic() + 30
while not go.exists():
    if time.monotonic() > deadline:
        raise TimeoutError('sender-go')
    time.sleep(.02)

capacity = 4096
gc_records = array('q', [0]) * (capacity * 5)
gc_count = 0

def gc_event(phase, info):
    global gc_count
    if gc_count < capacity:
        index = gc_count * 5
        gc_records[index] = time.monotonic_ns()
        gc_records[index+1] = time.process_time_ns()
        gc_records[index+2] = phase == 'start'
        gc_records[index+3] = info['generation']
        gc_records[index+4] = info.get('collected', 0)
    gc_count += 1

starts = []
def monotonic_ns():
    value = time.monotonic_ns()
    if not starts:
        starts.append(value)
    return value

probe.time = SimpleNamespace(monotonic_ns=monotonic_ns, monotonic=time.monotonic)
output = io.StringIO()
gc.callbacks.append(gc_event)
cpu_before = time.process_time_ns()
try:
    with contextlib.redirect_stdout(output):
        probe.send(sys.argv[1], False, sys.argv[2])
finally:
    end_ns = time.monotonic_ns()
    cpu_after = time.process_time_ns()
    gc.callbacks.remove(gc_event)
result = json.loads(output.getvalue())
result.update(diagnostic_only=True, metadata=metadata, start_ns=starts[0], end_ns=end_ns,
              process_cpu_ns=cpu_after-cpu_before, gc_count=gc_count,
              gc_records=[dict(wall_ns=gc_records[i*5], cpu_ns=gc_records[i*5+1],
                               phase='start' if gc_records[i*5+2] else 'stop',
                               generation=gc_records[i*5+3], collected=gc_records[i*5+4])
                          for i in range(min(gc_count,capacity))],
              gc_records_complete=gc_count<=capacity)
print(json.dumps(result))
