from pathlib import Path

from admission.admission import GATES, check_integrity, checked, evidence_closure, ref, sources, validate_gate
from admission.browser_admission import ADMISSION_SOURCE_CHANGES, current_environment
from measurement.raw import digest, now, read, require

VERSION = 'finite-browser-study-v1'
_HISTORICAL_APPROVED = {}
SOURCE_CHANGES = ADMISSION_SOURCE_CHANGES | {'src/analysis/admission/acceptance.py', 'src/analysis/admission/admission.py',
    'src/analysis/execution/experiments.py', 'src/analysis/admission/limited_readiness.py', 'src/analysis/admission/test_limited_readiness.py',
    'configs/schemas/freeze.schema.json'}
DESIGN = dict(control_pairs_per_cell=1, pilot_blocks_per_profile=5, main_blocks_per_profile=20,
              modes=['WS','WT-S','WT-D'], profiles=['r20p0','r20p1','r80p0','r80p1'],
              repeat_effect_ms=2,repeat_fullness_pp=1, sample='fixed-all-planned-outcomes')


def policy(binding):
    value = read(checked(binding))
    require(value['readiness_version'] == VERSION and value['design'] == DESIGN, 'unsupported finite study design')
    require(value['protocol'] == ref(Path('configs/contracts/protocol.json')) and value['plan'] == ref(Path('configs/plan.json')),
            'finite study policy protocol/plan mismatch')
    checked(value['rationale'])
    require(read(Path('configs/plan.json')).get('execution_policy') == VERSION, 'finite execution policy required')
    return value


def historical_report(binding, context, recalculate=True):
    report = read(checked(binding['report']))
    old_sources, current = report['source_hashes'], sources()
    changed = {name for name in old_sources.keys() | current.keys() if old_sources.get(name) != current.get(name)}
    require(changed <= SOURCE_CHANGES, 'unexpected historical source change: '+str(sorted(changed-SOURCE_CHANGES)))
    old_context = read(checked(report['environment']))
    require(all(context[key] == old_context[key] for key in ('host','vm','leaf','services')), 'historical runtime environment changed')
    require(context['config']['profiles'] == old_context['config']['profiles'] and
            context['config']['thresholds'] == old_context['config']['thresholds'], 'historical measured parameters changed')
    old_plan, plan = old_context['config']['plan'], context['config']['plan']
    require({k:v for k,v in old_plan.items() if k != 'execution_policy'} ==
            {k:v for k,v in plan.items() if k != 'execution_policy'}, 'historical plan bridge changed measurement')
    old_bindings, bindings = old_context['bindings'], context['bindings']
    require({k:v for k,v in old_bindings.items() if k != 'configs/contracts/protocol.json'} ==
            {k:v for k,v in bindings.items() if k != 'configs/contracts/protocol.json'}, 'historical lock bindings changed')
    receipt = read(checked(binding['replay']))
    require(receipt['schema_version'] == 1 and receipt['validation'] == 'validate-gate-exact-source-v1' and
            receipt['report'] == binding['report'] and receipt['environment'] == report['environment'] and
            receipt['source_hashes'] == old_sources and receipt['historical_status'] == report['status'] and
            receipt['exit'] == 0, 'historical exact-source replay mismatch')
    require(receipt['started_utc'] <= receipt['ended_utc'], 'historical replay timestamps')
    checked(receipt['runner'])
    checked(receipt['stderr'])
    observed = read(checked(receipt['stdout']))
    require(observed == dict(validated_report=binding['report'],source_hashes=old_sources,
                             environment=report['environment'],status=report['status']), 'historical replay primary mismatch')
    key = (binding['report']['sha256'],binding['replay']['sha256'])
    if key in _HISTORICAL_APPROVED:
        require(report['integrity'] == _HISTORICAL_APPROVED[key], 'historical approved graph changed')
        check_integrity(_HISTORICAL_APPROVED[key])
    else:
        require(recalculate, 'historical initial deep validation required')
        graph = evidence_closure([checked(item) for item in report['evidence']]+[checked(report['environment'])])
        require(report['integrity'] == graph, 'historical noncanonical evidence graph')
        _HISTORICAL_APPROVED[key] = graph
    return report


def bound_report(binding, context, environment_path, recalculate=True):
    report = read(checked(binding['report']))
    if report['source_hashes'] == sources() and report['environment'] == ref(environment_path):
        validate_gate(report,recalculate)
    else:
        report = historical_report(binding,context,recalculate)
    require(report['kind'] == 'real' and report['result']['status'] == report['status'], 'finite gate kind/status mismatch')
    return report


