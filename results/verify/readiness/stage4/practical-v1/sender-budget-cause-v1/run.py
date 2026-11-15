import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import traceback

ROOT=Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
os.chdir(ROOT)
BASE=Path('results/verify/readiness/stage4/practical-v1/sender-budget-cause-v1')
if list(BASE.glob('execution.*/network-started')):
    raise SystemExit('One prospective diagnostic already started; no automatic repeat.')
execution=Path(tempfile.mkdtemp(prefix='execution.',dir=BASE))
start=time.monotonic();deadline=start+240
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda name,value:(execution/name).write_text(json.dumps(value,indent=2)+'\n')
(execution/'started').write_text(stamp()+'\n')
inv=json.loads(Path('results/verify/readiness/stage4/practical-v1/release-v2/source-inventory.json').read_text())
files=[*inv,*(str(BASE/name) for name in ('run.py','plan.md','probe.py','collect.sh','method-review.md')),
       'docs/readiness/practical-preflight.py','build/release-state.json',
       'build/series-tls-stage2._n__udb0/server/good/cert.pem',
       'results/verify/diagnostic/timer-timer.JHhehRVV/context.json']
identity=lambda:{p:sha(p) for p in files}
before=identity();write('identity-before.json',before)
existing={str(p) for p in Path('results/verify/diagnostic').glob('sender-budget-cause.*') if p.is_dir()}
write('command.json',dict(argv=['sh',str(BASE/'collect.sh')],total_cap_s=240,network_cap_s=210,diagnostic_only=True))
code=2;process=None
def interrupted(signum,frame):raise KeyboardInterrupt('Diagnostic interrupted')
signal.signal(signal.SIGTERM,interrupted)
print('Execution:',execution,flush=True)
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        spec=importlib.util.spec_from_file_location('preflight','docs/readiness/practical-preflight.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        preflight=module.check();write('preflight.json',dict(path=str(preflight)))
        assert all(sha(p)==h for p,h in inv.items())
        assert identity()==before
        if deadline-time.monotonic()<145:raise TimeoutError('Insufficient setup/load/cleanup reserve before network')
        (execution/'network-started').write_text(stamp()+'\n')
        process=subprocess.Popen(['sh',str(BASE/'collect.sh')],env=dict(os.environ,SERIES_TLS_DIR=str(ROOT/'build/series-tls-stage2._n__udb0')),stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=process.wait(timeout=min(210,deadline-time.monotonic()-20))
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=min(15,max(1,deadline-time.monotonic()-4)))
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            code=124
    except BaseException:
        traceback.print_exc(file=stderr);code=2
    finally:
        new=sorted(str(p) for p in Path('results/verify/diagnostic').glob('sender-budget-cause.*') if p.is_dir() and str(p) not in existing)
        write('new-directories.json',new)
        if len(new)==1:
            run=Path(new[0]);(execution/'RUN').write_text(str(run)+'\n')
            try:
                final=[dict(path=str(p),sha256=sha(p)) for p in sorted(run.rglob('*')) if p.is_file()]
                write('final-captured.json',final)
                if code==0:
                    assert (run/'exit').read_text().strip()=='0'
                    read=lambda name:json.loads((run/name).read_text())
                    assert read('context-before.json')==read('context-after.json')==json.loads(Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json').read_text())
                    assert read('sources-before.json')==read('sources-after.json')==inv
                    for entry in read('captured.json'):assert sha(entry['path'])==entry['sha256']
                    for tool,copy in [('probe.py','diagnostic-probe.py'),('collect.sh','diagnostic-collector.sh'),('plan.md','diagnostic-plan.md')]:assert sha(BASE/tool)==sha(run/copy)
                project='wswt-'+run.name.lower().replace('.','-')
                leftovers=subprocess.run(['docker','ps','-a','--filter','name='+project,'--format','{{.Names}}'],capture_output=True,text=True,timeout=max(1,min(3,deadline-time.monotonic())))
                write('cleanup-observation.json',dict(exit=leftovers.returncode,stdout=leftovers.stdout,stderr=leftovers.stderr))
                assert leftovers.returncode==0 and not leftovers.stdout.strip()
            except BaseException:traceback.print_exc(file=stderr);code=2
        elif code==0:code=2
        after=identity();write('identity-after.json',after)
        if after!=before:code=2
        if code:(execution/'STOP').write_text('Diagnostic/preflight/identity incomplete; preserve all outputs, no automatic repeat.\n')
        write('result.json',dict(exit=code,scope='diagnostic only, not qualification',elapsed_s=time.monotonic()-start))
        (execution/'ended').write_text(stamp()+'\n');(execution/'exit').write_text(str(code)+'\n')
print('Execution:',execution,'exit:',code,flush=True)
raise SystemExit(code)
