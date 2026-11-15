import argparse
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from admission.admission import checked, leaf_covers, ref, sources
from admission.browser_admission import current_environment
from measurement.raw import digest, now, read, require, write
from execution.schedule import make_schedule

VERSION = 'exploratory-browser-study-v2'
LIMITS = dict(run_timeout_seconds=360, cleanup_timeout_seconds=30, series_budget_seconds=54000)
POLICY = Path('configs/policies/exploratory.json')
HISTORY = ('calibration', 'generator', 'aa')


def validate(directory, kind='real', initial=False):
    value = read(directory/'admission.json')
    require(kind == value['kind'] == 'real' and value['schema_version'] == 1 and
            value['phase'] == 'main' and value['execution_policy'] == VERSION,
            'exploratory admission scope')
    require(not (directory/'SYNTHETIC.json').exists(), 'synthetic main forbidden')
    require(value['source_hashes'] == sources(), 'exploratory source changed')
    policy = read(checked(value['policy']))
    require(policy['execution_policy'] == VERSION, 'exploratory policy binding')
    definition = read(checked(policy['document']))
    require(value['limits'] == LIMITS, 'exploratory execution bounds changed')
    schedule = read(directory/'schedule.json')
    require(schedule == read(checked(value['schedule'])) == make_schedule('main', directory.name, 20, 4, True),
            'exploratory fixed schedule changed')
    require(directory.parent.resolve() == Path('results/main').resolve(), 'exploratory main location')
    require(read(directory/'ledger.json') == dict(schema_version=1, series_id=directory.name, attempts=schedule['blocks']),
            'exploratory immutable assignment ledger changed')
    environment = current_environment(checked(value['environment']))
    require(value['history'] == {gate: definition['historical'][gate] for gate in HISTORY},
            'exploratory historical disclosure changed')
    require(value['unperformed'] == ['monitoring', 'pilot', 'power', 'reproduction'], 'unperformed stages changed')
    require(value['limitations'] == 'exploratory-observed-system-no-confirmatory-readiness-or-power-claim',
            'exploratory limitations missing')
    leaf = Path(value['leaf_pem'])
    require(leaf.read_text() == environment['leaf'], 'exploratory TLS differs from measured environment')
    leaf_covers(leaf, value['series_end_utc'])
    if initial:
        remaining = datetime.fromisoformat(value['series_end_utc']) - datetime.now(timezone.utc)
        require(remaining.total_seconds() >= (360 if (directory/'outcomes.json').exists() else LIMITS['series_budget_seconds']),
                'execution horizon expired')
        for name, sha in value['source_hashes'].items():
            saved = directory/'snapshot'/'source'/name
            require(saved.is_file() and digest(saved) == sha, 'exploratory source snapshot changed')
    if (directory/'outcomes.json').exists():
        from execution.execution import load_outcomes
        load_outcomes(directory)
    return value


def prepare(directory, environment_path, tls):
    commit = os.environ.get('BENCH_RELEASE_COMMIT', '')
    require(len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'host release commit required')
    require(directory.parent.resolve() == Path('results/main').resolve() and
            directory.name not in ('', '.', '..'), 'main directory required')
    require(not directory.exists(), 'immutable exploratory series already exists')
    environment = current_environment(environment_path)
    leaf = tls/'server/good/cert.pem'
    require(leaf.read_text() == environment['leaf'], 'actual measured TLS required')
    end = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    leaf_covers(leaf, end, LIMITS['series_budget_seconds'])
    directory.mkdir(parents=True)
    snapshot = directory/'snapshot'
    snapshot.mkdir()
    schedule = make_schedule('main', directory.name, 20, 4, True)
    write(directory/'schedule.json', schedule)
    write(snapshot/'schedule.json', schedule)
    write(directory/'ledger.json', dict(schema_version=1, series_id=directory.name, attempts=schedule['blocks']))
    shutil.copyfile(environment_path, snapshot/'environment.json')
    shutil.copyfile(POLICY, snapshot/'policy-definition.json')
    write(snapshot/'policy.json', dict(execution_policy=VERSION, document=ref(snapshot/'policy-definition.json')))
    inventory = sources()
    for name in inventory:
        destination = snapshot/'source'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, destination)
    value = dict(schema_version=1, kind='real', phase='main', execution_policy=VERSION,
                 created_utc=now(), release_commit=commit,
                 source_hashes=inventory, environment=ref(snapshot/'environment.json'),
                 schedule=ref(snapshot/'schedule.json'), policy=ref(snapshot/'policy.json'),
                 history={gate:read(POLICY)['historical'][gate] for gate in HISTORY},
                 unperformed=['monitoring','pilot','power','reproduction'], limits=LIMITS,
                 limitations='exploratory-observed-system-no-confirmatory-readiness-or-power-claim',
                 leaf_pem=str(leaf), series_end_utc=end)
    write(directory/'admission.json', value)
    validate(directory, initial=True)
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'check'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--environment', type=Path)
    parser.add_argument('--tls', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        require(args.environment is not None and args.tls is not None, 'actual environment and persistent TLS required')
        print(prepare(args.directory, args.environment, args.tls))
    else:
        validate(args.directory, initial=True)
        print(args.directory)
