import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

root = Path.cwd()
base = root/'results/verify/readiness/finite-browser-study-v1/reproduction-offline'
base.mkdir(parents=True, exist_ok=True)
output = Path(tempfile.mkdtemp(prefix='dependencies.', dir=base))
stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
def inventory():
    paths = [p for p in (root/'src/analysis').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
record = dict(schema_version=1, scope='current analysis source and offline hash-locked dependencies; immutable runtime images reused separately',
              started_utc=stamp(),source_hashes=inventory(),executor_id='/root/reproduction')
program = '''set -eu
cd /wheelhouse
sha256sum -c SHA256SUMS
cd /bench
python -B -m venv /tmp/reproduction-env
/tmp/reproduction-env/bin/python -B -m pip install --no-index --find-links=/wheelhouse --require-hashes --only-binary=:all: -r src/analysis/requirements.txt
/tmp/reproduction-env/bin/python -B -m pip check
PYTHONPATH=src/analysis /tmp/reproduction-env/bin/python -B -c 'from pathlib import Path; files=list(Path("src/analysis").rglob("*.py")); [compile(p.read_text(),str(p),"exec") for p in files]; import admission,acceptance,experiments,limited_readiness,metrics,raw; print("Compiled",len(files),"analysis modules; current imports succeeded")'
/tmp/reproduction-env/bin/python -B -m pip freeze
'''
argv = ['docker','run','--rm','--network','none','-e','PYTHONDONTWRITEBYTECODE=1','-v',str(root)+':/bench:ro','-w','/bench',
        'wswt-bench-analyzer:dev','sh','-c',program]
record['argv'] = argv
code = 2
with (output/'stdout.log').open('x') as stdout,(output/'stderr.log').open('x') as stderr:
    try:
        result = subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=180)
        code = result.returncode
        if inventory() != record['source_hashes']:
            raise ValueError('Analysis sources changed during offline dependency check')
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
        code = 2
    finally:
        record.update(ended_utc=stamp(),exit=code)
(output/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
(output/'exit').write_text(str(code)+'\n')
if code:
    (output/'STOP').write_text('Preserve failed offline dependency check.\n')
print(output)
raise SystemExit(code)
