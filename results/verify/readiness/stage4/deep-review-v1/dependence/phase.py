import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr

sys.path.insert(0,'results/verify/readiness/stage4/deep-review-v1/dependence')
source = Path('results/verify/readiness/stage4/deep-review-v1/dependence/analyze.py').read_text()
namespace = {}
exec(source[source.index('def capture('):source.index('started = ')], namespace)
capture = namespace['capture']
correlations = namespace['correlations']
namespace.update(np=np,LAGS=(500,1000,2000),struct=__import__('struct'))
root=Path('results/verify/diagnostic/calibration.lShojabe')
results=[]
for label in ('baseline-before','r20p0-latency'):
 d=root/label
 p=json.loads((d/'probe.json').read_text());rtts={r['id']:r['rtt_ms'] for r in p['reply_records']}
 rtt=np.array([rtts[i] for i in range(10000)]);fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap')
 network=np.array([(rv[i]-fw[i])/1000 for i in range(10000)])
 rows={}
 for name,values in [('rtt',rtt),('router_round_span',network),('residual',rtt-network)]:
  matrix=values.reshape(100,100)
  first=np.median(matrix[:50],axis=0);second=np.median(matrix[50:],axis=0)
  full=np.median(matrix,axis=0)
  ranked=rankdata(values).reshape(100,100)
  rank_profile=ranked.mean(axis=0)
  crossfitted=values-np.concatenate([np.tile(second,50),np.tile(first,50)])
  rows[name]=dict(first_half_medians=first.tolist(),second_half_medians=second.tolist(),phase_medians=full.tolist(),
   half_profile_spearman=float(spearmanr(first,second).statistic),
   phase_median_range=[float(full.min()),float(full.max())],
   mean_rank_phase_explained_variance=float(np.var(rank_profile)/np.var(ranked)),
   raw_acf=correlations(values).tolist(),crossfitted_phase_subtracted_acf_diagnostic=correlations(crossfitted).tolist(),
   largest_phase_medians=[dict(phase=int(i),median=float(full[i])) for i in np.argsort(full)[-10:][::-1]])
 results.append(dict(name=label,components=rows))
output=Path('results/verify/readiness/stage4/deep-review-v1/dependence/phase.json')
with output.open('x') as f:json.dump(dict(diagnostic_only=True,period_slots=100,results=results,limitations=['Period100chosen after inspection; exploratory only','Phase subtraction is a diagnostic operation and never changes raw or acceptance','Common process or timer activity is not identified by phase profile alone']),f,indent=2);f.write('\n')
for r in results:
 print(r['name'])
 for k,v in r['components'].items():print(k,{key:v[key] for key in ('half_profile_spearman','phase_median_range','mean_rank_phase_explained_variance','raw_acf','crossfitted_phase_subtracted_acf_diagnostic','largest_phase_medians')})
