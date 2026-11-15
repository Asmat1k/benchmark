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
directory = Path(sys.argv[1])
phase = json.loads((directory/'admission.json').read_text())['phase']
if phase == 'main':
    raise SystemExit('Main execution withheld by the latest user instruction; preparation only.')
limit = dict(aa=5400, monitoring=5400, pilot=10800, main=54000)[phase]
base = ROOT/'results/verify/readiness/finite-browser-study-v1'
execution = Path(tempfile.mkdtemp(prefix=phase+'-execution.', dir=base))
stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
record = dict(started_utc=stamp(), series=str(directory), limit_s=limit)
(execution/'started').write_text(record['started_utc']+'\n')
code = 2
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        head = subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=10).strip()
        subprocess.run(['sh','docker/release-state.sh'],check=True,stdout=stdout,stderr=stderr,timeout=60)
        spec = importlib.util.spec_from_file_location('preflight','docs/readiness/practical-preflight.py')
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)
        preflight.HEAD, preflight.BASE = head, base
        record['preflight'] = str(preflight.check())
        snapshot = json.loads((Path(record['preflight'])/'source-inventory.json').read_text())
        record.update(head=head,source_hashes=snapshot,admission_sha256=hashlib.sha256((directory/'admission.json').read_bytes()).hexdigest())
        argv = ['sh','docker/experiment.sh',str(directory),'yes']
        record['argv'] = argv
        (execution/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
        process = subprocess.Popen(argv,stdout=stdout,stderr=stderr,start_new_session=True,
                                   env=dict(os.environ,SERIES_TLS_DIR=str(preflight.TLS)))
        try:
            code = process.wait(timeout=limit)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            code = 124
        assert subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=10).strip() == head
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p,sha in snapshot.items())
        assert hashlib.sha256((directory/'admission.json').read_bytes()).hexdigest() == record['admission_sha256']
        record['containers_after'] = subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True,timeout=20).splitlines()
        assert not any(name.startswith('wswt-') for name in record['containers_after'])
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
        code = 2
    finally:
        record.update(ended_utc=stamp(),exit=code)
        (execution/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
        (execution/'exit').write_text(str(code)+'\n')
        (execution/'ended').write_text(record['ended_utc']+'\n')
        if code:
            (execution/'STOP').write_text('No automatic retry or replacement; retain all planned outcomes and partial logs.\n')
print(execution,flush=True)
sys.exit(code)
