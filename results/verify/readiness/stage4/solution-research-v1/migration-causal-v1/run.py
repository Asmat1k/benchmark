import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

base=Path('results/verify/readiness/stage4/solution-research-v1/migration-causal-v1')
mode=sys.argv[1]
assert mode in ('selftest','network')
execution=Path(tempfile.mkdtemp(prefix=mode+'.',dir=base))
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.glob('tools/*.py'))+sorted(base.glob('*.sh'))+[base/'plan.md',base/'run.py']}
(execution/'started').write_text(stamp()+'\n')
(execution/'identity-before.json').write_text(json.dumps(identity(),indent=2)+'\n')
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    process=subprocess.Popen(['sh',str(base/(mode+'.sh')),str(execution.resolve())],stdout=stdout,stderr=stderr,start_new_session=True)
    try: code=process.wait(timeout=60 if mode=='selftest' else 270)
    except subprocess.TimeoutExpired:
        (execution/'TIMEOUT').write_text('deadline reached; no retry\n')
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        code=124
(execution/'identity-after.json').write_text(json.dumps(identity(),indent=2)+'\n')
(execution/'ended').write_text(stamp()+'\n');(execution/'exit').write_text(str(code)+'\n')
print(execution);print('exit',code);print((execution/'stdout.log').read_text()[-2000:]);print((execution/'stderr.log').read_text()[-2000:])
raise SystemExit(code)
