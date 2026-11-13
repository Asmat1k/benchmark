import contextlib
import json
import hashlib
import ssl
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from raw import digest, now, read, require, write

_DEEP = 0
_APPROVED_GATES = {}
_CONTROLLER = None


@contextlib.contextmanager
def deep_validation():
    global _DEEP
    _DEEP += 1
    try: yield
    finally: _DEEP -= 1


@contextlib.contextmanager
def controller_session(directory, kind='real'):
    global _CONTROLLER
    require(_CONTROLLER is None, 'controller already active')
    _APPROVED_GATES.clear()
    with deep_validation():
        admit(directory,kind,initial=True)
    anchor=ref(directory/'admission.json')
    _CONTROLLER=(directory.resolve(),kind,anchor)
    try: yield
    finally: _CONTROLLER=None


GATES = ('build','tls','path','timer','raw','analysis','calibration','generator','aa','monitoring')
TRACKED = ('docs/protocol.md','configs/plan.json','configs/profiles.json','configs/thresholds.json',
           'docker/images.lock.json','src/client/package-lock.json','src/runner/package-lock.json',
           'src/server/go.sum','src/analysis/requirements.txt')


def ref(path):
    return dict(path=str(path),sha256=digest(path))


def checked(ref_value):
    path = Path(ref_value['path'])
    require(path.is_file() and digest(path) == ref_value['sha256'], 'evidence hash mismatch: '+str(path))
    return path


def sources():
    paths = list(TRACKED)
    for root in ('src','docker','docs/schemas'):
        paths.extend(str(p) for p in Path(root).rglob('*') if p.is_file() and
                     'node_modules' not in p.parts and '__pycache__' not in p.parts and 'dist' not in p.parts)
    paths.extend(['Makefile','compose.yaml'])
    return {p:digest(Path(p)) for p in sorted(set(paths))}


def validate_checks(document):
    Draft202012Validator(read(Path('docs/schemas/checks.schema.json')),format_checker=FormatChecker()).validate(document)
    ids = [r['id'] for r in document['checks']]
    require(len(set(ids)) == len(ids), 'duplicate check ID')
    for row in document['checks']:
        for evidence in row['evidence']: checked(evidence)
    mandatory = [r for r in document['checks'] if r['mandatory']]
    return 1 if any(r['status']=='failed' for r in mandatory) else 2 if not mandatory or any(r['status']!='passed' for r in mandatory) else 0




def evidence_closure(paths):
    files,trees={},{}
    pending=[Path(p).resolve() for p in paths]
    while pending:
        path=pending.pop()
        if str(path) in files: continue
        files[str(path)]=digest(path)
        if path.suffix!='.json': continue
        value=read(path)
        def visit(value):
            if isinstance(value,dict):
                if set(value)=={'path','sha256'}:
                    target=Path(value['path'])
                    if not target.is_absolute() and not target.exists(): target=path.parent/target
                    require(target.exists() and digest(target)==value['sha256'], 'closure evidence hash')
                    pending.append(target.resolve())
                    if target.name=='schedule.json' and read(target).get('series')!='main':
                        directory=target.parent.resolve()
                        members=sorted(p.resolve() for p in directory.rglob('*') if p.is_file() and 'derived' not in p.relative_to(directory).parts)
                        trees[str(directory)]=[str(p) for p in members]
                        pending.extend(members)
                else:
                    for key,item in value.items():
                        if key not in ('integrity','result','source_hashes'): visit(item)
            elif isinstance(value,list):
                for item in value: visit(item)
        visit(value)
    return dict(files=files,trees=trees)


def check_integrity(receipt):
    require(receipt['files'], 'missing integrity receipt')
    for path,sha in receipt['files'].items():
        require(Path(path).is_file() and digest(Path(path))==sha, 'immutable evidence changed: '+path)
    for directory,members in receipt['trees'].items():
        root=Path(directory)
        require(sorted(str(p.resolve()) for p in root.rglob('*') if p.is_file() and 'derived' not in p.relative_to(root).parts)==members, 'immutable evidence inventory changed')


