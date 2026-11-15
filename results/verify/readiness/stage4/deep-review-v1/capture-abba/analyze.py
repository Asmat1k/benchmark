import hashlib,json,os,sys
from pathlib import Path
import numpy as np
from scipy.stats import rankdata,spearmanr

sys.path[:0]=['docker','src/analysis']
from calibration_report import directions
from calibration_blocks import process_diagnostics
from sender_quality import evaluate
run=Path(sys.argv[1]);output=Path(sys.argv[2]);seal=json.loads((run/'captured.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(r['path'])==r['sha256'] for r in seal)
assert {r['path'] for r in seal}=={str(p) for p in run.rglob('*') if p.is_file() and p.name!='captured.json'}
assert (run/'exit').read_text().strip()=='0'
assert json.loads((run/'sources-before.json').read_text())==json.loads((run/'sources-after.json').read_text())
def cpu(path):
 lines=path.read_text().splitlines();uptime=float(lines[0].split()[0]);usage=int(next(l.split()[1] for l in lines if l.startswith('usage_usec ')))
 process=[l.split(') ',1)[1].split() for l in lines if '(tcpdump)' in l]
 assert len(process)==2
 ticks=sum(int(r[11])+int(r[12]) for r in process)
 return uptime,usage,ticks
results=[]
for name in ('buffered-A1','immediate-B1','immediate-B2','buffered-A2'):
 d=run/name;probe=json.loads((d/'probe.json').read_text());assert probe['sent']==5000 and len(probe['reply_records'])==5000 and probe['frame_bytes']==256
 flows=directions(d,probe);assert all(len(f['entered_ids'])==5000 and not f['dropped_ids'] for f in flows)
 for role in ('browser','server'):assert '0 packets dropped by kernel' in (d/f'{role}.log').read_text()
 values=np.full(5000,np.nan)
 for reply in probe['reply_records']:values[reply['id']]=reply['rtt_ms']
 assert np.isfinite(values).all()
 ranks=rankdata(values);centered=ranks-ranks.mean();den=centered@centered
 rank_correlations={str(lag):float(centered[:-lag]@centered[lag:]/den) for lag in (100,500,1000,2000)}
 matrix=values.reshape(50,100);medians=np.median(matrix,axis=0)
 split=float(spearmanr(np.median(matrix[:25],axis=0),np.median(matrix[25:],axis=0)).statistic)
 t0,c0,p0=cpu(d/'cpu-before.txt');t1,c1,p1=cpu(d/'cpu-after.txt');duration=t1-t0
 result=dict(name=name,option=(d/'capture-option').read_text().strip(),quality=evaluate(probe['sent_records'],5000),rtt_quantiles=np.quantile(values,[.5,.95,.99,1]).tolist(),diagnostics=process_diagnostics(values),rank_correlations=rank_correlations,phase=dict(cross_half_rank_correlation=split,median_profile=medians.tolist(),median_profile_range_ms=float(np.ptp(medians))),cpu=dict(duration_s=duration,router_core_pct=100*(c1-c0)/1e6/duration,tcpdump_core_pct=100*(p1-p0)/os.sysconf('SC_CLK_TCK')/duration,clock_ticks_per_s=os.sysconf('SC_CLK_TCK')))
 results.append(result)
result=dict(run=str(run),sealed_files=len(seal),scope='fixed short ABBA diagnostic; no acceptance/reliability claim',results=results)
with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for row in results:print(row['name'],'lag',row['quality']['metrics']['lag_ms'],'rtt',row['rtt_quantiles'],'rho',row['diagnostics']['rtt']['long_lag'],'rank',row['rank_correlations'],'phase',row['phase']['cross_half_rank_correlation'],'cpu',row['cpu'])
