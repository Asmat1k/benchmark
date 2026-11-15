import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
BASE = Path('results/verify/readiness/browser-generator-v1')
BASE.mkdir(parents=True, exist_ok=True)
execution = Path(tempfile.mkdtemp(prefix='execution.', dir=BASE))
ENV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
FAILED = Path('results/verify/readiness/stage4/practical-v1/full-calibration/calibration-sFWOAzbo-report.json')
POLICY = Path('docs/readiness/browser-generator-policy-v1.md')
DECISION = execution/'admission.json'
stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
record = dict(start=stamp(), network_limit_s=1500, environment=str(ENV), admission=str(DECISION))
code = 2
analyze = ['docker', 'run', '--rm', '--network', 'none', '-v', str(ROOT)+':/bench',
           '-v', str(ROOT)+':'+str(ROOT), '-w', '/bench', 'wswt-bench-analyzer:dev', 'python', '-B']
with (execution/'stdout.log').open('x') as stdout, (execution/'stderr.log').open('x') as stderr:
    try:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, timeout=10).strip()
        subprocess.run(['sh', 'docker/lib/release-state.sh'], check=True, timeout=60, stdout=stdout, stderr=stderr)
        spec = importlib.util.spec_from_file_location('preflight', 'docs/readiness/practical-preflight.py')
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)
        preflight.HEAD, preflight.BASE = head, ROOT/BASE
        record['preflight'] = str(preflight.check())
        snapshot = json.loads((Path(record['preflight'])/'source-inventory.json').read_text())
        record.update(head=head, source_hashes=snapshot, policy_sha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),
                      environment_sha256=hashlib.sha256(ENV.read_bytes()).hexdigest())
        subprocess.run(analyze+['src/analysis/browser_admission.py', 'create', str(DECISION), str(ENV), str(FAILED), str(POLICY)],
                       check=True, timeout=180, stdout=stdout, stderr=stderr)
        argv = ['sh', 'docker/commands/collect-diagnostic.sh', 'generator', str(ENV)]
        record['argv'] = argv
        (execution/'started').write_text(record['start']+'\n')
        (execution/'execution.json').write_text(json.dumps(record, indent=2)+'\n')
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True,
                                   env=dict(os.environ, SERIES_TLS_DIR=str(preflight.TLS), BENCH_GENERATOR_ADMISSION=str(DECISION)))
        try:
            code = process.wait(timeout=record['network_limit_s'])
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            code = 124
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, timeout=10).strip() == head
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in snapshot.items())
        assert hashlib.sha256(ENV.read_bytes()).hexdigest() == record['environment_sha256']
        assert hashlib.sha256(POLICY.read_bytes()).hexdigest() == record['policy_sha256']
        assert hashlib.sha256((preflight.TLS/'server/good/cert.pem').read_bytes()).hexdigest() == 'ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9'
        leftovers = subprocess.check_output(['docker', 'ps', '-a', '--format', '{{.Names}}'], text=True, timeout=20).splitlines()
        record['containers_after'] = leftovers
        assert not any(name.startswith('wswt-') for name in leftovers)
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
        code = 2
    record.update(end=stamp(), exit=code)
    (execution/'execution.json').write_text(json.dumps(record, indent=2)+'\n')
    (execution/'exit').write_text(str(code)+'\n')
    (execution/'ended').write_text(record['end']+'\n')
    if code:
        (execution/'STOP').write_text('Preserve all outcomes; no automatic repeat. Inspect logs and partial raw.\n')
print(execution, flush=True)
sys.exit(code)
