import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import traceback

ROOT=Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
os.chdir(ROOT)
BASE=Path('results/verify/readiness/stage4/practical-v1/full-calibration')
RELEASE=Path('results/verify/readiness/stage4/practical-v1/release-v2')
ENV=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
TLS=ROOT/'build/series-tls-stage2._n__udb0'
HEAD=json.loads((RELEASE/'release.json').read_text())['head']
INVENTORY=json.loads((RELEASE/'source-inventory.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
execution=Path(tempfile.mkdtemp(prefix='execution.',dir=BASE))
(execution/'started').write_text(stamp()+'\n')
def write(name,value):(execution/name).write_text(json.dumps(value,indent=2)+'\n')
def identity():
    files=[*INVENTORY,str(ENV),str(TLS/'server/good/cert.pem'),'build/release-state.json',
        str(BASE/'run.py'),str(BASE/'plan.md'),str(BASE/'collection-plan.json'),str(BASE/'check-prerequisites.py'),
        'docs/readiness/practical-preflight.py',str(RELEASE/'REPORT_MAP.json'),str(RELEASE/'timer-independent-review.json'),
        'results/verify/readiness/stage4/practical-v1/applicability/qualification-and-bw-bridge-v2.json']
    return {p:sha(p) for p in files}
def interrupted(signum, frame):
    raise KeyboardInterrupt('launch interrupted')
signal.signal(signal.SIGTERM,interrupted)
process=None
before=None
code=2
existing={str(p) for p in Path('results/verify/diagnostic').glob('calibration.*') if p.is_dir()}
write('existing-calibration-directories.json',sorted(existing))
write('command.json',dict(argv=['sh','docker/calibration.sh'],head=HEAD,network_limit_s=2400,TLS=str(TLS),acceptance='collection exit0 is pending independent raw/observed gate review'))
print('Execution:',execution,flush=True)
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        fixed=json.loads((BASE/'FIXED-SHA256.json').read_text())
        assert all(sha(p)==h for p,h in fixed.items()), 'preregistered launch inputs changed'
        spec=importlib.util.spec_from_file_location('preflight','docs/readiness/practical-preflight.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        preflight=module.check()
        write('preflight-reference.json',dict(path=str(preflight),result=json.loads((preflight/'result.json').read_text())))
        assert subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=5).strip()==HEAD
        assert all(sha(p)==h for p,h in INVENTORY.items())
        argv=['docker','run','--rm','--network','none','-e','PYTHONDONTWRITEBYTECODE=1','-v',str(ROOT)+':/bench','-w','/bench','wswt-bench-analyzer:dev','timeout','120','python','-B',str(BASE/'check-prerequisites.py')]
        result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=130)
        result.check_returncode()
        before=identity();write('identity-before.json',before)
        process=subprocess.Popen(['sh','docker/calibration.sh'],stdout=stdout,stderr=stderr,env=dict(os.environ,SERIES_TLS_DIR=str(TLS)),start_new_session=True)
        try:code=process.wait(timeout=2400)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            code=124
        new=sorted(str(p) for p in Path('results/verify/diagnostic').glob('calibration.*') if p.is_dir() and str(p) not in existing)
        write('new-calibration-directories.json',new)
        assert len(new)==1
        run=Path(new[0]);(execution/'CAL_RUN').write_text(str(run)+'\n')
        if code==0:
            read=lambda name:json.loads((run/name).read_text())
            assert (run/'exit').read_text().strip()=='0'
            assert read('context-before.json')==read('context-after.json')==json.loads(ENV.read_text())
            assert read('sources-before.json')==read('sources-after.json')==INVENTORY
            assert read('collection-plan.json')==json.loads((BASE/'collection-plan.json').read_text())
            for entry in read('captured.json'):assert sha(entry['path'])==entry['sha256']
            write('collection-status.json',dict(status='collected_pending_independent_review',run=str(run),calibration_passed=False))
    except BaseException:
        traceback.print_exc(file=stderr)
        code=2
    finally:
        new=sorted(str(p) for p in Path('results/verify/diagnostic').glob('calibration.*') if p.is_dir() and str(p) not in existing)
        write('new-calibration-directories.json',new)
        if len(new)==1:(execution/'CAL_RUN').write_text(new[0]+'\n')
        try:
            after=identity();write('identity-after.json',after)
            if before is not None:assert after==before
        except BaseException:traceback.print_exc(file=stderr);code=2
        if code:(execution/'STOP').write_text('Preflight/collection/identity failed; preserve raw; no automatic repeat.\n')
        (execution/'ended').write_text(stamp()+'\n');(execution/'exit').write_text(str(code)+'\n')
print('Execution:',execution,'exit:',code,flush=True)
if code:print((execution/'stderr.log').read_text()[-3000:])
raise SystemExit(code)
