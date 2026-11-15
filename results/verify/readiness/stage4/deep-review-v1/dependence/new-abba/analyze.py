import hashlib,json,struct
from pathlib import Path
import numpy as np
from scipy.stats import rankdata,spearmanr

root=Path('results/verify/diagnostic/capture-abba.MaDtfSFh');out=Path('results/verify/readiness/stage4/deep-review-v1/dependence/new-abba')
source=Path('results/verify/readiness/stage4/deep-review-v1/dependence/analyze.py').read_text();ns=dict(np=np,struct=struct,LAGS=(500,1000,2000));exec(source[source.index('def capture('):source.index('started = ')],ns);capture=ns['capture'];correlations=ns['correlations']
seal=json.loads((root/'captured.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();assert all(sha(r['path'])==r['sha256'] for r in seal)
results=[]
for label in ('buffered-A1','immediate-B1','immediate-B2','buffered-A2'):
 d=root/label;p=json.loads((d/'probe.json').read_text());replies={r['id']:r['rtt_ms'] for r in p['reply_records']};assert set(replies)==set(range(5000))
 fw=capture(d/'browser.pcap');rv=capture(d/'server.pcap');assert set(fw)==set(rv)==set(replies)
 rtt=np.array([replies[i] for i in range(5000)]);network=np.array([(rv[i]-fw[i])/1000 for i in range(5000)]);times=np.array([fw[i] for i in range(5000)]);phase=(times%1000000//10000).astype(int)
 components={}
 for name,v in [('rtt',rtt),('network_span',network),('remaining_rtt',rtt-network)]:
  bycycle=v.reshape(50,100);first=np.median(bycycle[:25],axis=0);second=np.median(bycycle[25:],axis=0);fold=np.median(bycycle,axis=0)
  absolute=np.array([np.median(v[phase==i]) if np.any(phase==i) else np.nan for i in range(100)])
  rank=rankdata(v);rankfold=rank.reshape(50,100).mean(axis=0)
  centered=fold-fold.mean();spectral=np.abs(np.fft.rfft(centered))**2;spectral[0]=0
  peaks=np.argsort(fold)[-6:][::-1];abspeaks=np.argsort(np.nan_to_num(absolute,nan=-1))[-6:][::-1]
  crossfit=v-np.concatenate([np.tile(second,25),np.tile(first,25)])
  components[name]=dict(median=float(np.median(v)),p99=float(np.quantile(v,.99)),acf=correlations(v).tolist(),rank_acf=correlations(rank).tolist(),phase_rank_explained_variance=float(np.var(rankfold)/np.var(rank)),half_phase_correlation=float(spearmanr(first,second).statistic),phase_median_range=[float(fold.min()),float(fold.max())],phase_medians=fold.tolist(),absolute_phase_medians=absolute.tolist(),strongest_phase_bins=[dict(slot_phase=int(i),median_ms=float(fold[i])) for i in peaks],strongest_epoch_bins=[dict(phase_ms=int(i)*10,median_ms=float(absolute[i])) for i in abspeaks],spectral_peak_hz=[dict(hz=int(i),power=float(spectral[i])) for i in np.argsort(spectral)[-6:][::-1]],crossfit_phase_subtraction_acf_diagnostic=correlations(crossfit).tolist())
 results.append(dict(name=label,first_packet_epoch_us=fw[0],first_packet_epoch_phase_ms=fw[0]%1000000/1000,components=components,inputs=[dict(path=str(d/name),sha256=sha(d/name)) for name in ('probe.json','browser.pcap','server.pcap')]))
result=dict(scope='Fixed existing ABBA raw decomposition; descriptive only',sealed_files=len(seal),results=results,limitations=['Kernel packet timestamps are not capture flush times','Changing buffered/immediate delivery did not identify a causal driver; global activity and guest wakeup/timer paths remain candidates','5000samples=50seconds, cannot rule out rare129ms episodes or qualify calibration','No phase subtraction/rank data replaces primary acceptance'])
with (out/'analysis.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for r in results:
 print(r['name'],'firstphase',r['first_packet_epoch_phase_ms'])
 for k,c in r['components'].items():print(k,{key:c[key] for key in ('median','p99','acf','phase_rank_explained_variance','half_phase_correlation','strongest_epoch_bins','spectral_peak_hz')})
