import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
source=Path.cwd()
with tempfile.TemporaryDirectory(prefix='d6-shell-',dir=source/'build') as temp:
 root=Path(temp);(root/'docker').mkdir();(root/'bin').mkdir();(root/'tmp').mkdir()
 for name in ('experiment.sh','controller-client.sh'):shutil.copyfile(source/'docker'/name,root/'docker'/name)
 (root/'docker/release-state.sh').write_text('exit 0\n')
 (root/'docker/measure.sh').write_text('echo reached > "$D6_MARKER"\nexit "$D6_CODE"\n')
 stub=root/'bin/docker'
 stub.write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
Path(os.environ['D6_PID']).write_text(str(os.getpid()))
if os.environ['D6_MODE']=='boot':sys.exit(17)
print(json.dumps(dict(value='ready',commit='a'*40)),flush=True)
for line in sys.stdin:
 if os.environ['D6_MODE']=='request':print(json.dumps(dict(code=2,error='offline deliberate failure')),flush=True)
 else:print(json.dumps(dict(code=0,value='0')),flush=True)
''');stub.chmod(0o755)
 for mode,code in [('boot',1),('request',1),('measure',1),('measure',3)]:
  marker=root/'network';marker.unlink(missing_ok=True);pid=root/'pid'
  env=dict(os.environ,PATH=str(root/'bin')+os.pathsep+os.environ['PATH'],TMPDIR=str(root/'tmp'),SERIES_TLS_DIR=str(root/'tls'),D6_MODE=mode,D6_CODE=str(code),D6_MARKER=str(marker),D6_PID=str(pid))
  t=time.monotonic();p=subprocess.run(['sh','docker/experiment.sh','results/verify/raw/offline-fixture','yes'],cwd=root,env=env,capture_output=True,text=True,timeout=20)
  assert p.returncode==2 if mode in ('boot','request') or code==3 else p.returncode==1,(mode,p.returncode,p.stderr)
  assert not list((root/'tmp').iterdir()),mode
  try:os.kill(int(pid.read_text()),0)
  except ProcessLookupError:pass
  else:raise AssertionError('controller still alive')
  assert marker.exists()==(mode=='measure')
  print(json.dumps(dict(mode=mode,measure_exit=code,exit=p.returncode,seconds=time.monotonic()-t,controller_reaped=True,fifo_removed=True,network_marker=marker.exists())))
print('Actual experiment.sh cleanup passed; only external Docker/release/measurement dependencies stubbed in isolated temporary copy; no validator patched and no real series.')
