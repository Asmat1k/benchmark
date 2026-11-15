import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr

sys.path[:0]=['docker','src/analysis']
from calibration_report import directions
from calibration_blocks import process_diagnostics
from sender_quality import evaluate

parser=argparse.ArgumentParser()
parser.add_argument('raw',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
root=args.raw
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((root/'captured.json').read_text())
assert all(sha(r['path'])==r['sha256'] for r in seal)
assert json.loads((root/'sources-before.json').read_text())==json.loads((root/'sources-after.json').read_text())

def capture(path):
    data=path.read_bytes();endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';position=24;packets={}
    while position<len(data):
        sec,usec,count,length=struct.unpack_from(endian+'IIII',data,position);position+=16
        frame=data[position:position+count];position+=count
        if frame[12:14]!=b'\x08\x00' or frame[23]!=17:continue
        ip=frame[14:];udp=ip[(ip[0]&15)*4:];packets[int.from_bytes(udp[8:12],'big')]=sec*1000000+usec
    return packets

def correlations(values):
    values=values-values.mean();variance=values@values
    return [float(values[:-lag]@values[lag:]/variance) if variance else 0. for lag in (500,1000,2000)]

results=[]
for label in ('shared-A1','pinned-B1','pinned-B2','shared-A2'):
    d=root/label;p=json.loads((d/'probe.json').read_text());n=len(p['sent_records']);assert n==5000
    assert p['sent']==n and p['frame_bytes']==256 and p['frequency_hz']==100
    assert [r['id'] for r in p['sent_records']]==list(range(n))
    assert len(p['reply_records'])==len({r['id'] for r in p['reply_records']})
    flows=directions(d,p)
    snapshots=json.loads((d/'probe-inspect.json').read_text());placement={}
    expected={'browser':'0','server':'1'} if label.startswith('pinned') else {'browser':'0-1','server':'0-1'}
    for role in ('browser','server'):
        inspect=next(r for r in snapshots if r['Name'].endswith('-probe-'+role))
        status=(d/f'{role}-status.txt').read_text();actual=next(line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith('Cpus_allowed_list:'))
        assert inspect['HostConfig']['CpusetCpus']==actual==expected[role]
        placement[role]=dict(docker_cpuset=inspect['HostConfig']['CpusetCpus'],proc_allowed_list=actual,image=inspect['Image'])
        assert '0 packets dropped by kernel' in (d/f'{role}.log').read_text()
    fw,rv=capture(d/'browser.pcap'),capture(d/'server.pcap');rtt=np.full(n,np.nan);network=np.full(n,np.nan)
    for reply in p['reply_records']:
        i=reply['id'];rtt[i]=reply['rtt_ms'];network[i]=(rv[i]-fw[i])/1000
    assert p['rtt_ms']==[r['rtt_ms'] for r in p['reply_records']]
    assert all(math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in p['reply_records'])
    assert np.isfinite(rtt[np.isfinite(rtt)]).all() and np.nanmin(rtt)>=0
    components={}
    for name,values in [('rtt',rtt),('router_span',network),('remaining_rtt',rtt-network)]:
        filled=np.where(np.isfinite(values),values,np.nanmedian(values))
        matrix=filled.reshape(50,100);first=np.median(matrix[:25],axis=0);second=np.median(matrix[25:],axis=0)
        phase=np.median(matrix,axis=0);ranked=rankdata(filled);rankphase=ranked.reshape(50,100).mean(axis=0)
        power=np.abs(np.fft.rfft(phase-phase.mean()))**2;power[0]=0
        components[name]=dict(correlation=correlations(filled),rank_correlation=correlations(ranked),
            median=float(np.nanmedian(values)),p95=float(np.nanquantile(values,.95)),p99=float(np.nanquantile(values,.99)),
            phase_half_spearman=float(spearmanr(first,second).statistic),
            phase_rank_variance_fraction=float(np.var(rankphase)/np.var(ranked)),
            phase_medians=phase.tolist(),phase_top_spectral_bins=[dict(hz=int(i),power=float(power[i])) for i in np.argsort(power)[-5:][::-1]],
            chunk_5second_medians=[float(np.nanmedian(v)) for v in np.array_split(values,10)])
    process=process_diagnostics(rtt)
    results.append(dict(name=label,n=n,placement=placement,quality=evaluate(p['sent_records'],n),
        process_diagnostics=process,actual_n_limits={str(l):float(3.5/np.sqrt(n-l)) for l in (500,1000,2000)},
        components=components,loss=[dict(direction=f['direction'],entered=len(f['entered_ids']),drops=len(f['dropped_ids'])) for f in flows],
        inputs=[dict(path=str(d/f),sha256=sha(d/f)) for f in ('probe.json','browser.pcap','server.pcap','probe-inspect.json','browser-status.txt','server-status.txt')]))
result=dict(run=str(root),sealed_files=len(seal),source_snapshots_equal=True,scope='fixed affinity ABBA read-only diagnostic decomposition, not formal acceptance',results=results,
    limitations=['N5000,not10000;shortabsenceofraretailsdoesnotqualifyfullcalibration',
        'AffinitychangesexecutionpolicyandCPUplacement;ENVfieldsalonecannotprovesamepolicy',
        'OnlyonefixedABBA,nocausalguaranteeagainstalltime-varyingconfounds',
        'Networkspancombinesforwardnetem/server/reverseingress;remainingRTTnotpureCPU',
        'Medianimputationusedonlymatchingprocessdiagnostics;rawRTTnotchanged',
        'IfAandBbothclearormixed,do notadoptaffinityasestablishedfix'])
with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for row in results:
    print(row['name'],'placement',row['placement'],'sender',row['quality']['status'],'processsuspect',row['process_diagnostics']['suspect'])
    for name,c in row['components'].items():print(name,'corr',c['correlation'],'median',c['median'],'p99',c['p99'],'phase',c['phase_half_spearman'],'chunks',c['chunk_5second_medians'])
