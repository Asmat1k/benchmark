import shutil,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,'src/analysis')
from raw import read,write
from synthetic import rehash
from experiments import paired_data
root=Path('/bench/build/d5-r7-synthetic/fixture-9l51pfgl')
source=root/'replacement-aa'; target=root/'chronology'
if target.exists():shutil.rmtree(target)
target.mkdir()
schedule=read(source/'schedule.json');ledger=read(source/'ledger.json')
replacement=next(a for a in ledger['attempts'] if a['replacement_of'] is not None)
others=[a for a in ledger['attempts'] if a['status']=='complete' and a['replacement_of'] is None and a['profile']==replacement['profile'] and a['modes']==replacement['modes']][:2]
attempts=[others[0],replacement,others[1]]
selected=[r for a in attempts for r in schedule['runs'] if r['attempt_id']==a['attempt_id']]
write(target/'ledger.json',dict(schema_version=1,series_id=schedule['series_id'],attempts=list(reversed(attempts))))
for i,run in enumerate(selected):
    folder=target/'raw'/run['run_id'];shutil.copytree(source/'raw'/run['run_id'],folder)
    manifest=read(folder/'manifest.json');start=datetime(2026,11,12,tzinfo=timezone.utc)+timedelta(seconds=i*90)
    manifest.update(started_utc=start.isoformat(),ended_utc=(start+timedelta(seconds=80)).isoformat());write(folder/'manifest.json',manifest);rehash(folder)
with patch('experiments.completed_series',return_value=(schedule,selected,[])):
    pairs,_=paired_data(target,dict(design='aa'))
assert [p['attempt_id'] for p in pairs]==[a['attempt_id'] for a in attempts]
assert [p['sides'][0]['run_id'] for p in pairs]==[selected[i]['run_id'] for i in (0,2,4)]
print('CHRONOLOGY PASSED replacement in middle of same mode/profile; order follows validated manifest chronology, not reversed ledger')
