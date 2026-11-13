import hashlib,json,math,sys
from pathlib import Path
import numpy as np
from scipy.stats import binom
sys.path[:0]=['src/analysis','docker']
from raw import read
from admission import sources
from acceptance import probe_records, dependence, exact_binomial
from calibration_report import directions, rate
root=Path('results/verify/diagnostic/calibration.ZQRTHB2H')
out=Path('results/verify/readiness/calibration-evaluation')
result=dict(head=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),collection=root.name)
seal=read(root/'captured.json')
result['sealed_files']=len(seal)
result['hash_errors']=[r['path'] for r in seal if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()!=r['sha256']]
original=read(root/'sources-before.json')
result['source_before_after_equal']=original==read(root/'sources-after.json')
result['source_current_equal']=original==sources()
result['context_equal']=read(root/'context-before.json')==read(root/'context-after.json')
result['probes']={}
for directory in sorted(root.iterdir()):
    if not directory.is_dir() or not (directory/'probe.json').exists() or directory.name.startswith('saturation'):
        continue
    probe=read(directory/'probe.json')
    timing=np.array([r['t_send_ms']-r['t_plan_ms'] for r in probe['sent_records']])
    rtt=sorted(probe['rtt_ms'])
    n=len(rtt)
    candidates=np.arange((n+1)//2+1)
    k=int(candidates[2*binom.cdf(candidates-1,n,.5)<=.025][-1])
    summary=dict(sent=len(probe['sent_records']),received=n,median_ms=float(np.median(rtt)),
                 rank_CI975=[rtt[k-1],rtt[n-k]] if k else None,
                 late_slots=int(sum(timing>=10)),negative_lags=int(sum(timing<0)),max_send_lag_ms=float(max(timing)),
                 p99_send_lag_ms=float(np.sort(timing)[9899]),dependence=dependence(probe['rtt_ms']))
    try:
        probe_records(probe)
        summary['probe_grid_valid']=True
    except ValueError as exc:
        summary['probe_grid_valid']=False
        summary['probe_grid_error']=str(exc)
    try:
        summary['directions']=[dict(direction=r['direction'],count=len(r['entered_ids']),drops=len(r['dropped_ids']),
                                     CI99=exact_binomial(len(r['dropped_ids']),len(r['entered_ids']))) for r in directions(directory,probe)]
    except ValueError as exc:
        summary['directions_error']=str(exc)
    result['probes'][directory.name]=summary
result['shifts']={}
for profile in ('r20p0','r20p1','r80p0','r80p1'):
    ci=result['probes'][profile+'-latency']['rank_CI975']
    target=20 if profile.startswith('r20') else 80
    result['shifts'][profile]={}
    for when in ('before','after'):
        baseline=result['probes']['baseline-'+when]['rank_CI975']
        shift=[ci[0]-baseline[1],ci[1]-baseline[0]]
        result['shifts'][profile][when]=dict(CI=shift,within_tolerance=target-2<=shift[0]<=shift[1]<=target+2)
result['saturation']=[]
for loss in (0,1):
    for direction in ('forward','reverse'):
        folder=root/f'saturation-{loss}-{direction}'
        sample=rate(folder,direction,loss/100)
        sample['mbit_s']=sample['forwarded_bytes']*8/sample['duration_s']/1e6
        sample['passed_9_11']=9<=sample['mbit_s']<=11
        result['saturation'].append(sample)
(out/'assessment.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print('integrity',{k:v for k,v in result.items() if k not in ('probes','shifts','saturation')})
for name,row in result['probes'].items():
    print(name,'median',round(row['median_ms'],4),'late',row['late_slots'],'lag1',round(row['dependence']['lag1'],4),'directions',row.get('directions_error',[(r['count'],r['drops']) for r in row.get('directions',[])]))
print('shifts',result['shifts'])
print('saturation',[(r['direction'],r['loss'],r['mbit_s']) for r in result['saturation']])
