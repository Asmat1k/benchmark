import copy
import json
from pathlib import Path
import sys

sys.path[:0]=['src/analysis','docker']
from admission import checked, ref, sources
from raw import read, write
from sender_quality import evaluate
from browser_bandwidth import load_rates

base=Path('results/verify/readiness/stage4/practical-v1/applicability')
run=Path('results/verify/diagnostic/sender-diagnostic.6uYg6iiy')
assert (run/'exit').read_text().strip()=='0'
seals=read(run/'captured.json')
assert len(seals)==79
for binding in seals: checked(binding)
hashes=sources()
old=read(run/'sources-before.json')
assert old==read(run/'sources-after.json')
assert {p for p,h in old.items() if hashes[p]!=h}=={'src/analysis/sender_quality.py'}
qualities=[]
for name in ('baseline-q1','baseline-q2','baseline-q3'):
    probe=read(run/name/'probe.json')
    actual=evaluate(probe['sent_records'],10000)
    assert actual==read(run/name/'sender-quality.json') and actual['status']=='passed'
    qualities.append(dict(name=name,quality=actual,probe=ref(run/name/'probe.json')))
oldenv=read(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json'))
newenvpath=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
newenv=read(newenvpath)
assert oldenv['config']['plan']['calibration']!=newenv['config']['plan']['calibration']
a,b=copy.deepcopy(oldenv),copy.deepcopy(newenv)
for value in (a,b):
    del value['bindings']['docs/protocol.md']
    del value['config']['plan']['calibration']
assert a==b
historical=read(base/'historical-bandwidth-replay.json')
loads=[]
for item in read(Path('results/verify/diagnostic/browser-bandwidth-v4.9r51339s/schedule.json'))['runs']:
    folder=Path('results/verify/diagnostic/browser-bandwidth-v4.9r51339s/raw')/item['run_id']
    loads.append(dict(mode=item['mode'],rates=load_rates(folder)))
assert loads==historical['result']['loads']
write(base/'qualification-and-bw-bridge-v2.json',dict(scope='Dependency applicability only, not calibration/generator/early gate pass',
    current_sources=hashes,old_qualification_sources=old,qualification=ref(run/'captured.json'),
    qualification_seals_checked=len(seals),default_sender_results=qualities,
    default_semantics='enforce_max_lag=True preserves historical sender-v2 including maxlag50ms; exact three result replay matches',
    environment=ref(newenvpath),environment_delta=['bindings.docs/protocol.md','config.plan.calibration'],
    failed_timer_status_preserved=True,bandwidth_loads=loads,historical_bw_replay=ref(base/'historical-bandwidth-replay.json'),
    bandwidth_scope='Unchanged baseline browser workload, frames, network, image IDs and accounting; measured CPU observer/idle selection revised with all rows retained; network-none markers add no browser/router flow bytes; new saturation required; historical ratios not current calibration',
    historical_bw_sources=historical['source_hashes']))
print('Three default sender quality replays exact; ENV semantic delta checked; old/current BW load_rates exact.')