def validate_gate(report, recalculate=True):
    from collection import environment, imported, measured
    gate=report['gate']
    data=read(checked(report['evidence'][0]))
    require(data['kind']==report['kind'] and data['gate']==gate and data['source_hashes']==report['source_hashes'] and data['environment']==report['environment'], 'input provenance mismatch')
    environment(checked(report['environment']),report['kind'])
    key=hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if key in _APPROVED_GATES:
        require(report['integrity']==_APPROVED_GATES[key], 'approved graph changed')
        check_integrity(_APPROVED_GATES[key])
        require(report['result']['status']==report['status'], 'gate result/status')
        return
    require(recalculate, 'deep-issued gate approval required')
    canonical=evidence_closure([checked(item) for item in report['evidence']]+[checked(report['environment'])])
    require(report['integrity']==canonical, 'noncanonical evidence graph')
    if gate in ('build','tls','path','raw','analysis','reproduction'):
        result=imported(data)
    else:
        from experiments import evaluate
        if gate in ('timer','generator','calibration'): measured(data)
        with deep_validation():
            result,_=evaluate('calibrate' if gate=='calibration' else gate,data)
    require(report['result']==json.loads(json.dumps(result,allow_nan=False)) and report['status']==result['status'], 'gate calculation/status mismatch')
    _APPROVED_GATES[key]=canonical


def aggregate(reports, environment, final=False, kind="real"):
    from collection import environment as validate_environment
    validate_environment(environment,kind)
    checks = []
    for gate in GATES:
        if gate not in reports:
            checks.append(dict(id=gate,mandatory=True,expected='passed real evidence',actual=None,units='gate',
                               tolerance=None,status='not_run',reason='gate_report_not_provided',utc=now(),evidence=[]))
            continue
        path = Path(reports[gate])
        report = read(path)
        require(report['kind']==kind and report['gate']==gate and report['source_hashes']==sources() and
                report['environment']==ref(environment), 'synthetic/stale/wrong environment gate evidence')
        require(report['status'] in ('passed','failed','inconclusive','not_run'), 'invalid gate status')
        require(report['evidence'], 'missing gate evidence')
        for evidence in report['evidence']: checked(evidence)
        validate_gate(report)
        checks.append(dict(id=gate,mandatory=True,expected='passed real evidence',actual=report['result'] if report['status']!='not_run' else None,
                           units='gate',tolerance=None,status=report['status'],reason=report.get('reason'),utc=now(),
                           evidence=[ref(path)]))
    result = dict(schema_version=1,checks=checks)
    return dict(kind=kind,final=final,source_hashes=sources(),environment=ref(environment),document=result), validate_checks(result)


def verify(path, environment, final=False, required=GATES, kind="real", recalculate=True):
    from collection import environment as validate_environment
    validate_environment(environment,kind)
    report = read(path)
    require(report['kind']==kind and (not final or report['final']), 'real final verify required')
    require(report['source_hashes']==sources() and report['environment']==ref(environment), 'verify environment/source mismatch')
    document = report['document']
    require({r['id'] for r in document['checks']} == set(GATES) and all(r['mandatory'] for r in document['checks']), 'missing mandatory gates')
    require(all(r['status']=='passed' for r in document['checks'] if r['id'] in required), 'mandatory verify not passed')
    validate_checks(document)
    for row in document['checks']:
        if row['id'] not in required: continue
        require(len(row['evidence'])==1, 'ambiguous gate report')
        evidence = read(checked(row['evidence'][0]))
        require(evidence['kind']==kind and evidence['gate']==row['id'] and evidence['status']=='passed' and
                evidence['source_hashes']==report['source_hashes'] and evidence['environment']==report['environment'], 'gate report mismatch')
        require(evidence['evidence'], 'empty underlying evidence')
        for item in evidence['evidence']: checked(item)
        validate_gate(evidence,recalculate)
    return report


def release():
    snapshot=read(Path('build/release-state.json'))
    current=sources()
    require(all(snapshot['files'].get(path)==sha for path,sha in current.items()), 'release source dirty or untracked')
    require({p for p in snapshot['files'] if p.startswith(('src/','docker/','docs/schemas/'))} <= set(current), 'release source deleted')
    require(len(snapshot['commit'])==40, 'invalid release commit')
    return snapshot['commit']


