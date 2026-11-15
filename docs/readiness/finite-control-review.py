import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/analysis'))
from admission import checked, ref, sources
from metrics import run_metrics
from raw import now, read, require, rows, validate_hashes, validate_raw
from resources import validate_resources
from series import context_snapshot
from stabilization_cpu import compare, quiet_summary
from schedule import MODES, PROFILES


def percentile(values,fraction):
    return sorted(values)[math.ceil(len(values)*fraction)-1] if values else None


def rtt_partition(slots,rtts,planned):
    returned=len(rtts)
    cutoff=percentile(rtts,.99)
    completed=[slot for slot in slots if slot['first_correct_echo_ms'] is not None and
               slot['first_correct_echo_ms']<=slot['t_plan_ms']+5000]
    values=[slot['first_correct_echo_ms']-slot['t_send_ms'] for slot in completed]
    require(values==rtts,'descriptive RTT sample differs from run_metrics')
    parts=dict(all=rtts,body=[value for value in rtts if value<=cutoff],
               tail=[value for value in rtts if value>cutoff]) if returned else dict(all=[],body=[],tail=[])
    statistics={}
    for name,values in parts.items():
        statistics[name]=dict(n=len(values),denominator_returned=returned,denominator_planned=planned,
            pct_returned=100*len(values)/returned if returned else None,pct_planned=100*len(values)/planned,
            median_ms=median(values) if values else None,mean_ms=sum(values)/len(values) if values else None,
            p95_ms=percentile(values,.95),p99_ms=percentile(values,.99),max_ms=max(values,default=None))
    tail=[dict(run_id=slot['run_id'],nonce=slot['nonce'],seq=slot['seq'],phase=slot['phase'],
               rtt_ms=slot['first_correct_echo_ms']-slot['t_send_ms'],send_lag_ms=slot['send_lag_ms'])
          for slot in completed if slot['first_correct_echo_ms']-slot['t_send_ms']>cutoff] if returned else []
    return dict(method='within-run nearest-rank p99; body <= cutoff; tail > cutoff; ties stay in body',
                cutoff_ms=cutoff,statistics=statistics,tail_identities=tail,
                unknown_rtt_planned=planned-returned,unknown_rtt_pct_planned=100*(planned-returned)/planned,
                limitation='Descriptive only. No trimming, lag subtraction, imputation, new threshold, or causal attribution.')


def outcome_counts(items,key):
    observed=[item.get('conditions',{}).get(key) for item in items]
    violated=sum(value is False for value in observed)
    unknown=sum(value is None for value in observed)
    return dict(n_planned=len(items),i_violated=violated,n_minus_i=len(items)-violated,
                known_satisfied=sum(value is True for value in observed),unknown=unknown,
                n_minus_i_includes_unknown=bool(unknown))


