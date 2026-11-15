import json
from pathlib import Path
import sys

sys.path[:0]=['src/analysis','docker']
from admission import checked, ref, sources
from acceptance import probe_records
from calibration_report import collection_plan, directions, rate
from calibration_observed import sender_check, observed_intervals
from browser_bandwidth import fractions
from raw import read, write

base=Path('results/verify/readiness/stage4/practical-v1/full-calibration')
output=base/'review'
run=Path('results/verify/diagnostic/calibration.sFWOAzbo')
execution=base/'execution.trv5h_3g'
assert (run/'exit').read_text().strip()==(execution/'exit').read_text().strip()=='0'
assert read(execution/'identity-before.json')==read(execution/'identity-after.json')
for path,digest in read(execution/'identity-after.json').items():
    mapped=Path(path)
    if mapped.is_absolute(): mapped=mapped.relative_to('/Users/dobrov/Desktop/Code/ITMO/benchmark')
    checked(dict(path=str(mapped),sha256=digest))
seals=read(run/'captured.json')
for entry in seals: checked(entry)
assert {r['path'] for r in seals}=={str(p) for p in run.rglob('*') if p.is_file() and p.name not in ('captured.json','exit','ended')}
plan=read(run/'collection-plan.json')
assert plan==collection_plan()==read(base/'collection-plan.json')
assert {p.name for p in run.iterdir() if p.is_dir()}=={c['name'] for c in plan['collections']}
assert read(run/'sources-before.json')==read(run/'sources-after.json')==sources()
assert (run/'commit').read_text().strip()=='acce5946499b7471bc35965919f3cdc910a7922c'
env=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
assert read(run/'context-before.json')==read(run/'context-after.json')==read(env)
features=('tcp-segmentation-offload','generic-segmentation-offload','generic-receive-offload','large-receive-offload')
for name in ('browser-route.txt','server-route.txt','router-links.txt'):
    text=(run/name).read_text()
    assert all(f+': off' in text for f in features)
assert '172.28.20.10 via 172.28.10.2 dev bench0' in (run/'browser-route.txt').read_text()
assert '172.28.10.10 via 172.28.20.2 dev bench0' in (run/'server-route.txt').read_text()
assert 'test "$(cat "/sys/class/net/$1/mtu")" = 1500' in Path('docker/network.sh').read_text()
for name in ('browser-neighbors','server-neighbors','router-browser-neighbors','router-server-neighbors'):
    assert len(read(run/(name+'.json')))==1 and read(run/(name+'.json'))[0]['state']==['PERMANENT']
echo={};egress=[];series=[]
for item in plan['collections'][:14]:
    name=item['name'];directory=run/name;probe=read(directory/'probe.json')
    assert (probe['sent'],probe['frame_bytes'],probe['frequency_hz'])==(10000,256,100)
    probe_records(probe,enforce_timing=False)
    assert probe['rtt_ms']==[r['rtt_ms'] for r in probe['reply_records']]
    flows=directions(directory,probe)
    lossy='p1-' in name
    quality=sender_check(probe,lossy)
    for role in ('browser','server'):
        assert '0 packets dropped by kernel' in (directory/(role+'.log')).read_text()
    profile=name.rsplit('-',1)[0]
    delay=0 if profile=='baseline' else .01 if profile.startswith('r20') else .04
    for dev,seed in (('to_server',item['forward_seed']),('to_browser',item['reverse_seed'])):
        first,last=[next(q for q in read(directory/('qdisc-'+when+'.json')) if q['kind']=='netem' and q['dev']==dev) for when in ('before','after')]
        assert first['options']==last['options'] and first['handle']==last['handle']
        opt=first['options']
        assert opt['seed']==seed and opt['limit']==1000 and opt['rate']['rate']==1250000
        assert opt.get('delay',{}).get('delay',0)==delay and opt.get('loss-random',{}).get('loss',0)==(.01 if lossy else 0)
        assert opt.get('delay',{}).get('jitter',0)==0 and opt.get('delay',{}).get('correlation',0)==0
        assert first['qlen']==last['qlen']==first['backlog']==last['backlog']==0
        assert last['bytes']-first['bytes']==298*(last['packets']-first['packets'])
    series.append(dict(name=name,quality=quality,flows=flows))
    if profile=='baseline':echo[name.rsplit('-',1)[1]]=probe
    elif name.endswith('-latency'):echo[profile]=probe
    else:
        for flow in flows:
            flow.update(profile=profile,when=name.rsplit('-',1)[1],collection_id=probe['collection_id'])
            if flow['direction']=='forward':flow['probe']=probe
            egress.append(flow)
saturation=[]
for item in plan['collections'][14:]:
    name=item['name'];_,loss,direction=name.split('-');sample=rate(run/name,direction,int(loss)/100)
    assert all(q['qlen']==q['backlog']==0 for q in read(run/name/'qdisc-stable.json') if q['kind']=='netem')
    sample['mbit_s']=sample['forwarded_bytes']*8/sample['duration_s']/1e6
    saturation.append(sample)
bridge=read(Path('results/verify/readiness/stage4/practical-v1/applicability/qualification-and-bw-bridge-v2.json'))
assert bridge['current_sources']==sources() and bridge['environment']==ref(env)
checked(bridge['historical_bw_replay'])
bandwidth=fractions(bridge['bandwidth_loads'],saturation)
write(output/'bandwidth-new-capacity.json',dict(**bandwidth,dependency_bridge=ref(Path('results/verify/readiness/stage4/practical-v1/applicability/qualification-and-bw-bridge-v2.json')),capacity=saturation))
bounds,diagnostics,windows=observed_intervals(echo,dict(observed_period_reviewed=True))
write(output/'numeric-preview.json',dict(status='computed_pending_independent_review_not_published_gate',sealed_files=len(seals),source_count=len(sources()),series=series,bounds=bounds,diagnostics=diagnostics,windows=windows,bandwidth=bandwidth,saturation=saturation))
write(output/'values-before-review.json',dict(method=plan['method']['method'],echo=echo,egress=egress,saturation=saturation))
print('Primary raw checks passed:',len(seals),'seals,',len(series),'echo +',len(saturation),'saturation')
for row in series:
    q=row['quality'];print(row['name'],q['status'],'maxlag',q['metrics']['lag_ms']['max'],'missing',q['missing_reply_count'],'shadowLag',max(max(p['counts']['sender_overdue']) for p in q['shadow_phases']),'joint',max(max(p['counts']['known_timing_bad']) for p in q['shadow_phases']))
print('bounds',bounds,'capacity',[s['mbit_s'] for s in saturation],'browser fraction',bandwidth['main_bandwidth_fraction'])