def leaf_covers(path, until, minimum_seconds=0, current_utc=None):
    certificate = ssl._ssl._test_decode_cert(str(path))
    current = (current_utc or datetime.now(timezone.utc)).timestamp()
    end = datetime.fromisoformat(until.replace('Z','+00:00')).timestamp()
    require(ssl.cert_time_to_seconds(certificate['notBefore']) <= current and current+minimum_seconds <= end <=
            ssl.cert_time_to_seconds(certificate['notAfter']), 'leaf does not cover planned series')
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(path.read_text())).hexdigest()



def coverage(verification, modes):
    from schedule import PROFILES
    for gate in ('aa','monitoring'):
        row=next(r for r in verification['document']['checks'] if r['id']==gate)
        report=read(checked(row['evidence'][0]))
        require({(g['mode'],g['profile']) for g in report['result']['groups']}=={(m,p) for m in modes for p in PROFILES}, 'mode/profile gate coverage')



def inventory(binding, category):
    actual=read(checked(binding))
    expected={p:sha for p,sha in sources().items() if p.startswith('src/analysis/')} if category=='analysis' else {p:sources()[p] for p in (*TRACKED[4:],'src/server/go.mod','docker/os-packages.txt')}
    require(actual==dict(files=expected), 'wrong '+category+' inventory')


def experiment_reports(bindings, modes, environment, kind='real', recalculate=True):
    reports={}
    for key in ('pilot','power'):
        report=read(checked(bindings[key]))
        require(report['gate']==key and report['kind']==kind and report['status']=='passed' and report['source_hashes']==sources() and report['environment']==environment, key+' report required')
        for evidence in report['evidence']: checked(evidence)
        validate_gate(report,recalculate)
        require(set(report['result']['coverage'])==modes, 'pilot/power mode coverage')
        reports[key]=report
    require(read(checked(reports['pilot']['evidence'][0]))['schedule']==read(checked(reports['power']['evidence'][0]))['schedule'], 'mixed pilot and power series')
    return reports


def separate_frozen_schedule(original,directory):
    current=directory/'schedule.json'
    require(original.resolve()!=current.resolve() and not (current.exists() and original.samefile(current)),
            'freeze must bind a separate immutable schedule')


def validate_freeze(value, remaining=None, recalculate=True):
    schema=read(Path('docs/schemas/freeze.schema.json'))
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(value)
    require(value['kind']=='real', 'synthetic freeze forbidden')
    environment=checked(value['bindings']['environment'])
    verify(checked(value['bindings']['verify']),environment,final=True,recalculate=recalculate)
    for binding in value['bindings'].values(): checked(binding)
    require(value['source_hashes']==sources(), 'freeze source inventory')
    require(value['release_commit']==release() and value['dirty'] is False, 'release mismatch')
    require(value['blocks_per_profile'] in (20,30,40,60), 'fixed main sample size required')
    require(value['repeat_effect_ms'] >= 2 and value['repeat_fullness_pp'] >= 1, 'repeat tolerance floors')
    schedule_path=checked(value['bindings']['schedule'])
    schedule=read(schedule_path)
    separate_frozen_schedule(schedule_path,Path('results/main')/schedule['series_id'])
    minimum_runs=len(schedule['runs']) if remaining is None else remaining
    leaf_hash=leaf_covers(Path(value['leaf_pem']),value['series_end_utc'],minimum_runs*80)
    require(digest(checked(value['bindings']['leaf_der']))==leaf_hash, 'leaf DER binding mismatch')
    require(read(Path('configs/thresholds.json'))['preliminary'] is False, 'final thresholds required')
    canonical={'protocol':'docs/protocol.md','plan':'configs/plan.json','profiles':'configs/profiles.json','thresholds':'configs/thresholds.json'}
    require(all(value['bindings'][key]==ref(Path(path)) for key,path in canonical.items()), 'canonical config/protocol bindings')
    schedule=read(checked(value['bindings']['schedule']))
    from schedule import block_runs, PROFILES
    require(schedule['series']=='main' and all(b['design']=='comparison' for b in schedule['blocks']), 'main comparison schedule required')
    require(schedule['runs']==[r for i,b in enumerate(schedule['blocks']) for r in block_runs(schedule,b,i)], 'main schedule derivation')
    modes={'WS','WT-S','WT-D'} if value['include_wt_d'] else {'WS','WT-S'}
    require(all(set(b['modes'])==modes and len(b['modes'])==len(modes) for b in schedule['blocks']), 'WT-D frozen decision mismatch')
    require(set(b['profile'] for b in schedule['blocks'])==set(PROFILES) and all(sum(b['profile']==p for b in schedule['blocks'])==value['blocks_per_profile'] for p in PROFILES), 'frozen main block counts')
    experiment_reports(value['bindings'],modes,value['bindings']['environment'],recalculate=recalculate)
    inventory(value['bindings']['analysis'],'analysis')
    inventory(value['bindings']['locks'],'locks')
    require(value['rationale'] and value['aa_shift_algorithm']=='paired side2-side1; linear p95 absolute shifts', 'pre-main rationale required')
    aa_row=next(r for r in read(checked(value['bindings']['verify']))['document']['checks'] if r['id']=='aa')
    aa=read(checked(aa_row['evidence'][0]))
    verification=read(checked(value['bindings']['verify']))
    coverage(verification,modes)
    require(value['repeat_effect_ms']==aa['result']['repeat_effect_ms'] and value['repeat_fullness_pp']==aa['result']['repeat_fullness_pp'], 'AA repeat tolerances mismatch')
    return value


