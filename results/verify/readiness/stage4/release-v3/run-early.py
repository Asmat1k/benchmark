import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

base=Path('results/verify/readiness/stage4/release-v3')
execution=Path(tempfile.mkdtemp(prefix='early-execution.',dir=base))
env=dict(os.environ,SERIES_TLS_DIR=str(Path('build/series-tls-stage2._n__udb0').resolve()))
start=time.monotonic();records=[]
for name,command in [('smoke',['sh','docker/smoke.sh']),('timer',['sh','docker/collect-diagnostic.sh','timer'])]:
 before=set(Path('results/verify/path' if name=='smoke' else 'results/verify/diagnostic').glob('wswt-smoke.*' if name=='smoke' else 'timer-timer.*'))
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
 with (execution/f'{name}.stdout.log').open('x') as stdout,(execution/f'{name}.stderr.log').open('x') as stderr:
  process=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
  try:code=process.wait(timeout=max(1,240-(time.monotonic()-start)))
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGKILL);process.wait()
   code=124
 after=set(Path('results/verify/path' if name=='smoke' else 'results/verify/diagnostic').glob('wswt-smoke.*' if name=='smoke' else 'timer-timer.*'))
 row=dict(name=name,command=command,start=stamp,elapsed_s=time.monotonic()-t,exit=code,new_paths=sorted(str(p) for p in after-before))
 records.append(row);(execution/'execution.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps(row),flush=True)
 if code:raise SystemExit(code)
print(execution,flush=True)
