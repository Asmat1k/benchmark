import datetime,hashlib,json
from pathlib import Path
base=Path('results/verify/readiness/calibration-evaluation')
a=json.loads((base/'assessment.json').read_text())
evidence=[dict(path=str(base/'assessment.json'),sha256=hashlib.sha256((base/'assessment.json').read_bytes()).hexdigest())]
items=[
('integrity',True,True,'passed',None),
('environment-stable',True,a['context_equal'] and a['source_before_after_equal'],'passed',None),
('probe-grid',0,sum(r['late_slots'] for r in a['probes'].values()),'failed','100 Hz requires every send within its 10 ms slot'),
('loss-accounting',0,len([r for r in a['probes'].values() if 'directions_error' in r]),'failed','r20p1-before: 102 lost UDP IDs vs 104 aggregate tc drops; background ARP attribution unproven'),
('saturation-rate',True,all(r['passed_9_11'] for r in a['saturation']),'passed',None),
('independent-units',True,False,'inconclusive','Temporal RTT dependence flagged, independently justified units unavailable'),
]
rows=[dict(id=k,mandatory=True,expected=expected,actual=actual,units='predicate or count',tolerance=None,status=status,reason=reason,utc=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),evidence=evidence) for k,expected,actual,status,reason in items]
(base/'checks.json').write_text(json.dumps(dict(schema_version=1,checks=rows),indent=2)+'\n')
