import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

base=Path('results/verify/readiness/stage4/deep-review-v1');rows=json.loads((base/'wake-abba/analysis.json').read_text())['results']
labels=['Wait A1','Poll0 B1','Poll0 B2','Wait A2'];colors=['#75889a','#16876e','#16876e','#75889a']
fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
for row,label,color in zip(rows,labels,colors):axes[0,0].plot(range(100),row['phase']['median_profile'],label=label,color=color,alpha=.8)
axes[0,0].set(xlabel='Slot phase within 1 second',ylabel='Median RTT, ms',title='RTT phase structure (baseline only)');axes[0,0].legend(ncol=2,fontsize=8)
values=[r['quality']['metrics']['lag_ms']['p99'] for r in rows]
axes[0,1].bar(labels,values,color=colors);axes[0,1].set(yscale='log',ylabel='p99 sender lag, ms',title='Sender timing')
for i,v in enumerate(values):axes[0,1].text(i,v*1.1,f'{v:.3f}',ha='center',fontsize=9)
axes[1,0].bar(labels,[r['rank_correlations']['1000'] for r in rows],color=colors);axes[1,0].set(ylabel='Rank autocorrelation at 10 s',title='Diagnostic dependence; no gate modification')
axes[1,1].bar(labels,[r['cpu']['sender_core_pct'] for r in rows],color=colors);axes[1,1].set(ylim=(0,110),ylabel='CPU, % of one virtual core',title='Explicit CPU tradeoff')
fig.suptitle('Fixed short ABBA experiment: 5,000 packets per run\nImprovement shown; rare-pause reliability and full calibration are not established',fontsize=12)
fig.savefig(base/'comparison.png',dpi=170);plt.close(fig)
