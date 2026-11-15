import importlib.util
import json
from pathlib import Path
import time

base=Path(__file__).parent
spec=importlib.util.spec_from_file_location('budget_probe',base/'probe.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
clock=Path('/proc/sys/kernel/sched_schedstats')
recorder=probe.Recorder()
started=time.monotonic_ns()
try:
    values=[recorder.snapshot() for _ in range(1000)]
finally:
    recorder.close()
for left,right in zip(values,values[1:]):
    assert all(a<=b for a,b in zip(left['schedstat'],right['schedstat']))
    assert left['thread_cpu_before_ns']<=right['thread_cpu_before_ns']
    assert left['voluntary']<=right['voluntary'] and left['involuntary']<=right['involuntary']
print(json.dumps(dict(status='offline_counter_selftest_only',snapshots=len(values),elapsed_ns=time.monotonic_ns()-started,
    sched_schedstats=clock.read_text().strip() if clock.exists() else None,
    observer_wall_ns=dict(min=min(r['wall_after_ns']-r['wall_before_ns'] for r in values),max=max(r['wall_after_ns']-r['wall_before_ns'] for r in values)),
    first=values[0],last=values[-1],limitation='Tight-loop offline cost only; not a network observer equivalence test'),indent=2))