def gate_completion(report):
    gate = report['gate']
    if gate in GATES[:6]:
        require(report['status'] == 'passed', 'early gate failed')
    elif gate == 'calibration':
        require(report['status'] == 'failed', 'finite historical calibration must remain failed')
    elif gate == 'generator':
        require(report['status'] in ('passed','failed'), 'generator lacks complete evaluation')
        runs = report['result']['runs']
        require(sorted((r['mode'],r['frequency_hz']) for r in runs) ==
                sorted((m,hz) for m in DESIGN['modes'] for hz in (20,100)), 'finite generator six-run coverage')
    else:
        result = report['result']
        require(report['status'] == 'inconclusive' and result['design'] == 'control-smoke-v1' and
                sorted((g['mode'],g['profile'],g['n']) for g in result['groups']) ==
                sorted((m,p,1) for m in DESIGN['modes'] for p in DESIGN['profiles']), 'finite smoke coverage/status')
        require(result['repeat_effect_ms'] == 2 and result['repeat_fullness_pp'] == 1, 'fixed reproduction tolerances')


def verify_limited(report, environment_path, final, required, recalculate=True):
    require(report['kind'] == 'real' and report['readiness_version'] == VERSION and
            report['source_hashes'] == sources() and report['environment'] == ref(environment_path) and
            (not final or report['final']), 'finite readiness source/environment/scope mismatch')
    policy(report['policy'])
    require(set(required) <= set(GATES) and set(report['gate_bindings']) <= set(GATES), 'unknown finite gate')
    context = current_environment(environment_path)
    rows = report['document']['checks']
    require(len(rows) == len(GATES) and {r['id'] for r in rows} == set(GATES) and all(r['mandatory'] for r in rows),
            'finite readiness ten retained gate rows required')
    for row in rows:
        binding = report['gate_bindings'].get(row['id'])
        if binding is None:
            require(row['status'] == 'not_run' and row['evidence'] == [] and row['actual'] is None,
                    'finite not-run row mismatch')
            require(row['id'] not in required, 'finite required evidence not collected')
            continue
        gate_report = bound_report(binding,context,environment_path,recalculate)
        require(gate_report['gate'] == row['id'] and row['status'] == gate_report['status'] and
                row['actual'] == gate_report['result'] and row['evidence'] == [binding['report']],
                'finite readiness rewrote historical/current gate outcome')
        if row['id'] in required:
            gate_completion(gate_report)
    require(report['prior_outcomes'], 'finite prior incomplete outcomes must remain disclosed')
    disclosed_partial = False
    for binding in report['prior_outcomes']:
        path = checked(binding)
        if path.suffix == '.json':
            prior = read(path)
            if prior.get('scope') == 'descriptive-unsealed-partial-not-official-run':
                require(prior['planned_outcomes_original'] == 6 and prior['officially_complete'] == 0 and
                        prior['started'] == 1 and prior['other_planned'] == 5, 'initial incomplete outcome accounting')
                require(prior['primary_hashes'], 'initial partial primary receipt missing')
                for name,sha in prior['primary_hashes'].items():
                    require(Path(name).is_file() and digest(Path(name)) == sha, 'initial partial primary changed: '+name)
                disclosed_partial = True
    require(disclosed_partial, 'initial incomplete generator outcomes not disclosed')
    return report


def aggregate_limited(data, environment_path, final=False):
    result = dict(kind='real',readiness_version=VERSION,final=final,source_hashes=sources(),
                  environment=ref(environment_path),policy=data['policy'],gate_bindings=data['gates'],
                  prior_outcomes=data['prior_outcomes'],document=dict(schema_version=1,checks=[]))
    context = current_environment(environment_path)
    policy(data['policy'])
    for gate in GATES:
        binding = data['gates'].get(gate)
        report = bound_report(binding,context,environment_path) if binding else None
        result['document']['checks'].append(dict(id=gate,mandatory=True,expected='finite policy completion; original status retained',
            actual=report['result'] if report else None,units='gate',tolerance=None,
            status=report['status'] if report else 'not_run',reason='known-limitations-explicit-policy' if report else 'gate_report_not_provided',
            utc=now(),evidence=[binding['report']] if binding else []))
    verify_limited(result,environment_path,final,GATES if final else tuple(data['gates']))
    return result,0