def run_review(directory,run,admission):
    folder=directory/'raw'/run['run_id']
    item=dict(run_id=run['run_id'],mode=run['mode'],profile=run['profile'],status='not-run',
              conditions=dict(technical_completeness=None,cpu_recovery_observed=None,
                              browser_20hz_lag_reference=None,useful_gain_completeness_reference=None))
    published=folder.exists()
    if not published:
        candidates=[p for p in (directory/'quarantine').glob('*') if (p/'run.json').is_file() and
                    read(p/'run.json')['run_id']==run['run_id']]
        if not candidates:
            return item
        require(len(candidates)==1,'ambiguous quarantined run')
        folder=candidates[0]
    item.update(status='technical-unknown',location='published' if published else 'quarantine',raw=str(folder))
    item['conditions']['technical_completeness']=False
    try:
        raw_error=None
        try:
            validate_raw(folder,directory/'schedule.json')
        except Exception as error:
            raw_error=str(error)
        if published:
            require(raw_error is None,'published raw validation: '+str(raw_error))
        else:
            require(raw_error=='queues not empty','quarantine supplement requires the observed queue-only stop')
            validate_hashes(folder)
            validate_resources(rows(folder/'resources.jsonl'),read(folder/'resource-window.json'))
            require(context_snapshot(folder)==read(folder/'context.json'),'quarantine actual context mismatch')
            summary=[]
            state=read(folder/'stabilization.json')
            for prefix in ('baseline',f"stabilization-{state['attempts']}"):
                records=[record for role in ('browser','server','router') for record in rows(folder/f'{prefix}-{role}.jsonl')]
                computed=quiet_summary(records,int((folder/f'{prefix}-marker').read_text()))
                require(computed==read(folder/f'{prefix}-cpu.json'),'quarantine CPU primary mismatch')
                summary.append(computed)
            comparison=compare(*summary)
            require(comparison==read(folder/f"stabilization-{state['attempts']}-comparison.json") and
                    state['cpu_recovered'] is (comparison['status']=='passed'),'quarantine CPU comparison mismatch')
            item['supplement_scope']='Descriptive sealed quarantine only; resource/CPU/context independently checked; queue admission remains failed.'
            item['raw_validation_error']=raw_error
        manifest=read(folder/'manifest.json')
        require(manifest['commit']==admission['release_commit'] and manifest['dirty'] is False,'raw release/dirty mismatch')
        require(read(folder/'context.json')==read(checked(admission['environment'])),'admitted actual context mismatch')
        slots=rows(folder/'slots.jsonl')
        completed=[s for s in slots if s['first_correct_echo_ms'] is not None and
                   s['first_correct_echo_ms']<=s['t_plan_ms']+5000]
        rtts=[s['first_correct_echo_ms']-s['t_send_ms'] for s in completed]
        timely=sum(s['first_correct_echo_ms']<=s['t_plan_ms']+100 for s in completed)
        metrics,canonical_rtts=run_metrics(slots,rows(folder/'events.jsonl'),rows(folder/'resources.jsonl'),100,5000)
        stabilization=read(folder/'stabilization.json')
        lag=metrics['p99_lag_ms']
        conditions=dict(technical_completeness=published,cpu_recovery_observed=stabilization.get('cpu_recovered'),
                        browser_20hz_lag_reference=lag<=5 if lag is not None else None,
                        useful_gain_completeness_reference=metrics['U_pct']<=1 and metrics['disconnects']==0)
        item.update(status='sealed-validated' if published else 'quarantined-invariant-failed',seal=ref(folder/'SHA256SUMS'),
            project=(folder/'service-names.txt').read_text(),
            start=manifest['started_utc'],end=manifest['ended_utc'],slots=len(slots),
            states=dict(Counter(s['send_state'] for s in slots)),completed=len(completed),
            timely=timely,late=len(completed)-timely,missing=len(slots)-len(completed),
            Q_ms=percentile(rtts,.95),S_pct=100*timely/len(slots),U_pct=100*(len(slots)-len(completed))/len(slots),
            p99_lag_ms=percentile([s['send_lag_ms'] for s in slots if s['send_lag_ms'] is not None],.99),
            stabilization=stabilization,disconnects=metrics['disconnects'],conditions=conditions,
            late_after_horizon_events=metrics['late_after_horizon'],
            all_body_tail=rtt_partition(slots,canonical_rtts,len(slots)),
            monitoring=run.get('monitoring','on'),seeds=[run['forward_seed'],run['reverse_seed']])
    except Exception as error:
        item['error']=str(error)
    return item


