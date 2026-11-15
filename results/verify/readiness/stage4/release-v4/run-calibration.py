import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import traceback

root=Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
os.chdir(root)
base=Path('results/verify/readiness/stage4/release-v4')
execution=Path(os.path.relpath(tempfile.mkdtemp(prefix='calibration-execution.',dir=base)))
env=dict(os.environ,SERIES_TLS_DIR=str(root/'build/series-tls-stage2._n__udb0'))
command=['sh','docker/calibration.sh']
head='494e1a99bf9c92bd2a26af7dce6a8752af23d448'
calibration_root=Path('results/verify/diagnostic')
before={str(p) for p in calibration_root.glob('calibration.*') if p.is_dir()}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):
    (execution/name).write_text(json.dumps(value,indent=2)+'\n')
def identity():
    files=list(json.loads((base/'source-inventory.json').read_text()))+['results/verify/diagnostic/timer-timer.2ST8NYBU/context.json','build/series-tls-stage2._n__udb0/server/good/cert.pem','build/release-state.json',str(base/'browser-bandwidth-v4-raw-review.json'),str(base/'calibration-fixed-plan.json')]
    rows=json.loads(subprocess.check_output(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev'],text=True))
    return dict(files={p:sha(p) for p in files},images=[r['Id'] for r in rows])
(execution/'started').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
(execution/'collector.sh').write_bytes(Path('docker/calibration.sh').read_bytes())
write('command.json',dict(command=command,release_commit=head,TLS=env['SERIES_TLS_DIR'],BW_RUN='results/verify/diagnostic/browser-bandwidth-v4.9r51339s'))
(execution/'collection-plan.expected.json').write_bytes((base/'calibration-fixed-plan.json').read_bytes())
write('existing-calibration-directories.json',sorted(before))
print('Execution:',execution,flush=True)
process=None;code=2;start_identity=None
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        subprocess.run(['sh','docker/check-release.sh',head],check=True,stdout=stdout,stderr=stderr)
        inventory=json.loads((base/'source-inventory.json').read_text())
        assert len(inventory)==134 and all(sha(p)==s for p,s in inventory.items())
        assert json.loads((base/'qualification-applicability.json').read_text())['status']=='passed'
        review=json.loads((base/'browser-bandwidth-v4-raw-review.json').read_text())
        assert review['status']=='raw_collection_accepted' and review['release_commit']==head
        for ref in review['evidence']+[review['environment']]:assert sha(ref['path'])==ref['sha256']
        start_identity=identity();write('identity-before.json',start_identity)
        expected=json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())
        assert start_identity['images']==[r['image_id'] for r in expected]
        process=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        code=process.wait()
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
        code=130
    except Exception:
        traceback.print_exc(file=stderr);code=2
    finally:
        new_paths=sorted(str(p) for p in calibration_root.glob('calibration.*') if p.is_dir() and str(p) not in before)
        write('new-calibration-directories.json',new_paths)
        try:
            end_identity=identity();write('identity-after.json',end_identity)
            if start_identity is not None and end_identity!=start_identity:
                stderr.write('Identity changed during collection\n');code=2
            if code==0:
                assert len(new_paths)==1
                run=Path(new_paths[0]);context=json.loads(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json').read_text())
                assert json.loads((run/'context-before.json').read_text())==json.loads((run/'context-after.json').read_text())==context
                assert json.loads((run/'sources-before.json').read_text())==json.loads((run/'sources-after.json').read_text())==inventory
                assert json.loads((run/'collection-plan.json').read_text())==json.loads((base/'calibration-fixed-plan.json').read_text())
                assert (run/'exit').read_text().strip()=='0'
        except Exception:
            traceback.print_exc(file=stderr);code=2
        if code:
            (execution/'STOP').write_text('Collection failed or identity invariant failed; preserve all raw; no automatic retry.\n')
(execution/'ended').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
(execution/'exit').write_text(str(code)+'\n')
if len(new_paths)==1:
    (execution/'CAL_RUN').write_text(new_paths[0]+'\n')
print('Execution:',execution)
for path in new_paths:print('CAL_RUN:',path)
print('Exit:',code)
raise SystemExit(code)
