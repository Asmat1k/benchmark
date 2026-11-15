import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path.cwd()
BASE = Path('results/verify/readiness/stage4/practical-v1/release-v2')
RUN = Path('results/verify/diagnostic/timer-timer.JHhehRVV')
EXECUTION = BASE/'timer-execution.sp770th8'
read = lambda p: json.loads(p.read_text())
rows = lambda p: [json.loads(x) for x in p.read_text().splitlines()]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
head = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
report_path = Path(str(RUN)+'-report/report.json')
report = read(report_path)
assert head.startswith('acce594') and report['status'] == 'passed'
assert (EXECUTION/'exit').read_text().strip() == '0' and read(EXECUTION/'execution.json')['exit'] == 0
assert set(p.name for p in (RUN/'raw').iterdir()) == {'b0-a0-m0','b0-a0-m1'}
assert not (RUN/'STOP').exists() and not (RUN/'quarantine').exists()
assert read(RUN/'queue.json') == []
schedule = read(RUN/'schedule.json')
assert read(RUN/'ledger.json') == dict(schema_version=1,series_id=RUN.name,attempts=[dict(b,status='complete') for b in schedule['blocks']])
context = read(RUN/'context.json')
assert context['config']['plan'] == read(Path('configs/plan.json'))
assert all(sha(Path(p)) == h for p,h in context['bindings'].items())
assert report['environment'] == dict(path=str(RUN/'context.json'),sha256=sha(RUN/'context.json'))
assert all(sha(Path(p)) == h for p,h in report['source_hashes'].items())
assert report['source_hashes'] == read(BASE/'source-inventory.json')
for path,digest in report['integrity']['files'].items():
    target = ROOT/path.removeprefix('/bench/') if path.startswith('/bench/') else Path(path)
    assert sha(target) == digest
stdout = (EXECUTION/'stderr.log').read_text()
summaries = []
for run in schedule['runs']:
    folder = RUN/'raw'/run['run_id']
    hashes = dict((name,digest) for digest,name in (x.split('  ',1) for x in (folder/'SHA256SUMS').read_text().splitlines()))
    assert hashes == {p.name:sha(p) for p in folder.iterdir() if p.name != 'SHA256SUMS'}
    manifest = read(folder/'manifest.json')
    assert manifest['commit'] == head and manifest['dirty'] is False and manifest['technical_valid']
    assert read(folder/'context.json') == context
    if run == schedule['runs'][0]:
        assert read(folder/'collection-sources.json') == report['source_hashes']
    else:
        assert not (folder/'collection-sources.json').exists()
    assert all(manifest[k] == v for k,v in run.items())
    resources = rows(folder/'resources.jsonl')
    assert all(r['oom'] == 0 and r['throttled_usec'] == 0 for r in resources)
    prefixes = ['baseline']+sorted(p.name.removesuffix('-marker') for p in folder.glob('stabilization-*-marker'))
    assert prefixes == ['baseline','stabilization-1']
    selections = {}
    for prefix in prefixes:
        marker = int((folder/(prefix+'-marker')).read_text())
        window = dict(start_usec=marker+10000,end_usec=marker+4520000)
        recorded = read(folder/(prefix+'-cpu.json'))
        assert recorded['window'] == window and recorded['run_id'] == run['run_id']
        assert (folder/(prefix+'-selector.exit')).read_text().strip() == '0'
        assert (folder/(prefix+'-selector.stderr.log')).read_text() == ''
        checked = {}
        for role in ('browser','server','router'):
            series = rows(folder/(prefix+'-'+role+'.jsonl'))
            assert all(b['sample_index'] == a['sample_index']+1 and b['end_usec'] > a['end_usec'] for a,b in zip(series,series[1:]))
            selected = [r for r in series if r['cpu_start_lower_usec'] > window['start_usec'] and r['cpu_end_upper_usec'] <= window['end_usec']]
            assert len(selected) >= 2 and recorded['roles'][role]['selected'] == selected
            assert all(r in resources for r in selected)
            peak = max((100*r['cpu_usage_usec']+r['interval_usec']-1)//r['interval_usec'] for r in selected)
            assert recorded['roles'][role]['peak_ceil_pct'] == peak
            checked[role] = dict(ids=[r['sample_index'] for r in selected],peak_ceil_pct=peak)
        selections[prefix] = checked
    comparison = read(folder/'stabilization-1-comparison.json')
    assert comparison['status'] == 'passed'
    for role in selections['baseline']:
        assert selections['stabilization-1'][role]['peak_ceil_pct'] <= selections['baseline'][role]['peak_ceil_pct']
    queues = rows(folder/'stabilization-1-queues.jsonl')
    assert len(queues) == 11
    for sample in queues+[read(folder/'qdisc-stable.json')]:
        netem = [q for q in sample if q['kind'] == 'netem']
        assert {q['dev'] for q in netem} == {'to_browser','to_server'}
        assert all(q['backlog'] == q['qlen'] == q['drops'] == 0 for q in netem)
    assert read(folder/'stabilization.json')['wait_limit_s'] == 30
    names = (folder/'service-names.txt').read_text().splitlines()
    assert all(name.strip('"').lstrip('/')+' Removed' in stdout for name in names)
    clock_result = None
    if run == schedule['runs'][0]:
        samples = read(folder/'clock-samples.json')
        assert len(samples) == 100001 and all(math.isfinite(x) for x in samples)
        delta = [b-a for a,b in zip(samples,samples[1:])]
        clock_result = dict(count=100000,monotonic=min(delta)>=0,step_ms=min(x for x in delta if x>0),p99_overhead_ms=sorted(delta)[98999])
        assert clock_result['monotonic'] and 0 < clock_result['step_ms'] <= .1 and clock_result['p99_overhead_ms'] <= .1
        assert all(report['result']['timer'][k] == v for k,v in clock_result.items())
    else:
        assert not (folder/'clock-samples.json').exists()
    summaries.append(dict(run_id=run['run_id'],mode=run['mode'],sealed_files=len(hashes),resource_rows=len(resources),selections=selections,queue_snapshots=11,clock_result=clock_result,cleanup_removed_from_execution_log=True))
output = dict(status='passed_internal_independent_raw_review',source_commit=head,collection=str(RUN),execution=str(EXECUTION),runs=summaries,report_integrity_files=len(report['integrity']['files']),report=dict(path=str(report_path),sha256=sha(report_path)),limitations=['Canonical validator replay performed separately by root; independent checks here use Python standard library','Only first diagnostic run requests100001clock calls; second run validates short WT-S cycle','No independent actual Docker inventory queried; cleanup confirmed by execution removal logs','Deadline enforced by shell source; individual queue test timestamps are not separately recorded','Not stage4 completion or calibration/generator acceptance'])
target = BASE/'timer-independent-review.json'
assert not target.exists()
target.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(dict(output=str(target),runs=summaries),indent=2))
