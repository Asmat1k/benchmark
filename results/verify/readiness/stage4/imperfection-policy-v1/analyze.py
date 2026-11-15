import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0,'src/analysis')
from sender_quality import evaluate

RUNS=('calibration.lShojabe','calibration.gIdWLx7o','calibration.ew2u0ceD')
OUT=Path(sys.argv[1])

def nearest_rank(values,q):
    return values[math.ceil(q*len(values))-1] if values else None

def describe(records):
    values=sorted(r['rtt_ms'] for r in records)
    return dict(n=len(values),median_ms=statistics.median(values) if values else None,
                mean_ms=statistics.mean(values) if values else None,
                p95_ms=nearest_rank(values,.95),p99_ms=nearest_rank(values,.99),max_ms=max(values) if values else None)

started=time.monotonic();result=[]
for label in RUNS:
    run=Path('results/verify/diagnostic')/label
    seals=json.loads((run/'captured.json').read_text())
    assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in seals)
    rows=[]
    for item in json.loads((run/'collection-plan.json').read_text())['collections'][:14]:
        p=json.loads((run/item['name']/'probe.json').read_text())
        sent=p['sent_records'];replies=p['reply_records']
        quality=evaluate(sent,10000)
        assert len(replies)==len({r['id'] for r in replies})
        values=sorted(r['rtt_ms'] for r in replies)
        cutoff=nearest_rank(values,.99)
        upper=[r for r in replies if r['rtt_ms']>cutoff]
        body=[r for r in replies if r['rtt_ms']<=cutoff]
        assert len(body)+len(upper)==len(replies)
        lags={r['id']:r['t_send_ms']-r['t_plan_ms'] for r in sent}
        late={i for i,v in lags.items() if v>=10}
        tail_ids={r['id'] for r in upper};returned={r['id'] for r in replies}
        missing=set(range(10000))-returned
        joint=dict(late_and_tail=len(returned&late&tail_ids),tail_not_late=len(tail_ids-late),late_not_tail=len((returned&late)-tail_ids),neither=len(returned-late-tail_ids))
        assert sum(joint.values())==len(replies)
        rows.append(dict(name=item['name'],sent=10000,returned=len(replies),missing_count=len(missing),missing_ids=sorted(missing),
                         all_returns=describe(replies),at_or_below_p99=describe(body),above_p99=describe(upper),
                         tail_cutoff_ms=cutoff,tail_percent_returned=100*len(upper)/len(replies),tail_percent_planned=len(upper)/100,
                         above_existing_100ms_count=sum(r['rtt_ms']>100 for r in replies),
                         above_existing_100ms_percent_planned=sum(r['rtt_ms']>100 for r in replies)/100,
                         sender_quality=quality,sender_late_ids=sorted(late),sender_above_existing_50ms=[dict(id=i,lag_ms=v) for i,v in lags.items() if v>50],
                         joint_returned_counts=joint,missing_and_late_count=len(missing&late),
                         tail_records=[dict(id=r['id'],rtt_ms=r['rtt_ms'],sender_lag_ms=lags[r['id']]) for r in upper],
                         rank_sensitivity_1pct=dict(p94_ms=nearest_rank(values,.94),p95_ms=nearest_rank(values,.95),p96_ms=nearest_rank(values,.96))))
    result.append(dict(run=str(run),commit=(run/'commit').read_text().strip(),seals_verified=len(seals),series=rows))
document=dict(scope='Exploratory additive body/tail description of three historical full collections; not revised admission or deletion',
              cutoff_rule='Per collection nearest-rank p99 over all returned finite RTT; body<=p99, tail>p99; ties stay in body',
              primary_sample='All original returned RTT retained; loss/missing separately counted against all10000planned slots',
              status='descriptive_only_no_gate_change',runs=result,elapsed_s=time.monotonic()-started,
              utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              limitations=['Tail is a descriptive rank label, not proof of measurement error or Gaussian outlier',
                           'Body/tail statistics are conditional; they cannot replace full-sample median/p95 or calibrated uncertainty',
                           'A single sender delay can affect neighbouring packet RTT; same-ID joint counts do not bound causal contamination',
                           'Rank sensitivity is a hypothetical diagnostic, not a millisecond or confidence bound',
                           'Calibration UDP observations do not establish WS/WT comparative rank stability',
                           'Historical failed reports and raw remain unchanged; no new numeric allowances selected'])
with OUT.open('x') as f:json.dump(document,f,indent=2,allow_nan=False);f.write('\n')
print('output',OUT,'elapsed_s',document['elapsed_s'])
for r in result:
 print(r['run'])
 for row in r['series']:
  print(row['name'],'returned',row['returned'],'fullmedian',row['all_returns']['median_ms'],'p95',row['all_returns']['p95_ms'],'tailn',row['above_p99']['n'],'tailmax',row['above_p99']['max_ms'],'sender',row['sender_quality']['status'])
