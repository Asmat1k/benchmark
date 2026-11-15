import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import traceback

root=Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
os.chdir(root)
base=Path('results/verify/readiness/stage4/solution-research-v1/qualification')
validation=base.parent/'production-validation'
execution=Path(tempfile.mkdtemp(prefix='execution.',dir=base))
tls=root/'build/series-tls-stage2._n__udb0'
head='d66559066b704fde567b6c9f92f57e2dcde22698'
inventory=json.loads((validation/'source-inventory.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):(execution/name).write_text(json.dumps(value,indent=2)+'\n')
def identity():
    files=[*inventory,str(base/'run.py'),str(base/'plan.md'),str(validation/'preflight.py'),str(validation/'analysis.json'),'build/release-state.json',str(tls/'server/good/cert.pem'),'results/verify/diagnostic/timer-timer.2ST8NYBU/context.json']
    rows=json.loads(subprocess.check_output(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev'],text=True,timeout=20))
    return dict(files={p:sha(p) for p in files},images=[r['Id'] for r in rows])

before={str(p) for p in Path('results/verify/diagnostic').glob('sender-diagnostic.*') if p.is_dir()}
(execution/'started').write_text(stamp()+'\n');(execution/'collector.sh').write_bytes(Path('docker/sender-diagnostic.sh').read_bytes())
write('command.json',dict(argv=['sh','docker/sender-diagnostic.sh','qualification'],head=head,TLS=str(tls),deadline_s=600))
print('Execution:',execution,flush=True)
process=None;first=None;code=2;new=[]
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        review=json.loads((validation/'analysis.json').read_text())
        assert len(review['results'])==2 and all(r['quality']['status']=='passed' and not r['process_diagnostics']['suspect'] for r in review['results'])
        for ref in json.loads((Path(review['run'])/'captured.json').read_text()):assert sha(ref['path'])==ref['sha256']
        subprocess.run(['python3','-B',str(validation/'preflight.py'),str(execution.resolve())],check=True,timeout=120,stdout=stdout,stderr=stderr)
        subprocess.run(['sh','docker/check-release.sh',head],check=True,timeout=20,stdout=stdout,stderr=stderr)
        first=identity();write('identity-before.json',first)
        process=subprocess.Popen(['sh','docker/sender-diagnostic.sh','qualification'],env=dict(os.environ,SERIES_TLS_DIR=str(tls)),stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=process.wait(timeout=600)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            code=124
    except Exception:traceback.print_exc(file=stderr);code=2
    finally:
        new=sorted(str(p) for p in Path('results/verify/diagnostic').glob('sender-diagnostic.*') if p.is_dir() and str(p) not in before)
        write('new-raw-directories.json',new)
        try:
            last=identity();write('identity-after.json',last)
            if first is not None:assert first==last
            if code==0:
                assert len(new)==1
                run=Path(new[0]);assert (run/'exit').read_text().strip()=='0'
                for ref in json.loads((run/'captured.json').read_text()):assert sha(ref['path'])==ref['sha256']
                qualities=[json.loads((run/f'baseline-q{i}/sender-quality.json').read_text()) for i in (1,2,3)]
                assert all(q['status']=='passed' for q in qualities)
                write('quality-summary.json',dict(sender_quality=qualities,status='collection_passed_pending_resource_review'))
        except Exception:traceback.print_exc(file=stderr);code=2
        if code:(execution/'STOP').write_text('Failed/incomplete; preserve all raw, no automatic retry.\n')
(execution/'ended').write_text(stamp()+'\n');(execution/'exit').write_text(str(code)+'\n')
if len(new)==1:(execution/'RAW_RUN').write_text(new[0]+'\n')
print('Execution:',execution);print('Exit:',code)
for p in new:print('RAW_RUN:',p)
if code:print((execution/'stderr.log').read_text()[-2500:])
raise SystemExit(code)
