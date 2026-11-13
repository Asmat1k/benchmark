from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import numpy as np

sys.path.insert(0, 'src/analysis')
from admission import checked, ref, sources, validate_checks
from collection import measured
from raw import read, validate_hashes, validate_raw
from analyze import run_identity

head = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
base = Path('results/verify/diagnostic/timer-timer.RKMg3sCH')
package = base.with_name(base.name+'-report')
report = read(package/'report.json')
actual = sources()
assert head=='d1573e82d7b61d01fb9df88f52469f256031f1d3' and report['source_hashes']==actual
for name, digest in actual.items():
    assert sha256(subprocess.check_output(['git','show',head+':'+name])).hexdigest()==digest
schedule = read(base/'schedule.json')
for run in schedule['runs']:
    folder = base/'raw'/run['run_id']
    m = run_identity(folder, run)
    assert m['commit']==head and m['dirty'] is False
    validate_raw(folder, base/'schedule.json')
    print(run['mode'], len(validate_hashes(folder)), 'files, clean release', m['commit'])
folder = base/'raw'/schedule['runs'][0]['run_id']
samples = read(folder/'clock-samples.json')
delta = np.diff(samples)
result = dict(count=len(delta),monotonic=bool(np.all(delta>=0)),step_ms=float(min(delta[delta>0])),p99_overhead_ms=float(np.sort(delta)[98999]))
assert result==measured(read(package/'input.json')) and report['status']=='passed'
assert all(report['result']['timer'][k]==v for k,v in result.items()) and len(samples)==100001
for path,digest in report['integrity']['files'].items():
    assert sha256(Path(path.removeprefix('/bench/')).read_bytes()).hexdigest()==digest
partial=read(Path('results/verify/readiness/host/partial-verify.json'))
code=validate_checks(partial['document'])
assert partial['kind']=='real' and not partial['final'] and partial['source_hashes']==actual and partial['environment']==report['environment'] and code==2
checks=partial['document']['checks']
assert [r['id'] for r in checks if r['status']=='passed']==['timer']
assert sum(r['mandatory'] and r['status']=='not_run' and r['reason']=='gate_report_not_provided' for r in checks)==9
assert next(r for r in checks if r['id']=='timer')['evidence']==[ref(package/'report.json')]
print('Clock sampled on',schedule['runs'][0]['mode'],len(samples),'readings:',result)
print(len(actual),'source SHA;',len(report['integrity']['files']),'report file SHA; partial verify', code)
