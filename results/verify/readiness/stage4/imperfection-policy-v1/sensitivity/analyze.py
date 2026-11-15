import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
sys.path[:0]=['src/analysis']
from metrics import run_metrics

BASE=Path('results/verify/readiness/stage4/imperfection-policy-v1/sensitivity')
RAW=Path('results/verify/diagnostic/browser-bandwidth-v4.9r51339s')
PERIOD_MS=50
DURATIONS_MS=(50,100,200,500)
BATCH=32
started=time.monotonic()

def read(path):return json.loads(path.read_text())

def metric_arrays(plan,sent,echo):
    complete=np.isfinite(echo)&(echo<=plan+5000)
    values=np.where(complete,echo-sent,np.nan)
    return dict(Q_ms=np.nanquantile(values,.95,axis=1,method='inverted_cdf'),
                S_pct=np.count_nonzero(complete&(echo<=plan+100),axis=1)*100/len(plan),
                U_pct=(len(plan)-np.count_nonzero(complete,axis=1))*100/len(plan))

def scalar_check(slots,model,onset,duration):
    changed=[dict(s) for s in slots]
    for s in changed:
        echo=s['first_correct_echo_ms']
        if model=='receive_service' and echo is not None and onset<=echo<onset+duration:
            s['first_correct_echo_ms']=onset+duration
        if model=='planned_slot_suppression' and onset<=s['t_plan_ms']<onset+duration:
            s.update(t_send_ms=None,first_correct_echo_ms=None,send_state='scheduler_miss',send_lag_ms=None)
    official,_=run_metrics(changed,[],[],100,5000)
    return {k:official[k] for k in ('Q_ms','S_pct','U_pct')}

review=read(Path('results/verify/readiness/stage4/release-v4/browser-bandwidth-v4-raw-review.json'))
assert review['BW_RUN']==str(RAW) and review['status']=='raw_collection_accepted'
for r in review['evidence']+[review['environment']]:
    assert hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256']
rows=[];sources=[];checks=0
for run in read(RAW/'schedule.json')['runs']:
    path=RAW/'raw'/run['run_id']/'slots.jsonl'
    slots=[json.loads(l) for l in path.read_text().splitlines()]
    assert len(slots)==1200
    p=np.array([s['t_plan_ms'] for s in slots])
    send=np.array([s['t_send_ms'] if s['t_send_ms'] is not None else np.nan for s in slots])
    echo=np.array([s['first_correct_echo_ms'] if s['first_correct_echo_ms'] is not None else np.nan for s in slots])
    assert np.all(np.diff(p)==PERIOD_MS)
    sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    base={k:float(v[0]) for k,v in metric_arrays(p,send[None,:],echo[None,:]).items()}
    anchors=np.sort(np.concatenate((p,p+PERIOD_MS/2)))
    for model in ('receive_service','planned_slot_suppression'):
        for duration in DURATIONS_MS:
            results={k:[] for k in base};affected=[]
            for offset in range(0,len(anchors),BATCH):
                starts=anchors[offset:offset+BATCH,None];end=starts+duration
                changed_echo=np.broadcast_to(echo,(len(starts),len(echo))).copy()
                changed_send=np.broadcast_to(send,changed_echo.shape).copy()
                mask=(changed_echo>=starts)&(changed_echo<end) if model=='receive_service' else (p>=starts)&(p<end)
                if model=='receive_service':changed_echo=np.where(mask,end,changed_echo)
                else:
                    changed_echo[mask]=np.nan;changed_send[mask]=np.nan
                actual=metric_arrays(p,changed_send,changed_echo)
                affected.extend(np.count_nonzero(mask,axis=1).tolist())
                for key,v in actual.items():results[key].extend(v.tolist())
            delta={k:dict(min=float(min(v)-base[k]),max=float(max(v)-base[k]),max_abs=float(max(abs(np.array(v)-base[k])))) for k,v in results.items()}
            for idx in (0,1,len(anchors)//2,len(anchors)-1,int(np.argmin(results['S_pct'])),int(np.argmax(np.abs(np.array(results['Q_ms'])-base['Q_ms'])))):
                expected=scalar_check(slots,model,float(anchors[idx]),duration)
                assert all(math.isclose(expected[k],results[k][idx],rel_tol=1e-12,abs_tol=1e-10) for k in base),(model,idx,expected)
                checks+=1
            worst=int(np.argmin(results['S_pct']))
            rows.append(dict(mode=run['mode'],model=model,duration_ms=duration,phases=len(anchors),baseline=base,delta=delta,max_affected=int(max(affected)),fullness_bound_pp=100*max(affected)/len(slots),worst_S_phase_ms=float(anchors[worst]-p[0])))
result=dict(status='synthetic_sensitivity_only_not_admission',raw_inputs=str(RAW),sources=sources,scenarios=rows,official_metric_crosschecks=checks,
            design=dict(durations_ms=list(DURATIONS_MS),events_per_scenario=1,period_ms=PERIOD_MS,phases='planned and midperiod starts',deadline_ms=100,horizon_ms=5000),
            elapsed_s=time.monotonic()-started,limitations=['Finitephasefamily notglobalworstcase','Separatemodels notfullTCPQUICreplay','Baselineonly;delayed/lossyprofilesmayreactdifferently','Nonewallowancechosen;noreal69mslagguarantee','Norealdataexcluded;historicalstatusesunchanged'])
with (BASE/'analysis.json').open('x') as f:
    json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print('elapsed',result['elapsed_s'],'officialchecks',checks)
for model in ('receive_service','planned_slot_suppression'):
    for duration in DURATIONS_MS:
        selected=[r for r in rows if r['model']==model and r['duration_ms']==duration]
        print(model,duration,'maxabsQ',max(r['delta']['Q_ms']['max_abs'] for r in selected),'maxabsSpp',max(r['delta']['S_pct']['max_abs'] for r in selected),'maxabsUpp',max(r['delta']['U_pct']['max_abs'] for r in selected),'maxaffected',max(r['max_affected'] for r in selected))
