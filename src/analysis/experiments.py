import argparse
import json
import subprocess
from pathlib import Path

from acceptance import calibration, equivalence, generator_gate, paired_schedule, timer_gate
from admission import GATES, admit, aggregate, checked, freeze, ref, sources, verify
from jsonschema import ValidationError

from metrics import run_metrics
from power import simulate
from raw import now, read, require, rows, validate_raw, write
from schedule import PROFILES, block_runs, make_schedule


def completed_series(directory, design, data):
    from analyze import validate_series, run_identity
    from collection import environment
    require(data['kind']=='synthetic' or not (directory/'SYNTHETIC.json').exists(), 'synthetic series cannot be official')
    admission=admit(directory,data['kind'],validate_completion=False)
    require(admission['environment']==data['environment'] and admission['source_hashes']==data['source_hashes'], 'official series provenance mismatch')
    require(read(checked(admission['environment']))==read(directory/'context.json'), 'official series context mismatch')
    environment(checked(admission['environment']),data['kind'])
    schedule,selected,audit=validate_series(directory,design)
    for run in selected:
        folder=directory/'raw'/run['run_id']
        manifest=run_identity(folder,run)
        require((data['kind']=='synthetic' or not (folder/'SYNTHETIC.json').exists()) and not manifest['dirty'] and
                manifest['commit']==admission['release_commit'], 'official raw release/provenance')
        require(read(folder/'context.json')==read(directory/'context.json'), 'official raw context')
    return schedule,selected,audit


def paired_data(directory, data):
    schedule,selected,audit=completed_series(directory,data['design'],data)
    pairs=[]
    attempts={b['attempt_id']:b for b in read(directory/'ledger.json')['attempts']}
    order=list(dict.fromkeys(r['attempt_id'] for r in selected))
    for block in [attempts[identity] for identity in order]:
        if block['status']!='complete': continue
        sides,projects=[],[]
        for run in [r for r in selected if r['attempt_id']==block['attempt_id']]:
            folder=directory/'raw'/run['run_id']
            projects.append((folder/'service-names.txt').read_text())
            metric,_=run_metrics(rows(folder/'slots.jsonl'),rows(folder/'events.jsonl'),rows(folder/'resources.jsonl'),100,5000)
            sides.append(dict(run_id=run['run_id'],mode=run['mode'],seeds=[run['forward_seed'],run['reverse_seed']],monitoring=run.get('monitoring')=='on',**metric))
        require(len(sides)==2 and projects[0]!=projects[1], 'fresh pair processes required')
        pairs.append(dict(attempt_id=block['attempt_id'],mode=block['modes'][0],profile=block['profile'],fresh_processes=True,independence_reviewed=False,sides=sides))
    return pairs,selected


def pilot_data(directory, data):
    schedule,selected,_=completed_series(directory,'comparison',data)
    require(schedule['series']=='pilot', 'official pilot required')
    values={p:[] for p in PROFILES}
    for block in schedule['blocks']:
        members=[r for r in selected if r['attempt_id']==block['attempt_id']]
        if not members: continue
        sides={}
        for run in members:
            folder=directory/'raw'/run['run_id']
            metric,_=run_metrics(rows(folder/'slots.jsonl'),rows(folder/'events.jsonl'),rows(folder/'resources.jsonl'),100,5000)
            sides[run['mode']]=metric['Q_ms']
        require(sides['WS'] is not None and sides['WT-S'] is not None, 'null pilot effect: report unavailable power')
        values[block['profile']].append(sides['WT-S']-sides['WS'])
    require(all(len(v)>=5 for v in values.values()), 'minimum pilot five blocks/profile')
    return values,selected


