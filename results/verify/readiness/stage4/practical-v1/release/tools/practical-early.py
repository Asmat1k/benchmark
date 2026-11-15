import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path('src/analysis').resolve()))

from admission import checked, ref, sources, validate_gate
from collection import PRIMARY_IDS
from diagnostic_input import diagnostic_raw
from raw import now, read, require, validate_raw, write


def prepare(smoke, timer_path, output):
    timer = read(timer_path)
    validate_gate(timer)
    require(timer['status'] == 'passed', 'timer must pass before primary preparation')
    environment_path = checked(timer['environment'])
    environment = read(environment_path)
    hashes = sources()
    stage2 = Path('results/verify/readiness/stage2-preflight')
    stage3 = Path('results/verify/readiness/stage4/practical-v1/release')
    build_history = Path('results/verify/readiness/stage4/release-v3')
    historical = Path('results/verify/readiness/stage3')
    require(hashes == read(stage3 / 'source-inventory.json'), 'current inventory correspondence')
    previous = read(Path('results/verify/readiness/stage4/release-v4/source-inventory.json'))
    changed = {p for p in set(hashes)|set(previous) if hashes.get(p) != previous.get(p)}
    allowed = {'configs/plan.json','docs/protocol.md','docs/schemas/plan.schema.json',
               'docker/calibration_probe.py','docker/calibration_probe_test.py','docker/calibration_report.py',
               'docker/calibration_test.py','src/analysis/acceptance.py','src/analysis/calibration_blocks.py',
               'src/analysis/calibration_observed.py','src/analysis/sender_quality.py','src/analysis/test_calibration_observed.py'}
    require(changed <= allowed, 'explicit host-mounted calibration source delta only')
    require(all(hashes[p] == previous[p] for p in hashes if p.startswith(('src/client/','src/server/','src/runner/'))),
            'unchanged browser/server/client dependencies for image and client-test applicability')
    expected_images = read(stage2 / 'release-evidence.json')
    expected_by_role = {i['tag'].split('-')[-1].split(':')[0]: i['image_id'] for i in expected_images}
    require(all(s['id'] == expected_by_role[s['role']] for s in environment['services']), 'actual environment image IDs')
    schedule_path = checked(read(checked(timer['evidence'][0]))['evidence'][0])
    directory = schedule_path.parent
    schedule = read(schedule_path)
    folders = []
    for index, run in enumerate(schedule['runs']):
        folder = directory / 'raw' / run['run_id']
        if index == 0:
            diagnostic_raw(directory, run, schedule, environment, hashes)
        else:
            validate_raw(folder, schedule_path)
            manifest = read(folder / 'manifest.json')
            require(all(manifest[k] == v for k, v in run.items()), 'second diagnostic attribution')
            require(read(folder / 'context.json') == environment and read(folder / 'schedule.json') == schedule,
                    'second diagnostic context/schedule')
            require(not manifest['dirty'] and manifest['commit'] == read(folders[0] / 'manifest.json')['commit'],
                    'second diagnostic release')
            require(not (folder / 'SYNTHETIC.json').exists(), 'synthetic second diagnostic')
        folders.append(folder)
    require(len(folders) == 2, 'both short D3 runs required')
    output.mkdir(parents=True, exist_ok=False)
    evidence = {}
    for gate in ('build', 'tls', 'path', 'raw', 'analysis'):
        (output / gate).mkdir()
        evidence[gate] = []

    def add(gate, identity, actual, scope, command, files, observations):
        require(identity in PRIMARY_IDS[gate], 'unknown primary ID')
        collection_id = output.name + '-' + gate
        trace_path = output / gate / (identity + '.json')
        trace = dict(collection_id=collection_id, gate=gate, id=identity, actual=bool(actual), scope=scope,
                     command=command, observations=observations, files=[ref(p) for p in files],
                     preparer=ref(Path(__file__)), source_inventory=ref(stage3 / 'source-inventory.json'), applicability=ref(stage3 / 'release.json'))
        write(trace_path, trace)
        evidence[gate].append(dict(id=identity, mandatory=True, expected=True, actual=bool(actual), units='predicate',
                                   tolerance=None, status='passed' if actual else 'failed',
                                   reason=scope, utc=now(), evidence=[ref(trace_path)]))

    build_log = (build_history / 'build.stdout.log').read_text()
    dockerfiles = [Path('docker/Dockerfile.' + role) for role in ('server', 'browser', 'analyzer')]
    installs = ['npm ci', 'go test -mod=readonly', '--require-hashes', 'pip check']
    source_text = '\n'.join(p.read_text() for p in dockerfiles)
    add('build', 'locked-install', all(s in source_text and s in build_log for s in installs),
        'v3 locked install and exact admitted images reused; new analysis modules executed from host mount; dependency delta explicitly disclosed in release capsule',
        'v3 docker/build.sh and content comparison; current image IDs and unchanged build dependencies; new D3 context',
        [build_history / 'build.stdout.log', build_history / 'build.stderr.log', build_history / 'image-comparison.json', build_history / 'analyzer-content-comparison.json', stage3 / 'release.json', stage2 / 'release-build-archive.json', stage2 / 'release-evidence.json', *dockerfiles],
        dict(installation_contracts=installs, image_dependencies_equal=True, actual_image_ids=environment['services']))
    preflight = read(stage3 / 'environment-preflight.json')
    add('build', 'native-platform', preflight['host_arch'].strip() == 'arm64' and preflight['vm']['arch'] == 'aarch64'
        and all((i['os'], i['architecture']) == ('linux', 'arm64') for i in expected_images),
        'actual host, Docker and unchanged release images', 'uname -m; docker info; docker image inspect',
        [stage3 / 'environment-preflight.json', stage2 / 'release-evidence.json'], preflight['images'])
    browser_rows = [json.loads(line) for line in (smoke / 'browser.txt').read_text().splitlines() if line.startswith('{')]
    browser_version = browser_rows[0]
    python_versions = (stage2 / 'release-python.txt').read_text().strip()
    add('build', 'versions', browser_version['version'] == '140.0.7339.16' and browser_version['node'] == 'v22.18.0'
        and browser_version['playwright'] == '1.55.0' and python_versions.startswith('3.12.11'),
        'current browser runtime plus unchanged image package inventory', 'smoke main.js; stage2 check_environment.py/dpkg-query',
        [smoke / 'browser.txt', smoke / 'build.txt', stage2 / 'release-python.txt', stage2 / 'release-os-packages.txt'],
        dict(browser=browser_version, python=python_versions))
    archive_record = read(stage3 / 'source-archive-preflight.json')['archive']
    archive = Path(archive_record['path'])
    with archive.open('rb') as handle:
        archive_sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    add('build', 'archive-hashes', archive_sha == archive_record['sha256'] and archive_sha in archive.name
        and archive_sha in Path(str(archive) + '.sha256').read_text(),
        'unchanged historical image archive bytes/sidecar and applicable stage2 image-archive content validation; historical source HEAD is not current source release', 'shasum -a 256 -c sidecar; hashlib.file_digest',
        [archive, stage3 / 'source-archive-preflight.json', Path(str(archive) + '.sha256'), stage2 / 'archive-verified.json'],
        dict(path=str(archive), actual_sha256=archive_sha, bytes=archive.stat().st_size, image_ids=expected_images, historical_archive_record=archive_record, current_sources=ref(stage3/'source-inventory.json'), scope='images reused; current host-mounted source files separately bound'))

    modes = {r['mode']: r for r in browser_rows if 'mode' in r}
    require(modes.get('WT-D', {}).get('exactFrames') == 3 and modes['WT-D'].get('supported') is True, 'WT-D must actually echo')
    for identity, mode in [('ws-secure', 'WS'), ('wts-secure', 'WT-S')]:
        add('tls', identity, browser_version['secureContext'] and modes.get(mode, {}).get('exactFrames') == 3,
            'real browser TLS and exact echo', 'caffeinate -ims sh docker/smoke.sh: main.js',
            [smoke / 'browser.txt', smoke / 'server.txt'], dict(runtime=browser_version, echo=modes[mode], wt_d=modes['WT-D']))
    for case, name, error in [('wrong-ca', 'unknown-ca', 'CERT_AUTHORITY_INVALID'), ('wrong-san', 'wrong-san', 'CERT_COMMON_NAME_INVALID'),
                               ('expired', 'expired', 'CERT_DATE_INVALID')]:
        row = next(r for r in browser_rows if r.get('name') == name and 'https' in r)
        for protocol in ('https', 'ws'):
            actual = row['https'] == error and (protocol == 'https' or row['wss'] == 'rejected')
            add('tls', protocol + '-' + case, actual, 'real negative TLS probe with specific certificate error',
                'smoke main.js: assert navigation rejection / WebSocket console certificate error', [smoke / 'browser.txt'], row)
    for case in ('wrong-pin', 'expired'):
        row = next(r for r in browser_rows if r.get('name') == case and 'wt' in r)
        actual = row['wt'] == 'WebTransportError' and 'CERTIFICATE_VERIFY_FAILED' in (smoke / 'browser.txt').read_text()
        add('tls', 'wt-' + case, actual, 'real WebTransport negative TLS probe', 'smoke main.js: WebTransport rejection and TLS console assertion',
            [smoke / 'browser.txt'], row)

    route_files = [smoke / (role + '-route.txt') for role in ('browser', 'server')]
    route_ok = all(expected in path.read_text() for path, expected in zip(route_files,
                    ['172.28.20.10 via 172.28.10.2 dev bench0', '172.28.10.10 via 172.28.20.2 dev bench0']))
    add('path', 'routes', route_ok, 'real route readbacks', 'smoke setup_links: ip route get; router ip route',
        [*route_files, smoke / 'router.txt'], dict(routes=[p.read_text() for p in route_files]))
    trace = (smoke / 'trace.txt').read_text()
    for protocol, marker in [('tcp', 'Flags'), ('udp', 'UDP')]:
        for direction, source, target, hops in [('forward', '172.28.10.10', '172.28.20.10', [('to_browser', 'In'), ('to_server', 'Out')]),
                                                ('reverse', '172.28.20.10', '172.28.10.10', [('to_server', 'In'), ('to_browser', 'Out')])]:
            matches = [[line for line in trace.splitlines() if re.search(rf'{interface} +{way} .*{re.escape(source)}\.\d+ > {re.escape(target)}\.\d+: .*{marker}', line)]
                       for interface, way in hops]
            add('path', protocol + '-' + direction, all(matches), 'real router packet capture on both interfaces',
                'smoke tcpdump -i any; iptables counters', [smoke / 'trace.txt', smoke / 'counters.txt'], dict(hops=hops, first_matches=[m[:1] for m in matches]))
    forwarding = (smoke / 'forwarding-disabled.txt').read_text().splitlines()
    blocked = json.loads(forwarding[-1])
    for identity, key in [('forwarding-off-ws', 'ws'), ('forwarding-off-wts', 'wt')]:
        add('path', identity, forwarding[0] == '0' and blocked[key] in ('rejected', 'timed_out'), 'real forwarding-off probe',
            'smoke router ip_forward=0; path.js', [smoke / 'forwarding-disabled.txt', smoke / 'forwarding-enabled.txt'], blocked)
    settings = [read(folder / ('network_' + when + '.json')) for folder in folders for when in ('before', 'after')]
    features = ('tcp-segmentation-offload', 'generic-segmentation-offload', 'generic-receive-offload', 'large-receive-offload')
    offload_ok = all('mtu 1500' in text and all(f + ': off' in text for f in features)
                     for setting in settings for text in [setting['links'], *setting['endpoints'].values()])
    add('path', 'offload-mtu', offload_ok, 'real D3 before/after endpoint and router readbacks; validate_raw also checks',
        'measure.sh capture before/after; validate_raw', [folder / ('network_' + when + '.json') for folder in folders for when in ('before', 'after')], settings)
    profiles = read(Path('configs/profiles.json'))
    readbacks = {}
    profile_ok = True
    for profile in profiles['profiles']:
        entries = [json.loads(line.split(' ', 1)[1])[0] for line in (smoke / (profile['id'] + '.txt')).read_text().splitlines()]
        readbacks[profile['id']] = entries
        profile_ok &= len(entries) == 2 and all(q['kind'] == 'netem' and q['options']['limit'] == profiles['limit_packets']
            and q['options']['rate']['rate'] == 1250000 and q['options']['delay']['delay'] == profile['egress_delay_ms'] / 1000
            and q['options'].get('loss-random', {}).get('loss', 0) == profile['egress_loss_pct'] / 100 for q in entries)
    add('path', 'profile-readback', profile_ok, 'real four-profile tc readbacks; no bandwidth/calibration claim',
        'smoke network profile for r20p0/r20p1/r80p0/r80p1', [smoke / (p['id'] + '.txt') for p in profiles['profiles']], readbacks)

    offline = Path('results/verify/readiness/stage4/practical-v1/early-offline/offline.stderr.log')
    client = historical / 'client-framing-tests.txt'
    null = Path('results/verify/readiness/stage4/practical-v1/early-offline/null.stderr.log')
    offline_ok = 'Ran 13 tests' in offline.read_text() and offline.read_text().rstrip().endswith('OK')
    client_ok = '# pass 9' in client.read_text() and '# fail 0' in client.read_text()
    with tempfile.TemporaryDirectory() as temporary:
        copied = Path(temporary) / 'raw'
        shutil.copytree(folders[0], copied)
        with (copied / 'slots.jsonl').open('a') as handle:
            handle.write('\n')
        try:
            validate_raw(copied, schedule_path)
            tamper_error = None
        except ValueError as error:
            tamper_error = str(error)
    raw_files = [schedule_path, stage3 / 'timer-execution/execution.json']
    raw_observation = dict(validated_runs=[str(p) for p in folders], short_slots=[read(p / 'completion.json') for p in folders],
                           tampered_copy_error=tamper_error, real_replacement_performed=False, offline_fixture_reuse='current offline/raw/null tests; historical client test reused only with unchanged client sources and same server/browser image IDs')
    raw_specs = {
        'framing': (client_ok, 'real three-mode smoke and short raw; framing edge cases use synthetic client transport', [client, smoke / 'browser.txt']),
        'clock-boundaries': (offline_ok and client_ok, 'real raw clock invariants; exact deadline/late edges use injected fixture clocks', [offline, client]),
        'slot-accounting': (offline_ok and client_ok, 'real short slots/events/counters; missed wakes/loss/late/disconnect use fixtures', [offline, client]),
        'hash-integrity': (tamper_error == 'hash mismatch', 'real full raw hash validation plus tampered temporary copy rejected', [offline]),
        'log-completeness': (offline_ok, 'real completion/events/server logs; missing-journal STOP uses fixture', [offline]),
        'resource-coverage': (offline_ok, 'real three-role resource windows; missing intervals use fixtures', [offline]),
        'replacement-recovery': (offline_ok, 'fixture behavior only: replacement, lock and recovery; no successful real series claimed', [offline]),
    }
    for identity, (actual, scope, files) in raw_specs.items():
        add('raw', identity, actual, scope, 'D3 diagnostic_raw/validate_raw both runs; stage3 documented unittest/node commands',
            [*files, *raw_files], raw_observation)
    analysis_tests = {
        'metrics-boundaries': 'test_metrics_deadlines_penalty_and_diagnostics', 'full-n-sign': 'test_exact_sign_enumeration_and_rank_coverage',
        'holm4': 'test_all_prespecified_references', 'rank-intervals': 'test_exact_sign_enumeration_and_rank_coverage',
        'paired-bootstrap': 'test_bootstrap_preserves_blocks_and_replay', 'offline-reference': 'test_all_prespecified_references',
    }
    for identity, method in analysis_tests.items():
        actual = offline_ok and any(line.startswith(method + ' ') and line.endswith(' ... ok') for line in offline.read_text().splitlines())
        add('analysis', identity, actual, 'current known-answer checks; no network performance claim',
            'python -B -m unittest -v test_analysis.StatisticalTests', [offline, Path('src/analysis/test_analysis.py'), Path('src/analysis/fixtures/references.json')],
            dict(test=method, result='ok' if actual else 'not confirmed'))
    null_ok = 'Ran 1 test' in null.read_text() and null.read_text().rstrip().endswith('OK')
    add('analysis', 'null-family', null_ok, 'new temporary synthetic null fixture with current protocol/context; original failures retained',
        'python -B docs/readiness/stage3-null-fixture.py', [null, Path('docs/readiness/stage3-null-fixture.py'), Path('src/analysis/test_analysis.py')],
        dict(test='SeriesTests.test_null_profiles_and_mixed_release_are_not_silently_removed', result='ok' if null_ok else 'not confirmed'))

    for gate, checks in evidence.items():
        require({r['id'] for r in checks} == set(PRIMARY_IDS[gate]), 'primary coverage')
        document = dict(schema_version=1, checks=checks)
        collection_id = output.name + '-' + gate
        meta = dict(kind='real', gate=gate, collection_id=collection_id, environment=timer['environment'], source_hashes=hashes)
        payload = output / gate / 'payload.json'
        write(payload, dict(gate=gate, collection_id=collection_id, document=document,
                            observations={r['id']: dict(collection_id=collection_id, **r) for r in checks}))
        collection = output / gate / 'collection.json'
        write(collection, dict(**meta, payload=ref(payload)))
        write(output / gate / 'input.json', dict(**meta, collection=ref(collection), document=document))
    print(json.dumps(dict(environment=timer['environment'], output=str(output), predicates={g: {r['id']: r['status'] for r in checks} for g, checks in evidence.items()}), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('smoke', type=Path)
    parser.add_argument('timer_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.smoke, args.timer_report, args.output)
