import collections
import json
from pathlib import Path
import re
import time

start=time.monotonic()
path=Path('results/verify/diagnostic/transition-trace.jNq2hqdS/r80p1-check/trace.txt')
sequence=[]
for line in path.read_text().splitlines():
    if 'net_dev_queue: dev=to_server ' not in line:
        continue
    match=re.search(r'\[(\d+)\].*? (\d+\.\d+):',line)
    sequence.append((int(match[1]),float(match[2])))
assert len(sequence)==10000
changes=[i for i in range(1,len(sequence)) if sequence[i][0]!=sequence[i-1][0]]
print(json.dumps(dict(scope='saved prior instrumented trace; not full failed run',packets=len(sequence),cpus=dict(collections.Counter(cpu for cpu,t in sequence)),sender_queue_cpu_changes=len(changes),first_changes=changes[:30],elapsed_s=time.monotonic()-start),indent=2))
