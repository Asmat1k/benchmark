import datetime
import json
from pathlib import Path
import sys

sys.path[:0]=['src/analysis','docker']
from admission import ref,sources,release
from browser_bandwidth import load_rates
from diagnostic_input import diagnostic_raw,generator_run
from raw import read,require,write
from schedule import make_schedule

base=Path('results/verify/readiness/stage4/release-v4');directory=Path('results/verify/diagnostic/browser-bandwidth-v4.9r51339s');execution=base/'bandwidth-execution.i3D0OccS'
hashes=sources();require(hashes==read(base/'source-inventory.json'),'current source inventory')
require(release()=='494e1a99bf9c92bd2a26af7dce6a8752af23d448','release identity')
require((execution/'exit').read_text().strip()=='0','collection exit')
require((execution/'identity-before.json').read_bytes()==(execution/'identity-after.json').read_bytes(),'collection identity changed')
from admission import checked
identity=read(execution/'identity-after.json')
for path,sha in identity['files'].items():checked(dict(path=path,sha256=sha))
schedule=read(directory/'schedule.json');expected=make_schedule('diagnostic',directory.name,1,1,datagrams=True,baseline=True);expected['generator_hz']=20
require(schedule==expected and len(schedule['runs'])==3,'fixed full schedule')
require(not (directory/'STOP').exists(),'collection STOP')
require(read(directory/'ledger.json')==dict(schema_version=1,series_id=directory.name,attempts=[dict(b,status='complete') for b in schedule['blocks']]),'incomplete ledger')
require(read(directory/'queue.json')==[],'pending queue')
context=read(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json'));require(read(directory/'context.json')==context,'external ENV mismatch')
observed=[];evidence=[ref(directory/name) for name in ('schedule.json','ledger.json','queue.json','context.json')]
for run in schedule['runs']:
 folder=diagnostic_raw(directory,run,schedule,context,hashes)
 manifest=read(folder/'manifest.json');require(manifest['commit']=='494e1a99bf9c92bd2a26af7dce6a8752af23d448' and not manifest['dirty'],'raw release/dirty')
 rates=load_rates(folder);summary=generator_run(folder,20)
 require(summary['measurement_slots']==1200 and summary['miss']==0,'missing measurement slots')
 require(summary['oom']==0 and summary['router_backlog_reviewed'],'resource/queue anomaly')
 observed.append(dict(mode=run['mode'],run_id=run['run_id'],rates=rates,completion=read(folder/'completion.json'),stabilization=read(folder/'stabilization.json'),resources=dict(window=summary['resource_window'],samples=len(summary['resource_samples']),oom=summary['oom'],router_peak_backlog_bytes=summary['router_peak_backlog_bytes'],browser_cpu_pct_limit=summary['browser_cpu_pct_limit'],server_cpu_pct_limit=summary['server_cpu_pct_limit'],browser_throttling_pct=summary['browser_throttling_pct'],server_throttling_pct=summary['server_throttling_pct']),descriptive_timing=dict(observed_hz=summary['observed_hz'],lag_p99_ms=summary['lag_p99_ms'],miss=summary['miss'])))
 evidence.extend(ref(p) for p in sorted(folder.iterdir()) if p.is_file())
require({r['mode'] for r in observed}=={'WS','WT-S','WT-D'},'mode coverage')
result=dict(status='raw_collection_accepted',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewer='Codex; full standard raw validator and primary counter/resource review',BW_RUN=str(directory),execution=str(execution),release_commit=release(),environment=ref(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json')),source_hashes=hashes,runs=observed,evidence=evidence,limitations=['No capacity/fraction computed until new full calibration saturation data','Descriptive resource/timing statistics do not constitute formal generator gate','Rates include setup/warmup/measurement/drain bytes divided by60s; no subtraction or frequency-times-payload estimate'])
output=base/'browser-bandwidth-v4-raw-review.json';require(not output.exists(),'review already exists');write(output,result)
print(output)
for row in observed:print(row['mode'],row['descriptive_timing'],[(r['direction'],r['bytes'],r['mbit_s_upper']) for r in row['rates']])
