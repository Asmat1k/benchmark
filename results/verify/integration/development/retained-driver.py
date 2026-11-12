import sys,time,json
from pathlib import Path
sys.path.insert(0,'src/analysis')
from raw import read,digest
from admission import check_integrity,evidence_closure,sources,aggregate
root=Path('build/d5-r7-synthetic/fixture-9l51pfgl')
assert read(root/'SYNTHETIC.json')['kind']=='synthetic'
for phase in ('aa','monitoring','pilot','power'):
 t=time.monotonic();p=root/(phase+'-current-report.json');report=read(p)
 assert report['kind']=='synthetic'
 check_integrity(report['integrity'])
 canonical=evidence_closure([Path(v['path']) for v in report['evidence']]+[Path(report['environment']['path'])])
 assert canonical==report['integrity'],phase
 print(phase,'saved report and canonical typed dependency graph integrity passed',round(time.monotonic()-t,3),'seconds',digest(p),flush=True)
 if report['source_hashes']!=sources():print(phase,'historical source inventory; NOT current admission; current aggregate rejects stale report',flush=True)
print('Historical R7 scientific outcomes reused from D5 independent review03, unchanged algorithms; current guards separately exercised by locked-suite. No source hash or evidence rewritten.')
