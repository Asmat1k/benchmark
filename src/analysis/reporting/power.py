import numpy as np
from scipy.stats import binom

from admission.acceptance import exact_binomial
from measurement.raw import require
from execution.schedule import PROFILES, seeds


def simulate(pilot, identity, replicates=10000, candidates=(20,30,40,60)):
    require(set(pilot) == set(PROFILES) and replicates == 10000, 'power protocol')
    require(tuple(candidates) == (20,30,40,60), 'fixed candidate sizes')
    residuals = []
    for profile in PROFILES:
        values = np.asarray(pilot[profile], dtype=float)
        require(len(values) >= 5 and np.isfinite(values).all(), 'pilot requires >=5 complete blocks per profile')
        residuals.append(values-np.median(values))
    results = []
    for n in candidates:
        for shift in (0,-5,5):
            for scenario in ('iid','ties','dependence','rare_failures'):
                rng = seeds('pilot',identity,7,n,(0,-5,5).index(shift),('iid','ties','dependence','rare_failures').index(scenario))
                state = rng.bit_generator.state
                arrays, widths, interval_diagnostics = [], [], []
                for values in residuals:
                    indices = rng.integers(0,len(values),size=(replicates,n if scenario != 'dependence' else (n+1)//2))
                    sample = values[indices]
                    if scenario == 'dependence': sample = np.repeat(sample,2,axis=1)[:,:n]
                    sample = sample+shift
                    if scenario == 'ties': sample = np.round(sample/5)*5
                    if scenario == 'rare_failures':
                        sample = sample.copy()
                        sample[rng.random(sample.shape)<.01] += 100
                    positive,negative = (sample>0).sum(axis=1),(sample<0).sum(axis=1)
                    arrays.append(np.minimum(1,2*np.minimum(binom.sf(positive-1,n,.5),binom.sf(negative-1,n,.5))))
                    ordered = np.sort(sample,axis=1)
                    diagnostics = {}
                    for alpha in (.05,.0125):
                        k = max(k for k in range((n+1)//2+1) if 2*binom.cdf(k-1,n,.5)<=alpha)
                        span = ordered[:,n-k]-ordered[:,k-1] if k else np.full(replicates,np.inf)
                        diagnostics[str(1-alpha)] = dict(ranks=[k,n-k+1],
                            width_quantiles=np.quantile(span,[.025,.5,.975]).tolist(),
                            coverage=float(np.mean((ordered[:,k-1]<=shift)&(ordered[:,n-k]>=shift))) if k else 1.)
                    interval_diagnostics.append(diagnostics)
                    widths.append(diagnostics['0.9875']['width_quantiles'])
                raw = np.stack(arrays,axis=1)
                order = np.argsort(raw,axis=1,kind='stable')
                sorted_p = np.take_along_axis(raw,order,axis=1)
                adjusted = np.minimum(1,np.maximum.accumulate(sorted_p*np.array([4,3,2,1]),axis=1))
                rejected = np.empty_like(adjusted,dtype=bool)
                np.put_along_axis(rejected,order,adjusted<.05,axis=1)
                counts = rejected.sum(axis=0)
                results.append(dict(n=n,shift_ms=shift,scenario=scenario,replicates=replicates,
                    profiles={p:dict(power=float(counts[i]/replicates),MC_CI99=exact_binomial(int(counts[i]),replicates),
                                     CI=interval_diagnostics[i]) for i,p in enumerate(PROFILES)},
                    familywise_rejection=float(np.mean(rejected.any(axis=1))),state_before=state))
    return dict(status='passed',method='centered paired-block pilot residual resampling; independent profiles; sign full n + Holm4',
                limitations=['small pilot cannot establish 80% power','sensitivity models are assumptions, not estimated mechanisms',
                             'rare failures modeled as +100 ms with probability .01; dependence repeats pairs; ties round to 5 ms'],
                pilot_residuals={p:v.tolist() for p,v in zip(PROFILES,residuals)},results=results)
