import hashlib
import json
from pathlib import Path
import time

BASE=Path('results/verify/readiness/stage4/imperfection-policy-v1/sensitivity')
WINDOW=1200
PHASES=5
PERIOD_MS=50
DEADLINE_MS=100
BAD_LIMIT=12

def rolling(values):
    prefix=[0]
    for v in values:prefix.append(prefix[-1]+int(v))
    return [prefix[i+WINDOW]-prefix[i] for i in range(len(values)-WINDOW+1)]

started=time.monotonic();runs=[]
for label in ('calibration.lShojabe','calibration.gIdWLx7o','calibration.ew2u0ceD'):
    run=Path('results/verify/diagnostic')/label
    refs=json.loads((run/'captured.json').read_text())
    assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in refs)
    rows=[]
    for item in json.loads((run/'collection-plan.json').read_text())['collections'][:14]:
        p=json.loads((run/item['name']/'probe.json').read_text())
        sends=p['sent_records'];reply={r['id']:r['rtt_ms'] for r in p['reply_records']}
        phases=[]
        for phase in range(PHASES):
            ss=sends[phase::PHASES]
            overdue=[r['t_send_ms']-r['t_plan_ms']>=PERIOD_MS for r in ss]
            known=[a or (r['id'] in reply and r['t_send_ms']+reply[r['id']]>r['t_plan_ms']+DEADLINE_MS) for a,r in zip(overdue,ss)]
            unknown=[not a and r['id'] not in reply for a,r in zip(overdue,ss)]
            phases.append(dict(phase=phase,slots=len(ss),windows=len(ss)-WINDOW+1,
                               max_sender_overdue=max(rolling(overdue)),
                               max_known_timing_bad=max(rolling(known)),
                               max_unknown_reply=max(rolling(unknown)),
                               max_bad_if_all_unknown_bad=max(rolling([a or b for a,b in zip(known,unknown)]))))
        rows.append(dict(name=item['name'],phases=phases,
                         max_sender_overdue=max(p['max_sender_overdue'] for p in phases),
                         max_known_timing_bad=max(p['max_known_timing_bad'] for p in phases),
                         missing=len(sends)-len(reply)))
    runs.append(dict(run=str(run),series=rows))

times=[];last=None
for i in range(10000):
    actual=max(i*10+(500 if i==5000 else 0),last+2.5 if last is not None else 0)
    times.append(actual);last=actual
counts=[]
for phase in range(PHASES):
    counts.append(max(rolling([times[i]-i*10>=PERIOD_MS or times[i]+.6>i*10+DEADLINE_MS for i in range(phase,10000,PHASES)])))
assert counts==[13,12,12,12,12]
result=dict(status='exploratory_shadow_guard_prototype_not_admission',
            definition='Five IDmod5 subsamples of100Hz UDPsendtimes;1200 consecutive planned50msslots perwindow;all4005windows retained',
            proposed_count_limit=BAD_LIMIT,limit_origin='existing1percentagepoint*1200plannedslots, notobserved69ms',
            sender_overdue='UDPlag>=50ms underobserved100Hzload, not actualbrowserreplay',
            receive_unknown='Missingreply has unknownRTT; do not classifytiming as good; loss0counterevidence needed forcompleteproxy',
            synthetic_counterexample=dict(pause_ms=500,catchup_gap_ms=2.5,assumed_rtt_ms=.6,phase_max_bad=counts,rejected=True),
            runs=runs,elapsed_s=time.monotonic()-started,
            limitations=['Countlimit provisional; not deployed','No estimate ofcounterfactualTCP/QUICmetrics','Adjacentphases/windows areoverlappingnotindependent','Noindividualmaxpauseguarantee','Lag-onlyproxyallprofiles;completejointtimingproxyonlyloss0','DoesnotjustifymeanrateorQbiasguarantee'])
with (BASE/'shadow.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('elapsed',result['elapsed_s'],'synthetic500msexample',counts)
for run in runs:
    print(run['run'],'max_sender',max(r['max_sender_overdue'] for r in run['series']),
          'max_joint_loss0',max(r['max_known_timing_bad'] for r in run['series'] if 'p1-' not in r['name']))
