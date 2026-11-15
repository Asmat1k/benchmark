from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


ROOT = Path.cwd()
BASE = ROOT/'results/verify/readiness/stage4/practical-v1/independent-results'
assert (BASE.parent/'implementation/regression.exit').read_text().strip() == '0'
image = 'sha256:9e263785dc135db52a216bc358c38218cf3d98f178a9981a365ca79cda7cbd62'
argv = ['docker','run','--rm','--network','none','--cpus','1','-e','PYTHONDONTWRITEBYTECODE=1',
        '-e','PYTHONPATH=src/analysis','-e','OPENBLAS_NUM_THREADS=1','-v',f'{ROOT}:/bench','-w','/bench',
        image,'timeout','120','python','-B',str((BASE/'compare.py').relative_to(ROOT))]
started = datetime.now(timezone.utc).isoformat()
clock = time.monotonic()
with (BASE/'stdout.log').open('xb') as stdout, (BASE/'stderr.log').open('xb') as stderr:
    try:
        result = subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=135)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
ended = datetime.now(timezone.utc).isoformat()
metadata = dict(argv=argv,cwd=str(ROOT),started_utc=started,ended_utc=ended,
                elapsed_s=time.monotonic()-clock,exit=code,network='none',
                purpose='Exploratory independent replay only, not a new confirmation',
                execution_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with (BASE/'execution.json').open('x') as out:
    json.dump(metadata,out,indent=2)
    out.write('\n')
with (BASE/'exit').open('x') as out:
    out.write(str(code)+'\n')
print(json.dumps(metadata,indent=2))
raise SystemExit(code)
