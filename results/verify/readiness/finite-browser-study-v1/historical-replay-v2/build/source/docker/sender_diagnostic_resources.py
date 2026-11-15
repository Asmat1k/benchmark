import json
from pathlib import Path
import sys
import time

CGROUP_FILES = ('cpu.stat', 'cpu.max', 'cpu.pressure', 'memory.current', 'memory.max',
                'memory.events', 'memory.stat', 'memory.pressure', 'io.pressure', 'pids.current')
PROC_FILES = ('stat', 'meminfo', 'loadavg', 'pressure/cpu', 'pressure/memory',
              'net/snmp', 'net/udp', 'net/softnet_stat')

for _ in range(int(sys.argv[1])):
    record = dict(wall_ns=time.monotonic_ns())
    for root, names in ((Path('/sys/fs/cgroup'), CGROUP_FILES), (Path('/proc'), PROC_FILES)):
        for name in names:
            path = root / name
            if path.exists():
                record[str(path)] = path.read_text()
    print(json.dumps(record), flush=True)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).touch()
    if len(sys.argv) > 3 and Path(sys.argv[3]).exists():
        break
    time.sleep(1)
