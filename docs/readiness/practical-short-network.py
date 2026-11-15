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

spec=importlib.util.spec_from_file_location('preflight','docs/readiness/practical-preflight.py')
preflight=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
mode=sys.argv[1]
assert mode in ('smoke','timer')
base=Path('results/verify/readiness/stage4/practical-v1/release-v2')
base.mkdir(parents=True,exist_ok=True)
execution=Path(tempfile.mkdtemp(prefix=mode+'-execution.',dir=base))
argv=['sh','docker/smoke.sh'] if mode=='smoke' else ['sh','docker/collect-diagnostic.sh','timer']
limit=90 if mode=='smoke' else 130
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
record=dict(argv=argv,limit_s=limit,start=stamp(),preflight=None)
code=2
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        record['preflight']=str(preflight.check())
        snapshot=json.loads((Path(record['preflight'])/'source-inventory.json').read_text())
        process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=dict(os.environ,SERIES_TLS_DIR=str(preflight.TLS)),start_new_session=True)
        try:code=process.wait(timeout=limit)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            code=124
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
    try:
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in snapshot.items())
        assert hashlib.sha256((preflight.TLS/'server/good/cert.pem').read_bytes()).hexdigest()=='ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9'
        assert subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=5).strip().startswith(preflight.HEAD)
        record['identity_after']='source HEAD and all source hashes plus TLS exact; actual timer context separately checked'
    except BaseException:
        code=2
        import traceback
        traceback.print_exc(file=stderr)
    record.update(end=stamp(),exit=code)
    (execution/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
    (execution/'exit').write_text(str(code)+'\n')
    if code:(execution/'STOP').write_text('No automatic repeat; preserve all outputs.\n')
print(execution)
sys.exit(code)