def execute(directory, executor=None):
    admit(directory)
    from series import queue
    require(not (directory/'STOP').exists(), 'series stopped')
    executor = executor or (lambda d,i: subprocess.run(['sh','docker/measure.sh',str(d),str(i)],check=True))
    while True:
        if (directory/'PENDING_REPLACEMENT').exists() or (directory/'replacement.json').exists():
            return 2
        admit(directory)
        schedule=read(directory/'schedule.json')
        remaining=queue(directory)
        if not remaining: return 0
        pending=[(i,r) for i,r in enumerate(schedule['runs']) if r['attempt_id']==remaining[0] and
                 not (directory/'raw'/r['run_id']).exists()]
        require(pending, 'planned attempt has no pending member')
        index,run=pending[0]
        try:
            executor(directory,index)
        except subprocess.CalledProcessError as error:
            if error.returncode==3 and (directory/'PENDING_REPLACEMENT').exists(): return 2
            (directory/'STOP').write_text('orchestration failure; inspect evidence before new version\n')
            raise
        except Exception:
            (directory/'STOP').write_text('orchestration failure; inspect evidence before new version\n')
            raise
        require((directory/'raw'/run['run_id']).exists(), 'executor did not publish raw')



def evaluate(action, data):
    evidence=[]
    if action in ('aa','monitoring'):
        require(data['design']==action, 'design mismatch')
        if data['kind']=='synthetic' and 'pairs' in data:
            return equivalence(data['pairs'],action,data['collection_id'],data.get('include_wt_d',False)),[]
        directory=checked(data['schedule']).parent
        pairs,selected=paired_data(directory,data)
        require(data['independence_reviewed'], 'independent units review required')
        for pair in pairs: pair['independence_reviewed']=True
        result=equivalence(pairs,action,directory.name,data.get('include_wt_d',False))
        evidence.extend(directory/'raw'/r['run_id']/'SHA256SUMS' for r in selected)
    elif action in ('pilot','power'):
        directory=checked(data['schedule']).parent
        values,selected=pilot_data(directory,data)
        evidence.extend(directory/'raw'/r['run_id']/'SHA256SUMS' for r in selected)
        result=simulate(values,directory.name) if action=='power' else dict(status='passed',effects=values,blocks={p:len(v) for p,v in values.items()})
        result['coverage']=sorted({r['mode'] for r in selected})
    else:
        result=calibration(data) if action=='calibrate' else generator_gate(data['runs']) if action=='generator' else dict(status='passed' if timer_gate(data) else 'failed',timer=data)
    return result,evidence


