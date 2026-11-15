from pathlib import Path
import datetime
import hashlib
import json
import math
import struct
import sys

sys.path[:0]=['docker','src/analysis']
from calibration_report import directions
from sender_quality import evaluate

run=Path('results/verify/diagnostic/sender-diagnostic.Mbdvg8v6')
execution=Path('results/verify/readiness/stage4/release-v3/qualification-execution.QnNt51TQ')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((run/'captured.json').read_text())
assert all(sha(r['path'])==r['sha256'] for r in seal)
assert {r['path'] for r in seal}=={str(p) for p in run.rglob('*') if p.is_file() and p.name!='captured.json'}
assert (run/'exit').read_text().strip()==(execution/'exit').read_text().strip()=='0'
assert (execution/'identity-before.sha256').read_bytes()==(execution/'identity-after.sha256').read_bytes()
for line in (execution/'identity-after.sha256').read_text().splitlines():
 digest,path=line.split(None,1);assert sha(path)==digest
assert (run/'commit').read_text().strip()=='3605994e8359a70443621517e11dd2383a726f48'
sources=json.loads((run/'sources-before.json').read_text());assert sources==json.loads((run/'sources-after.json').read_text())
assert all(sha(p)==s and sha(run/'sources'/p)==s for p,s in sources.items())
inventory=json.loads(Path('results/verify/readiness/stage4/release-v3/source-inventory.json').read_text());assert len(inventory)==134 and all(sha(p)==s for p,s in inventory.items())
info=json.loads((run/'docker-info.json').read_text());assert (info['NCPU'],info['MemTotal'])==(2,4109484032)
context=json.loads(Path('results/verify/diagnostic/timer-timer.2ST8NYBU/context.json').read_text())
inspect=json.loads((run/'inspect.json').read_text())
for role in context['services']:
 row=next(r for r in inspect if r['Name'].endswith('-'+role['role']+'-1'))
 assert row['Image']==role['id']
 assert [row['HostConfig'][k] for k in ('NanoCpus','Memory','ShmSize')]==[role[k] for k in ('cpu','memory','shm')]
features=('tcp-segmentation-offload','generic-segmentation-offload','generic-receive-offload','large-receive-offload')
for role,route in [('browser','172.28.20.10 via 172.28.10.2 dev bench0'),('server','172.28.10.10 via 172.28.20.2 dev bench0')]:
 text=(run/f'{role}-route.txt').read_text();assert route in text and all(f'{f}: off' in text for f in features)
neighbors={}
for role in ('browser','server'):
 for prefix in ('','router-'):
  name=prefix+role+'-neighbors'
  first,last=[json.loads((run/(name+suffix+'.json')).read_text()) for suffix in ('','-after')]
  assert first==last and len(first)==1 and 'PERMANENT' in first[0]['state']
  neighbors[name]=first[0]
def fields(text):return {k:int(v) for k,v in (line.split() for line in text.splitlines())}
def udp(row):
 lines=row['/proc/net/snmp'].splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('Udp:'))
 return dict(zip(lines[i].split()[1:],map(int,lines[i+1].split()[1:])))
def frame_types(path):
 data=path.read_bytes();endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24;types={};macs=set()
 while pos<len(data):
  sec,usec,n,wire=struct.unpack_from(endian+'IIII',data,pos);pos+=16;frame=data[pos:pos+n];pos+=n
  types[frame[12:14].hex()]=types.get(frame[12:14].hex(),0)+1
  macs.add((':'.join(f'{b:02x}' for b in frame[6:12]),':'.join(f'{b:02x}' for b in frame[:6])))
 return types,sorted(macs)
