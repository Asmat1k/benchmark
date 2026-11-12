import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,'src/analysis')
from raw import read,digest
from admission import validate_gate,sources
root=Path('build/d5-r7-synthetic/fixture-9l51pfgl')
assert read(root/'SYNTHETIC.json')['kind']=='synthetic'
prior=read(Path('results/verify/acceptance/development/recheck/source-hashes.json'))
print('prior source manifest type',type(prior).__name__,flush=True)
print('source manifest',json.dumps(prior)[:200],flush=True)
manifest={str(p):digest(p) for p in root.rglob('*') if p.is_file()}
Path('results/verify/integration/development/retained-inventory.json').write_text(json.dumps(manifest,indent=2))
for phase in ('aa','monitoring','pilot','power'):
 t=time.monotonic();p=root/(phase+'-current-report.json');report=read(p)
 assert report['kind']=='synthetic'
 assert report['source_hashes']==sources(),phase
 validate_gate(report,recalculate=False)
 print(phase,'typed dependency graph integrity passed',round(time.monotonic()-t,3),'seconds',digest(p),flush=True)
print('retained inventory',len(manifest),'files; provenance D5 handoff/recheck and independent review03; no scientific recalculation')
