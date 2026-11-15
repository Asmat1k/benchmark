import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from measurement.raw import ROOT, read, require, rows, write
from measurement.resources import validate_resources


CLOCK_QUANTUM_USEC = 10000
MAX_RESOURCE_INTERVAL_USEC = 1500000
QUIET_WINDOW_USEC = 3*MAX_RESOURCE_INTERVAL_USEC+2*CLOCK_QUANTUM_USEC
MIN_COMPLETE_SAMPLES = 2


def quiet_summary(records, marker):
    validator = Draft202012Validator(read(ROOT/'configs/schemas/resource.schema.json'))
    for row in records:
        validator.validate(row)
    require(len({row['run_id'] for row in records}) == 1, 'mixed quiet CPU run identity')
    window = dict(start_usec=marker+CLOCK_QUANTUM_USEC, end_usec=marker+QUIET_WINDOW_USEC)
    validate_resources(records, window)
    result = {}
    for role in ('browser','server','router'):
        samples = [r for r in records if r['role']==role]
        require(all('cpu_start_lower_usec' in r and 'cpu_end_upper_usec' in r for r in samples),
                'CPU snapshot brackets required')
        selected = [r for r in samples if r['cpu_start_lower_usec'] > window['start_usec'] and
                    r['cpu_end_upper_usec'] <= window['end_usec']]
        require(len(selected) >= MIN_COMPLETE_SAMPLES, 'insufficient complete quiet CPU intervals')
        result[role] = dict(selected=selected, count=len(selected),
                            total_interval_usec=sum(r['interval_usec'] for r in selected),
                            peak_ceil_pct=max((100*r['cpu_usage_usec']+r['interval_usec']-1)//r['interval_usec'] for r in selected))
    return dict(run_id=records[0]['run_id'], window=window, roles=result, limitation='CPU counter reads bracketed by quantized VM uptime; CPU percentage uses existing sampler elapsed denominator; external marker still adds VM scheduling load')


def compare(baseline, idle):
    require(baseline['run_id'] == idle['run_id'], 'mixed baseline/idle run identity')
    roles = {role:dict(baseline_ceil_pct=baseline['roles'][role]['peak_ceil_pct'],
                       idle_ceil_pct=idle['roles'][role]['peak_ceil_pct'],
                       passed=idle['roles'][role]['peak_ceil_pct'] <= baseline['roles'][role]['peak_ceil_pct'])
             for role in ('browser','server','router')}
    return dict(status='passed' if all(r['passed'] for r in roles.values()) else 'failed',roles=roles)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('baseline')
    parser.add_argument('idle',nargs='?')
    args = parser.parse_args()
    if args.idle:
        result = compare(read(args.directory/(args.baseline+'-cpu.json')),read(args.directory/(args.idle+'-cpu.json')))
        print(json.dumps(result,allow_nan=False))
        raise SystemExit(0 if result['status']=='passed' else 1)
    records = [r for role in ('browser','server','router') for r in rows(args.directory/(args.baseline+'-'+role+'.jsonl'))]
    marker = int((args.directory/(args.baseline+'-marker')).read_text())
    write(args.directory/(args.baseline+'-cpu.json'),quiet_summary(records,marker))
