from pathlib import Path
import json,struct,statistics,hashlib
run=Path('results/verify/diagnostic/sender-diagnostic.E243q4gg')
d=run/'baseline-q1'
p=json.loads((d/'probe.json').read_text());sent=p['sent_records'];rtt={x['id']:x['rtt_ms'] for x in p['reply_records']}
def pcap(path):
 data=path.read_bytes();endian='<' if data[:4]==b'\xd4\xc3\xb2\xa1' else '>';pos=24;out={}
 while pos<len(data):
  sec,usec,size,length=struct.unpack_from(endian+'IIII',data,pos);pos+=16;f=data[pos:pos+size];pos+=size
  if f[12:14]!=b'\x08\x00':continue
  ip=f[14:];udp=ip[(ip[0]&15)*4:]
  if ip[9]==17:out[int.from_bytes(udp[8:12],'big')]=sec*1000000+usec
 return out
fw=pcap(d/'browser.pcap');rv=pcap(d/'server.pcap')
def fields(s):return {k:int(v) for k,v in (x.split() for x in s.splitlines())}
def udp(row):
 lines=row['/proc/net/snmp'].splitlines();i=next(i for i,x in enumerate(lines) if x.startswith('Udp:'))
 return dict(zip(lines[i].split()[1:],map(int,lines[i+1].split()[1:])))
def cpus(row):return list(map(int,row['/proc/stat'].splitlines()[0].split()[1:]))
rows=[json.loads(x) for x in (d/'browser-resources.jsonl').read_text().splitlines()]
resources={}
for role in ('browser','server'):
 records=[json.loads(x) for x in (d/f'{role}-resources.jsonl').read_text().splitlines()]
 pairs=[]
 for a,b in zip(records,records[1:]):
  dt=(b['wall_ns']-a['wall_ns'])/1e9;ca=cpus(a);cb=cpus(b);dc=[y-x for x,y in zip(ca,cb)];total=sum(dc[:8]);cpu_a=fields(a['/sys/fs/cgroup/cpu.stat']);cpu_b=fields(b['/sys/fs/cgroup/cpu.stat'])
  pressure=lambda r: int(r['/proc/pressure/cpu'].splitlines()[0].split('total=')[1])
  pairs.append(dict(first_sent_count=udp(a)['OutDatagrams'],last_sent_count=udp(b)['OutDatagrams'],sample_gap_s=dt,vm_busy_pct=100*(total-dc[3]-dc[4])/total,vm_steal_jiffies=dc[7],probe_cpu_core_pct=100*(cpu_b['usage_usec']-cpu_a['usage_usec'])/1e6/dt,vm_cpu_pressure_ms=(pressure(b)-pressure(a))/1000,probe_throttled_us=cpu_b['throttled_usec']-cpu_a['throttled_usec'],oom=fields(b['/sys/fs/cgroup/memory.events'])['oom']-fields(a['/sys/fs/cgroup/memory.events'])['oom']))
 resources[role]=dict(max_sample_gap_s=max(x['sample_gap_s'] for x in pairs),max_vm_busy_pct=max(x['vm_busy_pct'] for x in pairs),max_probe_cpu_core_pct=max(x['probe_cpu_core_pct'] for x in pairs),around_failure=[x for x in pairs if x['first_sent_count']<9200 and x['last_sent_count']>9100])
events=[]
for i in (2298,7870,9151):
 event=[]
 for j in range(i-3,min(i+13,10000)):
  event.append(dict(id=j,plan_ms=sent[j]['t_plan_ms'],lag_ms=sent[j]['t_send_ms']-sent[j]['t_plan_ms'],send_gap_ms=sent[j]['t_send_ms']-sent[j-1]['t_send_ms'],forward_ingress_gap_ms=(fw[j]-fw[j-1])/1000,reverse_ingress_gap_ms=(rv[j]-rv[j-1])/1000,router_round_path_ms=(rv[j]-fw[j])/1000,rtt_ms=rtt[j],previous_reply_received_to_this_send_ms=sent[j]['t_send_ms']-(sent[j-1]['t_send_ms']+rtt[j-1])))
 events.append(dict(first_late_id=i,records=event))
network_round=[(rv[i]-fw[i])/1000 for i in range(10000)]
raw_refs={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [d/'probe.json',d/'browser.pcap',d/'server.pcap',d/'browser-resources.jsonl',d/'server-resources.jsonl',d/'router-resources.txt',run/'captured.json']}
result=dict(run=str(run),inputs=raw_refs,resources=resources,events=events,network_round_ms=dict(median=statistics.median(network_round),max=max(network_round)),rtt_ms=dict(median=statistics.median(rtt.values()),max=max(rtt.values())),send_vs_pcap_gap_difference_max_ms=max(abs((fw[i]-fw[i-1])/1000-(sent[i]['t_send_ms']-sent[i-1]['t_send_ms'])) for i in range(1,10000)))
out=Path('results/verify/readiness/stage4/qualification-E243q4gg-cause-final.json')
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(out)
print('event9151', json.dumps(next(e for e in events if e['first_late_id']==9151)['records'][3],indent=2))
