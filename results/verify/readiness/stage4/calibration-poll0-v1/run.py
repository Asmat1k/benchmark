import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import traceback

root=Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
os.chdir(root)
base=Path('results/verify/readiness/stage4/calibration-poll0-v1')
preflight_only=sys.argv[1:]==['--preflight']
assert not sys.argv[1:] or preflight_only
execution=Path(tempfile.mkdtemp(prefix='preflight.' if preflight_only else 'execution.',dir=base))
head='d4cf0f82f330af1cd188febfa5f3757a5cf37799'
tls=root/'build/series-tls-stage2._n__udb0'
envpath=Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json')
inventory=json.loads(Path('results/verify/readiness/stage4/deep-review-v1/source-inventory-new.json').read_text())
expected_images=[r['image_id'] for r in json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())]
tags=['wswt-bench-'+r+':dev' for r in ('server','browser','router','analyzer')]
plan=Path('results/verify/readiness/stage4/release-v4/calibration-fixed-plan.json')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,value):(execution/name).write_text(json.dumps(value,indent=2)+'\n')
def command(args):
    result=subprocess.run(args,input='',text=True,capture_output=True,timeout=20)
    with (execution/'preflight-commands.jsonl').open('a') as log:log.write(json.dumps(dict(argv=args,exit=result.returncode,stdout=result.stdout,stderr=result.stderr))+'\n')
    result.check_returncode()
    return result.stdout

def identity():
    rows=json.loads(command(['docker','image','inspect',*tags]))
    return dict(files={p:sha(p) for p in [*inventory,str(envpath),str(tls/'server/good/cert.pem'),'build/release-state.json',str(base/'run.py'),str(base/'plan.md'),str(plan)]},images=[r['Id'] for r in rows])

(execution/'started').write_text(stamp()+'\n')
(execution/'collector.sh').write_bytes(Path('docker/calibration.sh').read_bytes())
(execution/'collection-plan.expected.json').write_bytes(plan.read_bytes())
write('command.json',dict(argv=['sh','docker/calibration.sh'],head=head,TLS=str(tls),preflight_only=preflight_only,deadline_s=2400))
before={str(p) for p in Path('results/verify/diagnostic').glob('calibration.*') if p.is_dir()}
write('existing-calibration-directories.json',sorted(before))
process=None;start_identity=None;code=2;new=[]
print('Execution:',execution,flush=True)
with (execution/'stdout.log').open('x') as stdout,(execution/'stderr.log').open('x') as stderr:
    try:
        command(['sh','docker/check-release.sh',head])
        assert len(inventory)==134 and all(sha(p)==h for p,h in inventory.items())
        assert json.loads(Path('build/release-state.json').read_text())['commit']==head
        assert sha(envpath)=='231ae4819874cf877f8e2234b4331171309906cb4c259b847c7ff8fc403039da'
        cert=tls/'server/good/cert.pem'
        assert sha(cert)=='ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9'
        assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()=='fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18'
        horizon=ssl.cert_time_to_seconds(ssl._ssl._test_decode_cert(str(cert))['notAfter'])-datetime.datetime.now(datetime.timezone.utc).timestamp()
        assert horizon>=8*86400
        assert 'AC Power' in command(['pmset','-g','batt'])
        assert '"AppleClamshellState" = No' in command(['ioreg','-r','-k','AppleClamshellState','-d','4'])
        assert shutil.disk_usage(root).free>=2*1024**3
        info=json.loads(command(['docker','info','--format','{{json .}}']))
        assert info['NCPU']==2 and info['MemTotal']==4109484032 and info['Architecture']=='aarch64'
        containers=command(['docker','ps','--format','{{.Names}}'])
        assert not any(n.startswith('wswt-') for n in containers.splitlines())
        nets=json.loads(command(['docker','network','inspect',*command(['docker','network','ls','-q']).split()]))
        assert not any(c.get('Subnet') in ('172.28.10.0/24','172.28.20.0/24') for n in nets for c in n.get('IPAM',{}).get('Config',[]) or [])
        assert command(['docker','run','--rm','-i','--network','none','-v',str(root)+':/bench','-w','/bench',tags[-1],'python','-B','src/analysis/series.py','hold']).strip()=='locked'
        start_identity=identity();write('identity-before.json',start_identity)
        assert start_identity['images']==expected_images
        write('preflight.json',dict(status='passed',source_count=134,tls_horizon_days=horizon/86400,free_bytes=shutil.disk_usage(root).free))
        if preflight_only:code=0
        else:
            process=subprocess.Popen(['sh','docker/calibration.sh'],env=dict(os.environ,SERIES_TLS_DIR=str(tls)),stdout=stdout,stderr=stderr,start_new_session=True)
            try:code=process.wait(timeout=2400)
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                code=124
    except Exception:
        traceback.print_exc(file=stderr);code=2
    finally:
        new=sorted(str(p) for p in Path('results/verify/diagnostic').glob('calibration.*') if p.is_dir() and str(p) not in before)
        write('new-calibration-directories.json',new)
        try:
            end_identity=identity();write('identity-after.json',end_identity)
            if start_identity is not None:assert end_identity==start_identity
            if code==0 and not preflight_only:
                assert len(new)==1
                run=Path(new[0]);read=lambda n:json.loads((run/n).read_text())
                assert read('context-before.json')==read('context-after.json')==json.loads(envpath.read_text())
                assert read('sources-before.json')==read('sources-after.json')==inventory
                assert read('collection-plan.json')==json.loads(plan.read_text())
                assert (run/'exit').read_text().strip()=='0'
        except Exception:traceback.print_exc(file=stderr);code=2
        if code:(execution/'STOP').write_text('Collection/preflight/identity failed; preserve raw; no automatic retry.\n')
(execution/'ended').write_text(stamp()+'\n');(execution/'exit').write_text(str(code)+'\n')
if len(new)==1:(execution/'CAL_RUN').write_text(new[0]+'\n')
print('Execution:',execution);print('Exit:',code)
for p in new:print('CAL_RUN:',p)
if code:print((execution/'stderr.log').read_text()[-2500:])
raise SystemExit(code)
