import json
import sys
from hashlib import sha256
from pathlib import Path
import numpy as np

sys.path.insert(0,'src/analysis')
from raw import read, validate_raw, validate_hashes
from analyze import run_identity

base=Path('results/verify/diagnostic/timer-timer.dkKn7fVu')
report=read(base.with_name(base.name+'-WS-report')/'report.json')
schedule=read(base/'schedule.json')
for run in schedule['runs']:
    raw=base/'raw'/run['run_id']
    run_identity(raw,run)
    validate_raw(raw,base/'schedule.json')
    print(raw.name,run['mode'],len(validate_hashes(raw)),'files verified')
clock=read(base/'raw'/schedule['runs'][0]['run_id']/'clock-samples.json')
steps=np.diff(clock)
expected=dict(count=len(steps),monotonic=bool(np.all(steps>=0)),step_ms=float(min(steps[steps>0])),p99_overhead_ms=float(np.sort(steps)[98999]))
assert len(clock)==100001 and all(report['result']['timer'][k]==v for k,v in expected.items())
assert expected['monotonic'] and expected['step_ms']<=0.1 and expected['p99_overhead_ms']<=0.1 and report['status']=='passed'
for path,digest in report['integrity']['files'].items():
    assert sha256(Path(path.removeprefix('/bench/')).read_bytes()).hexdigest()==digest, path
print(expected, len(report['integrity']['files']), 'receipt file hashes verified')