probes=[]
for number in (1,2,3):
 d=run/f'baseline-q{number}';probe=json.loads((d/'probe.json').read_text())
 assert probe['sent']==10000 and probe['frame_bytes']==256 and probe['frequency_hz']==100
 assert len(probe['reply_records'])==10000 and {r['id'] for r in probe['reply_records']}==set(range(10000))
 assert all(math.isfinite(r['rtt_ms']) and r['rtt_ms']>=0 for r in probe['reply_records'])
 assert probe['rtt_ms']==[r['rtt_ms'] for r in probe['reply_records']]
 quality=evaluate(probe['sent_records'],10000)
 assert quality==json.loads((d/'sender-quality.json').read_text()) and quality['status']=='passed'
 flows=directions(d,probe);assert all(len(f['entered_ids'])==10000 and not f['dropped_ids'] for f in flows)
 captures={};resources={}
 for role in ('browser','server'):
  log=(d/f'{role}.log').read_text();assert '0 packets dropped by kernel' in log and '10000 packets captured' in log
  types,macs=frame_types(d/f'{role}.pcap');assert types=={'0800':10000}
  assert macs==[(neighbors['router-'+role+'-neighbors']['lladdr'],neighbors[role+'-neighbors']['lladdr'])]
  captures[role]=dict(types=types,macs=macs,kernel_drops=0)
  rows=[json.loads(line) for line in (d/f'{role}-resources.jsonl').read_text().splitlines()]
  assert len(rows)==105 and all(a['wall_ns']<b['wall_ns'] for a,b in zip(rows,rows[1:]))
  first,last=udp(rows[0]),udp(rows[-1]);delta={k:last[k]-first[k] for k in first}
  assert first['InDatagrams']==first['OutDatagrams']==(number-1)*10000 and last['InDatagrams']==last['OutDatagrams']==number*10000
  assert all(delta[k]==0 for k in ('InErrors','RcvbufErrors','SndbufErrors','InCsumErrors','MemErrors','NoPorts'))
  ca,cb=[fields(x['/sys/fs/cgroup/cpu.stat']) for x in (rows[0],rows[-1])];ma,mb=[fields(x['/sys/fs/cgroup/memory.events']) for x in (rows[0],rows[-1])]
  assert cb['throttled_usec']==ca['throttled_usec'] and mb['oom']==ma['oom'] and mb['oom_kill']==ma['oom_kill']
  resources[role]=dict(samples=105,duration_s=(rows[-1]['wall_ns']-rows[0]['wall_ns'])/1e9,udp_delta=delta,cpu_usage_usec=cb['usage_usec']-ca['usage_usec'],throttle_usec=cb['throttled_usec']-ca['throttled_usec'],oom=mb['oom']-ma['oom'],cpu_max=rows[0]['/sys/fs/cgroup/cpu.max'].strip(),udp_first=first,udp_last=last,coverage='cumulative UDP counters bracket baseline to baseline+10000; exact absolute sender start not recorded')
 qdisc={}
 for dev in ('to_browser','to_server'):
  first,last=[next(q for q in json.loads((d/f'qdisc-{when}.json').read_text()) if q['kind']=='netem' and q['dev']==dev) for when in ('before','after')]
  assert first['handle']==last['handle'] and first['options']==last['options']
  assert all(q[k]==0 for q in (first,last) for k in ('backlog','qlen'))
  delta={k:last[k]-first[k] for k in ('bytes','packets','drops')};assert delta==dict(bytes=2980000,packets=10000,drops=0)
  qdisc[dev]=delta
 snapshots=(d/'router-resources.txt').read_text().split('snapshot-end\n');assert len(snapshots)==106 and snapshots[-1]==''
 parsed=[]
 for snap in snapshots[:-1]:
  lines=snap.splitlines();queues=json.loads(lines[1]);cpu={line.split()[0]:int(line.split()[1]) for line in lines[2:] if len(line.split())==2}
  assert all(cpu.get(k,0)==0 for k in ('oom','oom_kill','nr_throttled','throttled_usec'))
  parsed.append(dict(uptime=float(lines[0]),queues=queues,cpu=cpu))
 for dev in ('to_browser','to_server'):
  for snap,expected in ((parsed[0],(number-1)*10000),(parsed[-1],number*10000)):
   q=next(q for q in snap['queues'] if q['kind']=='netem' and q['dev']==dev);assert q['packets']==expected
 resources['router']=dict(samples=105,first_uptime=parsed[0]['uptime'],last_uptime=parsed[-1]['uptime'],coverage='cumulative qdisc counters bracket baseline to baseline+10000; all samples retained')
 probes.append(dict(name=d.name,quality=quality,captures=captures,resources=resources,qdisc=qdisc))
result=dict(status='passed',reviewer='Codex, actual primary evidence review; no independent reviewer claimed',review_preparation='First local assertions corrected endpoint/router neighbor MAC direction and persistent namespace cumulative UDP/qdisc baselines; no collector/raw change or rerun',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run=str(run),execution=str(execution),sealed_files=len(seal),seal_sha256=sha(run/'captured.json'),source_snapshot_count=len(sources),source_inventory_count=134,source_ENV_TLS_release_stable=True,neighbors=neighbors,probes=probes,limitations=['Pcap snaplen96 proves full IDs/tag/header/accounting, not all256payload bytes; successful receive validates every full echoed payload','Collector has no qualification context.json; actual info/inspect/routes and unchanged external ENV/TLS references checked','No recorded absolute sender start; coverage demonstrated by complete endpoint/router counter brackets','Standalone sender-quality preliminary=true is descriptive hardcoded output; configs preliminary remains false','Qualification does not replace calibration or formal browser generator gate'])
out=Path('results/verify/readiness/stage4/release-v3/qualification-Mbdvg8v6-review.json')
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('review',out,'seal_files',len(seal))
for row in probes:print(row['name'],row['quality']['status'],row['quality']['metrics']['late_pct'],row['quality']['metrics']['lag_ms']['max'],row['quality']['metrics']['peak_packets_window'])