def freeze(proposal, output):
    require(not output.exists(), 'immutable freeze exists')
    require(proposal['kind']=='real', 'synthetic freeze forbidden')
    value=dict(proposal,frozen_utc=now())
    validate_freeze(value)
    write(output,value)


def validate_schedule_extension(directory, original, current):
    from analyze import schedule_snapshot
    from violation import detect
    schedule_snapshot(original,current)
    from schedule import block_runs
    require(current['runs']==[r for i,b in enumerate(current['blocks']) for r in block_runs(current,b,i)], 'current run derivation')
    for block in current['blocks'][len(original['blocks']):]:
        parent = block['replacement_of']
        require(parent is not None and Path(parent).name==parent, 'unauthorized appended block')
        archive = directory/'audit'/parent
        transaction = read(archive/'transaction.json')
        proof = read(archive/'evidence.json')
        require(transaction['evidence_sha256']==digest(archive/'evidence.json') and transaction['replacement']==
                next(b for b in transaction['schedule']['blocks'] if b['attempt_id']==block['attempt_id']), 'replacement proof binding')
        require({k:v for k,v in block.items() if k not in ('status','reason')}==
                {k:v for k,v in transaction['replacement'].items() if k not in ('status','reason')}, 'replacement metadata')
        schedule_snapshot(read(archive/'schedule.json'),current)
        schedule_snapshot(transaction['schedule'],current)
        require(proof['attempt_id']==parent and Path(proof['run_id']).name==proof['run_id'], 'replacement identity')
        source=archive/proof['run_id']
        require(proof['files']=={p.name:digest(p) for p in source.iterdir()}, 'replacement source changed')
        require(detect(source,directory/'schedule.json')==(proof['reason'],proof['error']), 'replacement violation not reproducible')



def phase_path(directory, schedule):
    parts=directory.resolve().parts
    for phase in ('pilot','main'):
        require(not any(parts[i:i+2]==('results',phase) for i in range(len(parts)-1)) or schedule['series']==phase,
                'phase/path mismatch')