parser=argparse.ArgumentParser()
parser.add_argument('series',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
schedule=read(args.series/'schedule.json')
admission=read(args.series/'admission.json')
require(admission['source_hashes']==sources(),'unit review source mismatch')
require(schedule['series']=='verify' and len(schedule['runs'])==24 and len(schedule['blocks'])==12,'fixed control smoke schedule')
require({(b['modes'][0],b['profile']) for b in schedule['blocks']}=={(m,p) for m in MODES for p in PROFILES},'12 mode/profile cells')
design=admission['phase']
require(design in ('aa','monitoring'),'control design')
run_items=[run_review(args.series,run,admission) for run in schedule['runs']]
by_id={r['run_id']:r for r in run_items}
pairs=[]
for block in schedule['blocks']:
    members=[by_id[r['run_id']] for r in schedule['runs'] if r['attempt_id']==block['attempt_id']]
    complete=len(members)==2 and all(r['status']=='sealed-validated' for r in members)
    pair=dict(attempt_id=block['attempt_id'],mode=block['modes'][0],profile=block['profile'],
              status='unknown',run_ids=[r['run_id'] for r in members])
    if complete:
        a,b=members
        pair.update(fresh_processes=a['project']!=b['project'],sequential=a['end']<=b['start'],
                    seeds_match=a['seeds']==b['seeds'],monitoring_order=[a['monitoring'],b['monitoring']],
                    Q_shift_ms=None if a['Q_ms'] is None or b['Q_ms'] is None else b['Q_ms']-a['Q_ms'],
                    S_shift_pp=b['S_pct']-a['S_pct'])
        seed_ok=pair['seeds_match'] if design=='monitoring' else not pair['seeds_match']
        monitoring_ok=set(pair['monitoring_order'])=={'on','off'} if design=='monitoring' else pair['monitoring_order']==['on','on']
        pair['status']='reviewed' if pair['fresh_processes'] and pair['sequential'] and seed_ok and monitoring_ok else 'invariant-failed'
    pair['conditions']={}
    for key in ('technical_completeness','cpu_recovery_observed','browser_20hz_lag_reference','useful_gain_completeness_reference'):
        values=[member.get('conditions',{}).get(key) for member in members]
        pair['conditions'][key]=False if any(value is False for value in values) else True if len(values)==2 and all(value is True for value in values) else None
    pairs.append(pair)
review=dict(utc=now(),reviewer='/root/integration',scope='internal-source-process-order-review-no-empirical-independence-claim',
    design=design,schedule=ref(args.series/'schedule.json'),admission=ref(args.series/'admission.json'),
    environment=admission['environment'],source_hashes=sources(),planned_runs=24,retained_runs=len(run_items),
    sealed_validated=sum(r['status']=='sealed-validated' for r in run_items),
    reviewed_pairs=sum(p['status']=='reviewed' for p in pairs),
    run_status_counts=dict(Counter(r['status'] for r in run_items)),
    collection_status='complete' if all(r['status']=='sealed-validated' for r in run_items) else 'failed-incomplete',
    empirical_equivalence='not-established',
    status='reviewed-with-statistical-limitations' if all(p['status']=='reviewed' for p in pairs) else 'technical-unknown-or-invariant-failed',
    limitations=['n1 per cell cannot establish equivalence, empirical independence, or drift distribution.',
                 'All planned outcomes retained; scientific performance does not control membership.',
                 'Q conditions on returned echoes; missing remains in S/U denominators.'],runs=run_items,pairs=pairs)
condition_definitions=dict(
    technical_completeness='All mandatory raw/schema/seal/source/ENV/resource assertions; required integrity, no outcome selection.',
    cpu_recovery_observed='Actual retained cpu_recovered bool; false remains a known observation, not a technical rejection.',
    browser_20hz_lag_reference='Existing diagnostic browser 20 Hz p99 send lag <=5 ms reference ONLY; not a new AA admission gate.',
    useful_gain_completeness_reference='Existing useful-gain U<=1% and disconnects=0 reference; not equivalence and not a membership filter.')
review['condition_accounting']=dict(definitions=condition_definitions,
    run_units={key:outcome_counts(run_items,key) for key in condition_definitions},
    pair_units={key:outcome_counts(pairs,key) for key in condition_definitions},
    interpretation='Each condition counted separately. All planned runs/pairs remain. n-minus-i includes unknown when present; known_satisfied and unknown are explicit.')
review['main_valid_totals']=dict(planned_all_runs=24*1200,known_published_planned=1200*sum(r['status']=='sealed-validated' for r in run_items),
    known_published_returned=sum(r.get('completed',0) for r in run_items if r['status']=='sealed-validated'),
    known_published_missing=sum(r.get('missing',0) for r in run_items if r['status']=='sealed-validated'),
    technical_unknown_planned=1200*sum(r['status']!='sealed-validated' for r in run_items))
review['outcome_accounting']=dict(published_valid=sum(r['status']=='sealed-validated' for r in run_items),
    quarantined_rejected=sum(r['status']=='quarantined-invariant-failed' for r in run_items),
    not_started=sum(r['status']=='not-run' for r in run_items),
    published_metrics_unknown_runs=sum(r['status']!='sealed-validated' for r in run_items))
review['all_body_tail_totals']=dict(planned=sum(r.get('slots',1200) for r in run_items),
    returned=sum(r.get('completed',0) for r in run_items),
    body=sum(r.get('all_body_tail',{}).get('statistics',{}).get('body',{}).get('n',0) for r in run_items),
    tail=sum(r.get('all_body_tail',{}).get('statistics',{}).get('tail',{}).get('n',0) for r in run_items),
    missing_within_horizon=sum(r.get('missing',0) for r in run_items),
    technically_unknown_runs=sum(r['status']!='sealed-validated' for r in run_items),
    unavailable_rtt_planned_slots=1200*sum('completed' not in r for r in run_items),
    quarantined_descriptive_runs=sum(r['status']=='quarantined-invariant-failed' for r in run_items),
    note='Supplement combines available published and explicitly labelled quarantined descriptions; use main_valid_totals for officially valid data. Tail cutoffs are per run; no pooled cutoff or common-distribution estimate.')
args.output.mkdir(parents=True,exist_ok=False)
(args.output/'unit-review.json').write_text(json.dumps(review,indent=2,allow_nan=False)+'\n')
lines=['# Внутренний review контрольной серии','',
       f"{design}: {review['sealed_validated']}/24 published sealed raw; {review['reviewed_pairs']}/12 process/order/seed pairs. {review['collection_status']}; empirical equivalence not established.",
       f"Run status counts: {review['run_status_counts']}. Quarantined RTT summaries remain descriptive and do not change admission status.",
       f"Officially valid sample totals: {review['main_valid_totals']}. Quarantine is additional description, never a valid-run substitution.",'',
       '|Mode|Profile|Status|Q shift ms (side2−side1)|S shift pp|','|---|---|---|---|---|']
for p in pairs:
    lines.append('|'+ '|'.join(str(p.get(k)) for k in ('mode','profile','status','Q_shift_ms','S_shift_pp'))+'|')
lines+=['','Все 24 назначенных исхода:','',
        '|Run|Mode|Profile|Status|Slots|Completed|Missing|Error|','|---|---|---|---|---|---|---|---|']
for r in run_items:
    lines.append('|'+ '|'.join(str(r.get(k)) for k in ('run_id','mode','profile','status','slots','completed','missing','raw_validation_error'))+'|')
lines+=['','Отдельный учёт условий (каждое отдельно; ни один исход не исключён):','',
        '|Condition|Unit|n planned|n−i (includes unknown)|i violated|Known satisfied|Unknown|',
        '|---|---|---|---|---|---|---|']
for unit,accounting in (('run',review['condition_accounting']['run_units']),('pair',review['condition_accounting']['pair_units'])):
    for key,value in accounting.items():
        lines.append('|'+ '|'.join(str(v) for v in (key,unit,value['n_planned'],value['n_minus_i'],value['i_violated'],value['known_satisfied'],value['unknown']))+'|')
lines+=['','RTT all/body/tail (дополнительное описание; quarantine не становится официальным raw):','',
        '|Run|Published?|Returned / planned|Cutoff p99 ms|Body n|Tail n|Missing|Body median ms|Tail max ms|',
        '|---|---|---|---|---|---|---|---|---|']
for r in run_items:
    if 'all_body_tail' not in r:
        continue
    partition=r['all_body_tail'];stats=partition['statistics']
    values=(r['run_id'],r['status']=='sealed-validated',f"{r['completed']}/{r['slots']}",partition['cutoff_ms'],
            stats['body']['n'],stats['tail']['n'],r['missing'],stats['body']['median_ms'],stats['tail']['max_ms'])
    lines.append('|'+ '|'.join(str(value) for value in values)+'|')
lines+=['','20Hz p99 lag reference — diagnostic comparison, не новый gate AA; U/disconnect — useful-gain reference, не доказательство эквивалентности. CPU recovery false сохраняется как наблюдение.','',
        'All/body/tail описаны внутри каждого run по nearest-rank p99 RTT из run_metrics (body<=p99, tail>p99). Полные статистики, cutoff, ID хвоста и оба знаменателя находятся в unit-review.json. Missing RTT не относится ни к body, ни к tail.','',
        'Это source/process/order review внутренних исполнителей; научная эквивалентность при n1 не установлена. Все slots и технически неизвестные исходы сохранены, RTT не корректируется.']
(args.output/'unit-review.md').write_text('\n'.join(lines)+'\n')
print(args.output/'unit-review.json')