def report(gate, result, evidence, kind, environment):
    require(kind in ('synthetic','real'), 'evidence kind')
    from admission import evidence_closure
    return dict(integrity=evidence_closure(evidence+[environment]),kind=kind,gate=gate,status=result['status'],result=result,reason=None,
                utc=now(),source_hashes=sources(),environment=ref(environment),evidence=[ref(p) for p in evidence])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('calibrate','generator','timer','aa','monitoring','pilot','power','verify','freeze','prepare','execute','next','import-checks'))
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--environment',type=Path)
    parser.add_argument('--kind',choices=('synthetic','real'),default='synthetic')
    parser.add_argument('--phase',choices=('aa','monitoring','pilot','main'))
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--reproduction',type=Path)
    parser.add_argument('--final',action='store_true')
    parser.add_argument('--datagrams',action='store_true')
    parser.add_argument('--blocks',type=int,default=20)
    parser.add_argument('--execute-real-experiments',action='store_true')
    args=parser.parse_args()
    action=args.action
    if action=='next':
        from series import queue
        require(args.execute_real_experiments and args.kind=='real', 'explicit real execution required')
        admit(args.output)
        require(not (args.output/'STOP').exists(), 'series stopped')
        if (args.output/'PENDING_REPLACEMENT').exists() or (args.output/'replacement.json').exists(): return 2
        schedule=read(args.output/'schedule.json')
        remaining=queue(args.output)
        if not remaining:
            print('complete')
            return 0
        pending=[i for i,r in enumerate(schedule['runs']) if r['attempt_id']==remaining[0] and not (args.output/'raw'/r['run_id']).exists()]
        require(pending, 'planned attempt has no pending member')
        print(pending[0])
        return 0
    if action=='execute':
        require(args.execute_real_experiments and args.kind=='real', 'explicit real execution required')
        return execute(args.output)
    if action=='prepare':
        require(args.phase and args.environment and args.verify, 'phase/environment/verify required')
        require(not args.output.exists() or args.phase=='main' and set(p.name for p in args.output.iterdir())=={'schedule.json'}, 'immutable series directory exists')
        required=GATES if args.phase in ('pilot','main') else GATES[:8] if args.phase=='aa' else GATES[:9]
        verify(args.verify,args.environment,final=args.phase=='main',required=required)
        require(args.kind=='real', 'synthetic evidence cannot admit real series')
        if args.phase=='main':
            require(args.freeze and args.freeze.exists() and args.reproduction, 'main freeze and independent reproduction required')
            schedule=read(checked(read(args.freeze)['bindings']['schedule']))
            require(schedule['series_id']==args.output.name, 'frozen series identity')
        elif args.phase=='pilot':
            require(args.blocks>=5, 'pilot minimum five blocks')
            schedule=make_schedule('pilot',args.output.name,args.blocks,4,args.datagrams)
        else:
            schedule=paired_schedule(args.phase,args.output.name,args.datagrams,args.blocks)
        args.output.mkdir(parents=True,exist_ok=True)
        if not (args.output/'schedule.json').exists(): write(args.output/'schedule.json',schedule)
        write(args.output/'ledger.json',dict(schema_version=1,series_id=args.output.name,attempts=schedule['blocks']))
        original = checked(read(args.freeze)['bindings']['schedule']) if args.phase=='main' else args.output/'schedule-original.json'
        if args.phase!='main': write(original,schedule)
        write(args.output/'admission.json',dict(kind='real',phase=args.phase,schedule=ref(original),
            source_hashes=sources(),release_commit=__import__('admission').release(),environment=ref(args.environment),verify=ref(args.verify),
            **({'freeze':ref(args.freeze),'reproduction':ref(args.reproduction)} if args.freeze else {})))
        admit(args.output,initial=True)
        return 0
    require(not args.output.exists(), 'immutable output exists')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if action=='freeze':
        require(args.kind=='real', 'real freeze only')
        freeze(read(args.input),args.output)
        return 0
    if action=='verify':
        result,code=aggregate(read(args.input) if args.input else {},args.environment,args.final,args.kind)
        write(args.output,result)
        return code
    require(args.input and args.environment, 'input/environment required')
    data=read(args.input)
    require(data['kind']==args.kind and data['environment']==ref(args.environment) and data['source_hashes']==sources(), 'publication provenance mismatch')
    from collection import environment as validate_environment,measured
    validate_environment(args.environment,args.kind)
    if action in ('timer','generator','calibrate'): measured(data)
    if action=='import-checks':
        from collection import imported,environment
        environment(args.environment,args.kind)
        result=imported(data)
        code=0 if result['status']=='passed' else 1 if result['status']=='failed' else 2
        require(data['gate'] in ('build','tls','path','raw','analysis','reproduction'), 'unsupported imported gate')
        write(args.output,report(data['gate'],result,[args.input],args.kind,args.environment))
        return code
    evidence=[args.input]
    from admission import deep_validation
    with deep_validation():
        result,extra=evaluate(action,data)
    evidence.extend(extra)
    if args.kind=='real':
        require(data['kind']=='real' and data['source_hashes']==sources() and data['environment']==ref(args.environment), 'real input provenance required')
        require(data['evidence'], 'real collection evidence required')
        evidence.extend(checked(value) for value in data['evidence'])
    gate='calibration' if action=='calibrate' else action
    write(args.output,report(gate,result,evidence,args.kind,args.environment))
    return 0 if result['status']=='passed' else 1 if result['status']=='failed' else 2


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (ValueError,KeyError,OSError,AssertionError,ValidationError) as error:
        print(str(error))
        raise SystemExit(2)
