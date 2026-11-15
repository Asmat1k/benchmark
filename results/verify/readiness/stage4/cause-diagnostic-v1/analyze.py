from pathlib import Path
import bisect
import hashlib
import json
import re
import sys

sys.path[:0]=['docker','src/analysis']
from sender_quality import evaluate
from calibration_report import directions,ingress
from calibration_probe import collection_tag

run=Path(sys.argv[1]);out=Path(sys.argv[2]);d=run/'baseline-scheduling'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal=json.loads((run/'captured.json').read_text())
assert all(sha(x['path'])==x['sha256'] for x in seal)
assert {x['path'] for x in seal}=={str(p) for p in run.rglob('*') if p.is_file() and p.name!='captured.json'}
before=json.loads((run/'sources-before.json').read_text());after=json.loads((run/'sources-after.json').read_text())
assert before==after and all(sha(p)==s for p,s in before.items())
assert all(sha(run/'sources'/p)==s for p,s in before.items())
for saved in (run/'diagnostic-tools').glob('*.py'):
 assert sha(saved)==sha(Path('results/verify/readiness/stage4/cause-diagnostic-v1/tools')/saved.name)
p=json.loads((d/'probe.json').read_text());target=json.loads((d/'target.json').read_text())['host_tid']
loss=json.loads((d/'trace-loss.json').read_text());assert all(v==0 for r in loss.values() for v in r.values())
events=[]
for line in (d/'trace.txt').read_text().splitlines():
 match=re.search(r'\s(\d+)\.(\d+): (.+)',line)
 if match:events.append(dict(ns=int(match[1])*10**9+int(match[2].ljust(9,'0')),event=match[3]))
assert events==sorted(events,key=lambda e:e['ns'])
assert next(e['ns'] for e in events if 'sender-trace-ready' in e['event']) < p['start_ns'] < p['end_ns'] < next(e['ns'] for e in events if 'sender-trace-stop' in e['event'])
namespace_ids=next(line.split()[1:] for line in json.loads((d/'target.json').read_text())['status'].splitlines() if line.startswith('NSpid:'))
assert int(namespace_ids[0])==target and int(namespace_ids[-1])==p['metadata']['tid']
pairs={}
for call in ('sendto','recvfrom','pselect6'):
 enter=[e for e in events if e['event'].startswith(f'sys_{call}(')];leave=[e for e in events if e['event'].startswith(f'sys_{call} ->')]
 assert len(enter)==len(leave)
 assert all(a['ns']<=b['ns'] for a,b in zip(enter,leave))
 pairs[call]=[(a['ns'],b['ns'],b['event']) for a,b in zip(enter,leave)]
assert len(pairs['sendto'])==len(pairs['recvfrom'])==10000
sent=p['sent_records'];times=[p['start_ns']+round(r['t_send_ms']*1e6) for r in sent]
assert all(t-2000<=a for t,(a,b,e) in zip(times,pairs['sendto']))
segments=[];state='running';since=pairs['sendto'][0][0]
for e in events:
 if e['ns']<since:continue
 text=e['event'];next_state=None
 if text.startswith('sched_switch:'):
  if f'prev_pid={target} ' in text:next_state='runnable' if re.search(r'prev_state=(\S+)',text)[1].startswith('R') else 'sleeping'
  elif f'next_pid={target} ' in text:next_state='running'
 elif text.startswith('sched_wakeup:') and state!='running':next_state='runnable'
 if next_state:
  segments.append((since,e['ns'],state));state=next_state;since=e['ns']
segments.append((since,p['end_ns'],state))
def duration(a,b):
 result=dict(running=0,runnable=0,sleeping=0)
 for start,end,state in segments:
  if end>=a and start<=b:result[state]+=max(0,min(b,end)-max(a,start))/1e6
 return result
collections=[];pending=None
for g in p['gc_records']:
 if g['phase']=='start':pending=g
 elif pending:
  collections.append(dict(generation=g['generation'],start_ns=pending['wall_ns'],end_ns=g['wall_ns'],wall_ms=(g['wall_ns']-pending['wall_ns'])/1e6,cpu_ms=(g['cpu_ns']-pending['cpu_ns'])/1e6));pending=None
assert p['gc_records_complete']
roots=[]
for i in range(1,10000):
 lag=sent[i]['t_send_ms']-sent[i]['t_plan_ms'];gap=(times[i]-times[i-1])/1e6
 if gap<15:continue
 a,b=times[i-1],times[i];calls=[]
 for kind,ps in pairs.items():
  for start,end,ret in ps:
   if end>=a and start<=b and (end-start)>=1000000:calls.append(dict(kind=kind,start_ns=start,end_ns=end,duration_ms=(end-start)/1e6,return_event=ret))
 roots.append(dict(id=i,lag_ms=lag,gap_ms=gap,phase_ms=duration(a,b),long_syscalls=calls,gc_overlap=[g for g in collections if g['end_ns']>=a and g['start_ns']<=b]))
roots.sort(key=lambda r:r['gap_ms'],reverse=True)
fw=ingress(d/'browser.pcap',bytes([172,28,10,10]),bytes([172,28,20,10]),collection_tag(p['collection_id']))
rv=ingress(d/'server.pcap',bytes([172,28,20,10]),bytes([172,28,10,10]),collection_tag(p['collection_id']))
assert fw==rv==set(range(10000))=={r['id'] for r in p['reply_records']}
coverage={}
for role in ('browser','server'):
 rows=[json.loads(l) for l in (d/f'{role}-resources.jsonl').read_text().splitlines()]
 coverage[role]=dict(before_start_ms=(p['start_ns']-rows[0]['wall_ns'])/1e6,after_end_ms=(rows[-1]['wall_ns']-p['end_ns'])/1e6,samples=len(rows))
 assert coverage[role]['before_start_ms']>0 and coverage[role]['after_end_ms']>0
result=dict(run=str(run),sealed_files=len(seal),sources_match=True,trace_loss=loss,target=target,syscalls={k:len(v) for k,v in pairs.items()},coverage=coverage,quality=evaluate(sent,10000),gc=dict(collections=len(collections),max_wall_ms=max([g['wall_ms'] for g in collections],default=0),max_cpu_ms=max([g['cpu_ms'] for g in collections],default=0),records=collections),process_cpu_ms=p['process_cpu_ns']/1e6,roots=roots,limitations=['running is guest scheduler state and cannot rule out vCPU pauses','Instrumentation includes first-timestamp wrapper and GC callback; overhead not causally measured','Single fixed diagnostic, not qualification or acceptance'])
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('quality',result['quality']['status'],result['quality']['metrics']['lag_ms'])
print('gc',result['gc']['collections'],result['gc']['max_wall_ms'],result['gc']['max_cpu_ms'])
print('trace',result['trace_loss'],'syscalls',result['syscalls'],'coverage',coverage)
for r in roots[:10]:print(json.dumps(r))
