import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0,'src/analysis')
from sender_quality import evaluate

base=Path('results/verify/readiness/stage4/practical-v1/comparison')
labels=['lShojabe','gIdWLx7o','ew2u0ceD','sFWOAzbo']
profiles=['r20p0','r20p1','r80p0','r80p1']
read=lambda p:json.loads(Path(p).read_text())
def stamp(p):return datetime.datetime.fromisoformat(Path(p).read_text().strip().replace('Z','+00:00'))
def rolling_peak(values):
    total=sum(values[:1200]);peak=total
    for i in range(1200,len(values)):
        total+=values[i]-values[i-1200];peak=max(peak,total)
    return peak
runs=[]
for label in labels:
    run=Path('results/verify/diagnostic/calibration.'+label)
    seals=read(run/'captured.json')
    assert len(seals)==146
    for ref in seals:assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256']
    plan=read(run/'collection-plan.json');series=[];bounds={}
    for item in plan['collections'][:14]:
        name=item['name'];p=read(run/name/'probe.json');q=evaluate(p['sent_records'],10000)
        replies={r['id']:r['rtt_ms'] for r in p['reply_records']}
        values=sorted(replies.values())
        medians=[statistics.median([replies[i] for i in range(start,start+500) if i in replies]) for start in range(0,10000,500)]
        peaks=[];joint=[]
        for phase in range(5):
            ss=p['sent_records'][phase::5]
            overdue=[int(r['t_send_ms']-r['t_plan_ms']>=50) for r in ss]
            known=[int(late or (r['id'] in replies and r['t_send_ms']+replies[r['id']]>r['t_plan_ms']+100)) for late,r in zip(overdue,ss)]
            peaks.append(rolling_peak(overdue));joint.append(rolling_peak(known))
        practical_sender=(q['metrics']['late_pct']<=1 and q['metrics']['peak_packets_window']<=4 and q['metrics']['gap_ms']['min']>=2.5-1e-8 and max(peaks)<=12 and ('p1-' in name or (len(replies)==10000 and max(joint)<=12)))
        series.append(dict(name=name,returned=len(values),missing=10000-len(values),median_ms=statistics.median(values),p95_ms=values[math.ceil(len(values)*.95)-1],p99_ms=values[math.ceil(len(values)*.99)-1],max_rtt_ms=max(values),late_pct=q['metrics']['late_pct'],late_count=q['metrics']['late_slots'],max_lag_ms=q['metrics']['lag_ms']['max'],old_sender_status=q['status'],old_sender_reasons=q['reasons'],shadow_lag_phase_peaks=peaks,shadow_known_joint_phase_peaks=joint,retrospective_practical_sender_passed=practical_sender,window_medians=medians))
        if name.startswith('baseline-') or name.endswith('-latency'):bounds[name]=[min(medians),max(medians)]
    envelopes=[]
    for profile in profiles:
        p=bounds[profile+'-latency'];target=20 if profile.startswith('r20') else 80
        for which in ('before','after'):
            b=bounds['baseline-'+which];interval=[p[0]-b[1],p[1]-b[0]]
            envelopes.append(dict(profile=profile,baseline=which,observed_range_ms=interval,within_2ms=target-2<=interval[0]<=interval[1]<=target+2))
    capacities=[]
    for item in plan['collections'][14:]:
        rows=(run/item['name']/'window.txt').read_text().splitlines()
        duration=float(rows[3])-float(rows[0]);first,last=read_string=json.loads(rows[2]),json.loads(rows[5])
        capacities.append(dict(name=item['name'],mbit_s=(last['bytes']-first['bytes'])*8/duration/1e6))
    runs.append(dict(run=str(run),started_utc=stamp(run/'started').isoformat(),ended_utc=stamp(run/'ended').isoformat(),duration_s=(stamp(run/'ended')-stamp(run/'started')).total_seconds(),source_commit=(run/'commit').read_text().strip(),seals_verified=len(seals),sent=140000,returned=sum(r['returned'] for r in series),missing=sum(r['missing'] for r in series),old_sender_passed=sum(r['old_sender_status']=='passed' for r in series),retrospective_practical_sender_passed=sum(r['retrospective_practical_sender_passed'] for r in series),observed_envelopes_within_2ms=sum(e['within_2ms'] for e in envelopes),series=series,observed_envelopes=envelopes,capacity=capacities))
result=dict(scope='Descriptive cross-version comparison; retrospective calculations are not new acceptance or failure-rate inference',runs=runs,total_echo_sent=560000,total_duration_s=sum(r['duration_s'] for r in runs),input_raw_unchanged=True)
(base/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
for r in runs:
    print(r['run'],r['duration_s'],'oldsender',r['old_sender_passed'],'retrospectiveSender',r['retrospective_practical_sender_passed'],'observedEnvelopes',r['observed_envelopes_within_2ms'],'missing',r['missing'],'capacity',[round(c['mbit_s'],6) for c in r['capacity']])
    print('sender issues',[(s['name'],s['late_pct'],s['max_lag_ms']) for s in r['series'] if s['old_sender_status']!='passed'])
