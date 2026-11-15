import tempfile,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,'src/analysis')
from synthetic import make_fixture
from schedule import make_schedule
from raw import read,write,rows
with tempfile.TemporaryDirectory(prefix='d6-review-synthetic-') as t:
 d=Path(t)/'fixture';s=make_schedule('pilot',d.name,1,1)
 s['blocks']=s['blocks'][:1];s['runs']=s['runs'][:2]
 make_fixture(d,schedule=s)
 l=read(d/'ledger.json');l['attempts'][0]['status']='planned';write(d/'ledger.json',l)
 r=s['runs'][0];f=d/'raw'/r['run_id']; p=d/'member.partial';f.rename(p)
 write(p/'page.json',dict(slots=rows(p/'warmup.jsonl')+rows(p/'slots.jsonl'),events=rows(p/'events.jsonl')))
 (p/'SHA256SUMS').unlink()
 for when in ('before','after'):
  write(p/f'qdisc-{when}.json',read(p/f'network_{when}.json')['qdisc'])
 (d/'STOP').write_text('stop fixture')
 for action in ('context','complete'):
  x=subprocess.run([sys.executable,'-B','src/analysis/record.py',action,str(d),'0',str(p)],capture_output=True,text=True)
  print(action,x.returncode,x.stdout,x.stderr[-350:])
 print('published',f.is_dir(),'ledger',read(d/'ledger.json')['attempts'][0]['status'],'no_admission',not (d/'admission.json').exists(),'STOP', (d/'STOP').exists())
