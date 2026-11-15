import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

base=Path('results/verify/readiness/stage4/deep-review-v1/affinity-abba')
execution=Path(tempfile.mkdtemp(prefix='execution.',dir=base))
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def identity():
    paths=list((base/'tools').glob('*.py'))+[base/'collect.sh',base/'plan.md',Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json'),Path('build/series-tls-stage2._n__udb0/server/good/cert.pem')]
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(execution/'started').write_text(stamp()+'\n')
(execution/'identity-before.json').write_text(json.dumps(identity(),indent=2)+'\n')
env=dict(os.environ,SERIES_TLS_DIR=str(Path('build/series-tls-stage2._n__udb0').resolve()))
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    process=subprocess.Popen(['sh',str(base/'collect.sh')],env=env,stdout=stdout,stderr=stderr,start_new_session=True)
    try:
        code=process.wait(timeout=270)
    except subprocess.TimeoutExpired:
        (execution/'TIMEOUT').write_text('270seconds; terminating diagnostic, no retry\n')
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait()
        code=124
(execution/'identity-after.json').write_text(json.dumps(identity(),indent=2)+'\n')
(execution/'ended').write_text(stamp()+'\n')
(execution/'exit').write_text(str(code)+'\n')
print(execution)
print('exit',code)
print((execution/'stdout.log').read_text()[-1200:])
raise SystemExit(code)
