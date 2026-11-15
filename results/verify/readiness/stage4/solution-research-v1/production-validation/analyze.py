import hashlib,json,os,sys
from pathlib import Path
import numpy as np
sys.path[:0]=['docker','src/analysis']
from calibration_report import directions
from calibration_blocks import process_diagnostics
from acceptance import exact_binomial
from sender_quality import evaluate
run=Path(sys.argv[1]);output=Path(sys.argv[2]);seal=json.loads((run/'captured.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(row['path'])==row['sha256'] for row in seal)
assert (run/'exit').read_text().strip()=='0'
assert json.loads((run/'sources-before.json').read_text())==json.loads((run/'sources-after.json').read_text())
results=[]
for name in ('r80p0-check','r80p1-check'):
 d=run/name;p=json.loads((d/'probe.json').read_text());assert p['sent']==10000 and p['frame_bytes']==256 and p['frequency_hz']==100
 assert p['sender_cpu_after']==[0]
 quality=evaluate(p['sent_records'],10000);flows=directions(d,p)
 assert len({r['id'] for r in p['reply_records']})==len(p['reply_records'])
 for role in ('browser','server'):assert '0 packets dropped by kernel' in (d/f'{role}.log').read_text()
 values=np.full(10000,np.nan)
 for row in p['reply_records']:values[row['id']]=row['rtt_ms']
 loss=[dict(direction=f['direction'],count=len(f['entered_ids']),drops=len(f['dropped_ids']),interval=exact_binomial(len(f['dropped_ids']),len(f['entered_ids']),1-.01/8)) for f in flows]
 sender_cpu=[]
 for when in ('before','after'):sender_cpu.append(int(next(l.split()[1] for l in (d/f'sender-cpu-{when}.txt').read_text().splitlines() if l.startswith('usage_usec '))))
 t0,t1=[float((d/f'cpu-{when}.txt').read_text().splitlines()[0].split()[0]) for when in ('before','after')]
 results.append(dict(name=name,quality=quality,replies=len(p['reply_records']),rtt_quantiles=np.nanquantile(values,[.5,.95,.99,1]).tolist(),process_diagnostics=process_diagnostics(values),loss=loss,sender_core_pct=100*(sender_cpu[1]-sender_cpu[0])/1e6/(t1-t0)))
result=dict(scope='fixed two-profile similar diagnostic; not full calibration acceptance',run=str(run),commit=(run/'commit').read_text().strip(),sealed_files=len(seal),results=results)
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for r in results:print(r['name'],r['quality']['status'],r['quality']['metrics']['lag_ms'],r['rtt_quantiles'],'process_suspect',r['process_diagnostics']['suspect'],'cpu',r['sender_core_pct'],'loss',r['loss'])
