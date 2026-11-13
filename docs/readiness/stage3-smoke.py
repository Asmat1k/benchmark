import hashlib
import ipaddress
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
TLS = ROOT / 'build/series-tls-stage2._n__udb0'
PIN = 'fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    os.chdir(ROOT)
    power = output('pmset', '-g', 'batt')
    if "Now drawing from 'AC Power'" not in power:
        raise SystemExit('STOP: connect AC power before smoke')
    head = output('git', 'rev-parse', 'HEAD')
    subprocess.run(['sh', 'docker/check-release.sh', head], check=True)
    subprocess.run(['sh', 'docker/release-state.sh'], check=True)
    expected = json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())
    images = json.loads(output('docker', 'image', 'inspect', *(i['tag'] for i in expected)))
    if any((a['Id'], a['Os'], a['Architecture']) != (e['image_id'], e['os'], e['architecture']) for a, e in zip(images, expected)):
        raise SystemExit('STOP: release images changed')
    if output('docker', 'info', '--format', '{{.NCPU}} {{.MemTotal}}') != '2 4109484032':
        raise SystemExit('STOP: Docker resources changed')
    networks = json.loads(output('docker', 'network', 'inspect', *output('docker', 'network', 'ls', '-q').split()))
    laboratory = [ipaddress.ip_network(s) for s in ('172.28.10.0/24', '172.28.20.0/24')]
    for network in networks:
        for config in network['IPAM']['Config'] or []:
            subnet = ipaddress.ip_network(config['Subnet'])
            if any(subnet.overlaps(target) for target in laboratory):
                raise SystemExit('STOP: laboratory subnet occupied')
    certificate = TLS / 'server/good/cert.pem'
    der = subprocess.check_output(['openssl', 'x509', '-in', str(certificate), '-outform', 'DER'])
    if hashlib.sha256(der).hexdigest() != PIN:
        raise SystemExit('STOP: unexpected leaf identity')
    subprocess.run(['openssl', 'x509', '-in', str(certificate), '-checkend', '691200', '-noout'], check=True)
    subprocess.run(['docker', 'run', '--rm', '-i', '--network', 'none', '-v', f'{ROOT}:/bench', '-w', '/bench',
                    'wswt-bench-analyzer:dev', 'python', '-B', 'src/analysis/series.py', 'hold'], input=b'', check=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = Path('results/verify/readiness/stage3') / f'smoke-run-{stamp}'
    directory.mkdir(parents=True, exist_ok=False)
    before = set(Path('results/verify/path').glob('wswt-smoke.*'))
    leaf_before = digest(certificate)
    command = ['caffeinate', '-ims', 'sh', 'docker/smoke.sh']
    print(f'Journal: {directory}/smoke.txt', flush=True)
    started = time.monotonic()
    with (directory / 'smoke.txt').open('w') as log:
        result = subprocess.run(command, env={**os.environ, 'SERIES_TLS_DIR': str(TLS)}, stdout=log, stderr=subprocess.STDOUT)
    paths = sorted(set(Path('results/verify/path').glob('wswt-smoke.*')) - before)
    record = dict(command=command, cwd=str(ROOT), head=head, helper_sha256=digest(Path(__file__)),
                  power=power, tls_dir=str(TLS), leaf_before=leaf_before, leaf_after=digest(certificate),
                  images=[dict(tag=e['tag'], id=a['Id']) for a, e in zip(images, expected)],
                  exit=result.returncode, seconds=time.monotonic()-started, paths=[str(p) for p in paths])
    (directory / 'execution.json').write_text(json.dumps(record, indent=2)+'\n')
    files = [p for root in [directory, *paths] for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS']
    (directory / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p}\n' for p in sorted(files)))
    print(json.dumps(record, indent=2))
    if result.returncode or record['leaf_before'] != record['leaf_after']:
        (directory / 'STOP').write_text('smoke failed or persistent leaf changed; inspect execution.json and smoke.txt\n')
        return result.returncode or 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
