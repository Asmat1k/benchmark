import hashlib
import json
from pathlib import Path
import struct
import time

import numpy as np
from scipy.stats import rankdata

ROOT = Path('results/verify/diagnostic/calibration.lShojabe')
OUTPUT = Path('results/verify/readiness/stage4/deep-review-v1/dependence')
LAGS = (500, 1000, 2000)
REPLICATES = 1024
SEED = 20261114


def capture(path):
    data = path.read_bytes()
    endian = '<' if data[:4] == b'\xd4\xc3\xb2\xa1' else '>'
    position, result = 24, {}
    while position < len(data):
        sec, usec, count, length = struct.unpack_from(endian+'IIII', data, position)
        position += 16
        frame = data[position:position+count]
        position += count
        if frame[12:14] != b'\x08\x00' or frame[23] != 17:
            continue
        ip = frame[14:]
        udp = ip[(ip[0] & 15)*4:]
        result[int.from_bytes(udp[8:12], 'big')] = sec*1000000+usec
    return result


def correlations(values):
    centered = values-values.mean()
    variance = centered@centered
    return np.array([centered[:-lag]@centered[lag:]/variance for lag in LAGS])


def acf(values):
    centered = values-values.mean()
    spectrum = np.fft.rfft(centered, 32768)
    products = np.fft.irfft(spectrum*spectrum.conjugate(), 32768)[:2001]
    return products/products[0]


started = time.monotonic()
results = []
for index, label in enumerate(('baseline-before', 'r20p0-latency')):
    directory = ROOT/label
    paths = [directory/'probe.json', directory/'browser.pcap', directory/'server.pcap']
    probe = json.loads(paths[0].read_text())
    replies = {r['id']:r['rtt_ms'] for r in probe['reply_records']}
    assert set(replies) == set(range(10000))
    rtt = np.array([replies[i] for i in range(10000)])
    forward, reverse = capture(paths[1]), capture(paths[2])
    assert set(forward) == set(reverse) == set(replies)
    network = np.array([(reverse[i]-forward[i])/1000 for i in range(10000)])
    residual = rtt-network
    ranked = rankdata(rtt, method='average')
    winsor = np.minimum(rtt, np.quantile(rtt, .99))
    component_acfs = {name:correlations(values).tolist() for name, values in
                      [('rtt',rtt),('router_ingress_round_span',network),('remaining_rtt',residual),
                       ('rank_diagnostic',ranked),('winsor99_diagnostic',winsor)]}
    centered = rtt-rtt.mean()
    variance = centered@centered
    contributions = {}
    for lag in LAGS:
        terms = centered[:-lag]*centered[lag:]/variance
        indexes = np.argsort(terms)[-10:][::-1]
        contributions[str(lag)] = dict(total=float(terms.sum()), top1=float(terms[indexes[0]]),
            top2=float(terms[indexes[:2]].sum()), top10=float(terms[indexes].sum()),
            top_pairs=[dict(i=int(i),j=int(i+lag),product=float(terms[i]),
                rtt=[float(rtt[i]),float(rtt[i+lag])],
                router_span=[float(network[i]),float(network[i+lag])],
                remaining_rtt=[float(residual[i]),float(residual[i+lag])]) for i in indexes])
    rng = np.random.Generator(np.random.PCG64(SEED+index))
    iid, blocks = [], []
    for _ in range(REPLICATES):
        iid.append(correlations(rtt[rng.permutation(10000)]))
        block_indexes = rng.permutation(100)
        blocks.append(correlations(rtt.reshape(100,100)[block_indexes].reshape(-1)))
    observed = np.abs(correlations(rtt))
    limits = 3.5/np.sqrt(10000-np.array(LAGS))
    permutations = {}
    for name, sample in [('iid_exchangeability',iid),('one_second_block_exchangeability',blocks)]:
        sample = np.asarray(sample)
        permutations[name] = dict(replicates=REPLICATES,per_lag_two_sided_tail_fraction=
            ((1+np.sum(np.abs(sample)>=observed,axis=0))/(REPLICATES+1)).tolist(),
            abs_corr_95th=np.quantile(np.abs(sample),.95,axis=0).tolist(),
            abs_corr_99th=np.quantile(np.abs(sample),.99,axis=0).tolist(),
            heuristic_family_rejection_rate=float(np.any(np.abs(sample)>limits,axis=1).mean()))
    temporal = acf(rtt)
    peaks = np.argsort(np.abs(temporal[50:]))[-15:][::-1]+50
    rank_acf = acf(ranked)
    row = dict(name=label,inputs=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
        n=10000,lags=list(LAGS),limits=limits.tolist(),component_acfs=component_acfs,
        contributions=contributions,permutations=permutations,
        descriptive=dict(median=float(np.median(rtt)),p99=float(np.quantile(rtt,.99)),
            network_min=float(network.min()),residual_min=float(residual.min()),
            chunk_medians=np.median(rtt.reshape(20,500),axis=1).tolist()),
        strongest_lags_50_to_2000=[dict(lag=int(lag),pearson=float(temporal[lag]),rank=float(rank_acf[lag])) for lag in peaks],
        short_acf={str(lag):float(temporal[lag]) for lag in (1,2,5,10,20,50,100,200)},
        rank_short_acf={str(lag):float(rank_acf[lag]) for lag in (1,2,5,10,20,50,100,200)})
    results.append(row)
result = dict(kind='descriptive research only; original acceptance unchanged',seed=SEED,replicates=REPLICATES,
    elapsed_s=time.monotonic()-started,results=results,
    limitations=['The post-hoc rank/winsorized series never replace primary RTT or acceptance criteria',
        'Permutation fractions assume exchangeability and are exploratory; dependence invalidates IID inference',
        'One-second block permutation preserves local clusters but assumes exchangeable blocks, not proved',
        'Router ingress round span includes forward netem/server/reply arrival; remaining RTT combines reverse netem and client receive plus send-to-capture offset',
        'No scheduler trace recorded for this calibration; no causal attribution to Qdrant, host, guest, GC or timer from these metrics alone'])
with (OUTPUT/'analysis.json').open('x') as f:
    json.dump(result,f,indent=2)
    f.write('\n')
for row in results:
    print(row['name'],json.dumps(dict(acfs=row['component_acfs'],
        contributions={k:{n:v[n] for n in ('total','top1','top2','top10')} for k,v in row['contributions'].items()},
        permutations=row['permutations'],strongest_lags=row['strongest_lags_50_to_2000'][:5]),indent=2))
print('elapsed_s',result['elapsed_s'])
