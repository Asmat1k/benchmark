import json
from pathlib import Path
import re
import sys

out=Path(sys.argv[1]);mode=sys.argv[2]
read=lambda n:json.loads((out/n).read_text())
records=read('server-records.json');trace=(out/'trace.txt').read_text()
assert records and len({r['id'] for r in records})==len(records)
assert read('target.json')['nspid'][-1]==read('server-ready.json')['pid']
assert '[mono]' in read('trace-config.json')['clock']
assert all(v==0 for row in read('trace-loss.json').values() for v in row.values())
for label,file in [('ready','trace-ready.json'),('stop','trace-stopped.json')]:
    marker=re.findall(r'(\d+\.\d+): tracing_mark_write: transition-trace-'+label,trace)
    assert len(marker)==1, (label,marker)
    ns=round(float(marker[0])*1e9);bracket=read(file)
    assert bracket['before_ns']-2000<=ns<=bracket['after_ns']+2000
counts={}
for call,before,after in [('recvfrom','before_recv_ns','received_ns'),('sendto','before_send_ns','after_send_ns')]:
    entries=[round(float(t)*1e9) for t in re.findall(r'(\d+\.\d+): sys_'+call+r'\(',trace)]
    exits=[(round(float(t)*1e9),v) for t,v in re.findall(r'(\d+\.\d+): sys_'+call+r' -> (\S+)',trace)]
    successful=[t for t,v in exits if v in ('0x100','100','256')]
    assert len(successful)==len(records),(call,len(entries),len(exits),len(successful),len(records))
    assert len(entries) in (len(records),len(records)+1)
    for row,a,b in zip(records,entries,successful):
        assert row[before]-2000<=a<=b<=row[after]+2000,(call,row['id'],a,b,row)
    counts[call]=dict(entries=len(entries),exits=len(exits),success=len(successful),terminal_outstanding=len(entries)-len(exits))
assert 'sched_wakeup:' in trace and 'sched_switch:' in trace
assert 'sys_pselect6' not in trace
if mode=='selftest':assert len(records)==20
result=dict(status='passed',records=len(records),counts=counts,mode=mode,zero_trace_loss=True,pid_clock_brackets_valid=True)
(out/'trace-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