def execution_state(directory, original, current, validate_completion=True):
    import copy
    from schedule import replace_block
    ledger=read(directory/'ledger.json')
    Draft202012Validator(read(Path('docs/schemas/ledger.schema.json'))).validate(ledger)
    require(ledger['series_id']==current['series_id'] and len(ledger['attempts'])==len(current['blocks']), 'execution ledger identity')
    for attempt in ledger['attempts']:
        if attempt['status']=='quarantined':
            require(sum(b['replacement_of']==attempt['attempt_id'] for b in current['blocks'])==1 and (directory/'audit'/attempt['attempt_id']/'transaction.json').is_file(), 'quarantine requires replacement proof')
    for block,attempt in zip(current['blocks'],ledger['attempts']):
        require({k:v for k,v in block.items() if k!='status'}=={k:v for k,v in attempt.items() if k!='status'}, 'execution ledger metadata')
    order=[b['attempt_id'] for b in original['blocks']]
    for block in current['blocks'][len(original['blocks']):]:
        archive=directory/'audit'/block['replacement_of']
        transaction=read(archive/'transaction.json')
        prior=read(archive/'schedule.json')
        statuses={a['attempt_id']:a['status'] for a in transaction['ledger']['attempts']}
        remaining=[a for a in order if a!=block['replacement_of'] and statuses[a]=='planned']
        rebuilt=copy.deepcopy(prior)
        replacement=replace_block(rebuilt,block['replacement_of'],transaction['ledger']['attempts'][next(i for i,a in enumerate(transaction['ledger']['attempts']) if a['attempt_id']==block['replacement_of'])]['reason'],remaining)
        require(replacement==transaction['replacement'] and remaining==transaction['queue'], 'replacement queue derivation')
        completed=[a for a in order if statuses[a]=='complete']
        order=completed+remaining
    statuses={a['attempt_id']:a['status'] for a in ledger['attempts']}
    order=[a for a in order if statuses[a]!='quarantined']
    remaining=[a for a in order if statuses[a]=='planned']
    require(order==[a for a in order if statuses[a]=='complete']+remaining, 'execution ledger order')
    if (directory/'queue.json').exists():
        require(read(directory/'queue.json')==remaining, 'execution queue changed')
    published={p.name for p in (directory/'raw').iterdir()} if (directory/'raw').exists() else set()
    required={r['run_id'] for r in current['runs'] if statuses[r['attempt_id']]=='complete'}
    allowed=required|{r['run_id'] for r in current['runs'] if remaining and r['attempt_id']==remaining[0]}
    require(required<=published<=allowed, 'execution raw membership/completion')
    for run in current['runs']:
        if run['run_id'] not in published: continue
        folder=directory/'raw'/run['run_id']
        manifest=read(folder/'manifest.json')
        require(folder.name==manifest['run_id'] and all(manifest.get(k)==v for k,v in run.items()), 'published run attribution')
        from raw import validate_hashes
        inventory=validate_hashes(folder)
        require({'manifest.json','completion.json','slots.jsonl','events.jsonl','resources.jsonl','warmup.jsonl','config.json','context.json','schedule.json','server.json','checks.json','security.json','provenance.json','leaf.pem','resource-window.json'}<=set(inventory), 'published raw files incomplete')
        Draft202012Validator(read(Path('docs/schemas/manifest.schema.json'))).validate(manifest)
        with (folder/'slots.jsonl').open() as slots:
            slot_count=sum(1 for _ in slots)
        require(manifest['technical_valid'] and slot_count==1200, 'published slot completeness')
        completion=read(folder/'completion.json')
        require(completion['status']=='complete' and completion['run_id']==run['run_id'] and completion['measurement_rows']==1200, 'published run completeness')
    pending_runs=[r['run_id'] for r in current['runs'] if remaining and r['attempt_id']==remaining[0]]
    seen=[r for r in pending_runs if r in published]
    require(seen==pending_runs[:len(seen)], 'execution side order')
    if not remaining and validate_completion:
        from analyze import validate_series
        validate_series(directory,current['blocks'][0]['design'])
    return remaining



def accepted_schedule(original, phase):
    from schedule import PROFILES, make_schedule
    from acceptance import paired_schedule
    modes={m for b in original['blocks'] for m in b['modes']}
    datagrams='WT-D' in modes
    if phase in ('aa','monitoring'):
        count=sum(b['profile']==PROFILES[0] and b['modes'][0]=='WS' for b in original['blocks'])
        expected=paired_schedule(phase,original['series_id'],datagrams,count)
    else:
        count=sum(b['profile']==PROFILES[0] for b in original['blocks'])
        require(count>=5 if phase=='pilot' else count in (20,30,40,60), 'official planned block count')
        expected=make_schedule(phase,original['series_id'],count,4,datagrams)
    require(original==expected, 'original accepted schedule changed')


