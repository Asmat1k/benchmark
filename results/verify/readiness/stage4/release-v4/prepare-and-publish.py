import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

base=Path('results/verify/readiness/stage4/release-v4');prior=Path('results/verify/readiness/stage4/release-v3')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
execution=next(base.glob('early-execution.*'));steps=json.loads((execution/'execution.json').read_text());assert len(steps)==2 and all(s['exit']==0 for s in steps)
smoke=Path(steps[0]['new_paths'][0]);timer=next(Path(p) for p in steps[1]['new_paths'] if not p.endswith('-report'))
original=Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json');assert (timer/'context.json').read_bytes()==original.read_bytes()
snapshot=json.loads(Path('build/release-state.json').read_text());inventory=json.loads((base/'source-inventory.json').read_text());old=json.loads((prior/'source-inventory.json').read_text())
assert all(sha(p)==s==snapshot['files'][p] for p,s in inventory.items())
delta=sorted(p for p in inventory if inventory[p]!=old[p]);assert set(delta)=={'docker/measure.sh','docker/browser_bandwidth_test.py'}
images=json.loads(subprocess.check_output(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev'],text=True));expected=json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())
assert [i['Id'] for i in images]==[i['image_id'] for i in expected]
info=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True));assert info['NCPU']==2 and info['MemTotal']==4109484032
(base/'release.json').write_text(json.dumps(dict(release_commit=snapshot['commit'],source_delta_from_v3=delta,source_count=134,image_inputs_unchanged=True,images_reused=expected,environment_original=str(original),environment_actual=str(timer/'context.json'),environment_bytes_equal=True,build='v3 cached build reused after unchanged image dependencies; collector/test are host-mounted; no new build/archive'),indent=2)+'\n')
(base/'environment-preflight.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host_arch=subprocess.check_output(['uname','-m'],text=True),images=expected,vm=dict(cpu=info['NCPU'],memory=info['MemTotal'],arch=info['Architecture'])),indent=2)+'\n')
archive=json.loads((prior/'source-archive-preflight.json').read_text())['archive']
(base/'source-archive-preflight.json').write_text(json.dumps(dict(archive=archive,head=snapshot['commit'],source_count=134,reused_archive_for_identical_images=True),indent=2)+'\n')
(base/'timer-execution').mkdir();(base/'timer-execution/execution.json').write_bytes((execution/'execution.json').read_bytes())
qualification=Path('results/verify/diagnostic/sender-diagnostic.Mbdvg8v6');bindings=json.loads((qualification/'captured.json').read_text());assert all(sha(r['path'])==r['sha256'] for r in bindings)
qual_sources=json.loads((qualification/'sources-before.json').read_text());assert qual_sources==json.loads((qualification/'sources-after.json').read_text())
assert not set(delta)&set(qual_sources) and all(sha(p)==s for p,s in qual_sources.items())
assert 'measure.sh' not in (qualification/'collector.sh').read_text()
accepted=prior/'qualification-Mbdvg8v6-review.json';assert json.loads(accepted.read_text())['status']=='passed'
(base/'qualification-applicability.json').write_text(json.dumps(dict(status='passed',reviewer='Codex, explicit dependency applicability review',current_release=snapshot['commit'],measurement_release=(qualification/'commit').read_text().strip(),source_delta=delta,qualification_dependency_count=len(qual_sources),all_dependencies_unchanged=True,seal_files_verified=len(bindings),accepted_review=dict(path=str(accepted),sha256=sha(accepted)),qualification_raw=str(qualification),current_source_inventory=dict(path=str(base/'source-inventory.json'),sha256=sha(base/'source-inventory.json')),rationale='Neither changed file is invoked or loaded by qualification collector; all13captured executable/config dependencies, images, UDPsender, thresholds and ENV/TLS remain identical. Raw and historical review untouched. Not a claim that all134historical hashes match.'),indent=2)+'\n')
command_prefix=['docker','run','--rm','--network','none','-e','PYTHONDONTWRITEBYTECODE=1','-v',f'{Path.cwd()}:/bench','-w','/bench','wswt-bench-analyzer:dev','python','-B']
deadline=time.monotonic()+120;records=[]
def execute(name,argv,expected_exit=0):
 start=time.monotonic();budget=deadline-start
 if budget<=0:raise SystemExit(124)
 with (base/f'{name}.stdout.log').open('x') as stdout,(base/f'{name}.stderr.log').open('x') as stderr:
  try:code=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=budget).returncode
  except subprocess.TimeoutExpired:code=124
 records.append(dict(name=name,command=argv,elapsed_s=time.monotonic()-start,exit=code));(base/'publication-execution.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,code,flush=True)
 if code!=expected_exit:raise SystemExit(code if code else 1)
env=['--environment',str(original)]
execute('timer-input',command_prefix+['src/analysis/diagnostic_input.py','timer',str(original),str(base/'timer-original-env'),str(timer)])
execute('timer-report',command_prefix+['src/analysis/experiments.py','timer','--kind','real','--input',str(base/'timer-original-env/input.json'),*env,'--output',str(base/'timer-original-env/report.json')])
execute('primary',command_prefix+['docs/readiness/stage4-primary-v4.py',str(smoke),str(base/'timer-original-env/report.json'),str(base/'primary-real-v4')])
(base/'reports').mkdir();mapping={}
for gate in ('build','tls','path','raw','analysis'):
 execute('publish-'+gate,command_prefix+['src/analysis/experiments.py','import-checks','--kind','real','--input',str(base/'primary-real-v4'/gate/'input.json'),*env,'--output',str(base/'reports'/f'{gate}.json')])
 report=base/'reports'/f'{gate}.json';assert json.loads(report.read_text())['status']=='passed';mapping[gate]=str(report)
mapping['timer']=str(base/'timer-original-env/report.json');(base/'REPORT_MAP.json').write_text(json.dumps(mapping,indent=2)+'\n')
execute('verify',command_prefix+['src/analysis/experiments.py','verify','--kind','real','--input',str(base/'REPORT_MAP.json'),*env,'--output',str(base/'verify-pre-bandwidth.json')],2)
v=json.loads((base/'verify-pre-bandwidth.json').read_text());checks={r['id']:r['status'] for r in v['document']['checks']}
assert all(checks[g]=='passed' for g in mapping) and all(checks[g]=='not_run' for g in ('calibration','generator','aa','monitoring')) and not v['final']
print('Six early gates passed; qualification applicability passed; pending new bandwidth collection',flush=True)
