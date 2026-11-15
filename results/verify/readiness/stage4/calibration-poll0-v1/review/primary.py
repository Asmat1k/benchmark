import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
sys.path[:0]=['docker','src/analysis']
from admission import checked,ref,release,sources
from calibration_report import collection_plan,directions,rate
from calibration_blocks import process_diagnostics
from acceptance import dependence,exact_binomial
from sender_quality import evaluate

run=Path('results/verify/diagnostic/calibration.gIdWLx7o');base=Path('results/verify/readiness/stage4/calibration-poll0-v1/review');execution=base.parent/'execution.et3hz8uc'
seal=json.loads((run/'captured.json').read_text())
for r in seal:checked(r)
assert {r['path'] for r in seal}=={str(p) for p in run.rglob('*') if p.is_file() and p.name not in ('captured.json','exit','ended')}
assert (run/'exit').read_text().strip()==(execution/'exit').read_text().strip()=='0'
assert (execution/'identity-before.json').read_bytes()==(execution/'identity-after.json').read_bytes()
for p,s in json.loads((execution/'identity-after.json').read_text())['files'].items():checked(dict(path=p.removeprefix('/Users/dobrov/Desktop/Code/ITMO/benchmark/'),sha256=s))
plan=json.loads((run/'collection-plan.json').read_text());assert plan==collection_plan()==json.loads(Path('results/verify/readiness/stage4/release-v4/calibration-fixed-plan.json').read_text())
assert {p.name for p in run.iterdir() if p.is_dir()}=={r['name'] for r in plan['collections']}
original=json.loads(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json').read_text())
assert json.loads((run/'context-before.json').read_text())==json.loads((run/'context-after.json').read_text())==original
assert sources()==json.loads((run/'sources-before.json').read_text())==json.loads((run/'sources-after.json').read_text())==json.loads(Path('results/verify/readiness/stage4/deep-review-v1/source-inventory-new.json').read_text())
assert release()==(run/'commit').read_text().strip()=='d4cf0f82f330af1cd188febfa5f3757a5cf37799'
rows=[]
for i,item in enumerate(plan['collections'][:14]):
 d=run/item['name'];probe=json.loads((d/'probe.json').read_text());assert probe['sent']==10000 and probe['frame_bytes']==256 and probe['frequency_hz']==100
 quality=evaluate(probe['sent_records'],10000)
 replies=probe['reply_records'];assert len(replies)==len({r['id'] for r in replies}) and all(math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in replies)
 assert probe['rtt_ms']==[r['rtt_ms'] for r in replies]
 flows=directions(d,probe);captures={}
 for role in ('browser','server'):
  log=(d/f'{role}.log').read_text();assert '0 packets dropped by kernel' in log;captures[role]=dict(kernel_drops=0,log=log)
 queues={}
 for dev,seed in [('to_server',item['forward_seed']),('to_browser',item['reverse_seed'])]:
  first,last=[next(q for q in json.loads((d/f'qdisc-{when}.json').read_text()) if q['kind']=='netem' and q['dev']==dev) for when in ('before','after')]
  assert first['handle']==last['handle'] and first['options']==last['options'] and first['options']['seed']==seed
  assert first['options']['rate']['rate']==1250000 and first['options']['limit']==1000
  assert first['backlog']==first['qlen']==last['backlog']==last['qlen']==0
  queues[dev]=dict(options=first['options'],delta={k:last[k]-first[k] for k in ('bytes','packets','drops')})
 rtts=np.asarray(probe['rtt_ms']);values=np.full(10000,np.nan)
 for reply in replies:values[reply['id']]=reply['rtt_ms']
 loss=[]
 for flow in flows:
  count,drops=len(flow['entered_ids']),len(flow['dropped_ids']);interval=exact_binomial(drops,count,1-.01/8)
  loss.append(dict(direction=flow['direction'],entered=count,drops=drops,interval=interval,nominal_in_interval=interval[0]<=.01<=interval[1] if 'p1-' in item['name'] else drops==0))
 latency=np.quantile(rtts,[.05,.25,.5,.75,.95,.99]).tolist()
 failures=sorted(probe['sent_records'],key=lambda s:s['t_send_ms']-s['t_plan_ms'],reverse=True)[:3]
 row=dict(name=item['name'],quality=quality,replies=len(replies),loss=loss,captures=captures,qdisc=queues,quantiles=dict(zip(['p5','p25','median','p75','p95','p99'],latency)),dependence=dependence(probe['rtt_ms']),largest_lag_records=failures)
 row['process_diagnostics']=process_diagnostics(values)
 row['formal_process_series']=item['name'].endswith('-latency') or item['name'].startswith('baseline-')
 rows.append(row)
saturation=[]
for item in plan['collections'][14:]:
 name=item['name'];_,loss,direction=name.split('-');d=run/name;sample=rate(d,direction,int(loss)/100)
 stable=json.loads((d/'qdisc-stable.json').read_text());assert all(q['backlog']==q['qlen']==0 for q in stable if q['kind']=='netem')
 assert sample['offered_bytes']>=sample['forwarded_bytes']>0
 sample.update(name=name,mbit_s=sample['forwarded_bytes']*8/sample['duration_s']/1e6)
 saturation.append(sample)
failed=[r['name'] for r in rows if r['quality']['status']!='passed']
flagged=[r['name'] for r in rows if r['formal_process_series'] and r['process_diagnostics']['suspect']]
loss_failed=[r['name'] for r in rows if r['name'].endswith(('-before','-after')) and not all(l['nominal_in_interval'] for l in r['loss'])]
capacity_failed=[r['name'] for r in saturation if not 9<=r['mbit_s']<=11]
result=dict(status='failed' if failed or loss_failed or capacity_failed else 'inconclusive' if flagged else 'primary_checks_clear_pending_inference',reason='Full fixed post-poll0 primary review; no bootstrap or automatic process assumption approval',flagged_formal_process_series=flagged,loss_check_failures=loss_failed,capacity_failures=capacity_failed,reviewer='Codex; full primary integrity/network/timing review, no independent reviewer claimed',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),CAL_RUN=str(run),execution=str(execution),sealed_files_verified=len(seal),source_count=len(sources()),source_ENV_release_plan_unchanged=True,failed_sender_subseries=failed,echo=rows,saturation=saturation,evidence=[ref(run/'captured.json'),ref(run/'collection-plan.json'),ref(run/'context-before.json'),ref(run/'context-after.json')],limitations=['No circular-block bootstrap executed; no official calibration report published yet','No retrospective CPU/scheduler trace; primary integrity and process checks do not identify physical causes','Pcap snaplen96 covers headers/ID/tag/accounting, not complete256byte wire payload; receiver validates all returned payload bytes','No mandatory macOS trace added; no raw/seal modification or repeat','process_diagnostics are rejection heuristics, not automatic assumption approval'])
p=base/'primary-review-v3.json'
with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(p)
for row in rows:print(row['name'],row['quality']['status'],'median',row['quantiles']['median'],'loss',[(l['direction'],l['entered'],l['drops'],l['nominal_in_interval']) for l in row['loss']], 'process',row.get('process_diagnostics',{}).get('suspect'))
for sample in saturation:print(sample['name'],sample['mbit_s'])