def admit(directory, kind=None, validate_completion=True, initial=False):
    kind=kind or (_CONTROLLER[1] if _CONTROLLER is not None and _CONTROLLER[0]==directory.resolve() else "real")
    trusted=_CONTROLLER is not None and _CONTROLLER[0]==directory.resolve() and _CONTROLLER[1]==kind
    require(trusted or initial or _DEEP>0, 'trusted controller admission or full initial validation required')
    if trusted: require(ref(directory/'admission.json')==_CONTROLLER[2], 'controller admission changed')
    recalculate=initial or _DEEP>0
    require((directory/'admission.json').is_file(), 'series requires admission')
    schedule = read(directory/'schedule.json')
    admission = read(directory/'admission.json')
    require(admission['kind']==kind and admission['source_hashes']==sources(), 'missing/stale series admission')
    if kind=='real' and initial:
        require(admission['release_commit']==release(), 'initial admission release commit mismatch')
    if kind=='real': require(not (directory/'SYNTHETIC.json').exists(), 'synthetic series cannot be real admission')
    if kind=='synthetic':
        require((directory/'SYNTHETIC.json').exists() and not directory.resolve().is_relative_to(Path('results').resolve()), 'synthetic admission isolated fixtures only')
    original = read(checked(admission['schedule']))
    validate_schedule_extension(directory,original,schedule)
    phase_path(directory,schedule)
    execution_state(directory,original,schedule,validate_completion)
    env = checked(admission['environment'])
    phase = admission['phase']
    require(phase in ('aa','monitoring','pilot','main'), 'unknown admitted phase')
    require(schedule['series'] == (phase if phase in ('pilot','main') else 'verify'), 'admitted phase mismatch')
    require(all(b['design']==('comparison' if phase in ('pilot','main') else phase) for b in schedule['blocks']), 'admitted design mismatch')
    if kind=='real': accepted_schedule(original,phase)
    required = GATES if phase in ('pilot','main') else GATES[:8] if phase == 'aa' else GATES[:9]
    verification=verify(checked(admission['verify']),env,final=phase=='main',required=required,kind=kind,recalculate=recalculate)
    modes=set(original['blocks'][0]['modes'])
    if phase in ('pilot','main'): coverage(verification,modes)
    if schedule['series']=='main':
        published={p.name for p in (directory/'raw').iterdir()} if (directory/'raw').exists() else set()
        active={a['attempt_id'] for a in read(directory/'ledger.json')['attempts'] if a['status']!='quarantined'}
        remaining=sum(r['attempt_id'] in active and r['run_id'] not in published for r in schedule['runs'])
        frozen = validate_freeze(read(checked(admission['freeze'])),remaining,recalculate=recalculate)
        require(frozen['kind']=='real' and frozen['release_commit']==release() and frozen['source_hashes']==sources(), 'frozen release mismatch')
        schema=read(Path('docs/schemas/freeze.schema.json'))
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(frozen)
        for value in frozen['bindings'].values(): checked(value)
        separate_frozen_schedule(checked(admission['schedule']),directory)
        require(frozen['bindings']['schedule']==admission['schedule'], 'frozen schedule mismatch')
        require(frozen['bindings']['verify']==admission['verify'] and frozen['bindings']['environment']==admission['environment'], 'freeze/verify mismatch')
        leaf_covers(Path(frozen['leaf_pem']),frozen['series_end_utc'])
        reproduction=read(checked(admission['reproduction']))
        require(reproduction['kind']=='real' and reproduction['gate']=='reproduction' and reproduction['status']=='passed' and reproduction['source_hashes']==sources() and reproduction['environment']==admission['environment'], 'independent reproduction required')
        require(reproduction['result'].get('freeze')==admission['freeze'], 'reproduction belongs to another freeze')
        validate_gate(reproduction,recalculate=recalculate)
    return admission
