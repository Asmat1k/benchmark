import hashlib
import json
from pathlib import Path
import re

out = Path(__file__).parent
run = Path('results/verify/diagnostic/sender-scheduling.LGEmSpOH')
directory = run/'baseline-scheduling'
probe = json.loads((directory/'probe.json').read_text())
target = json.loads((directory/'target.json').read_text())['host_tid']
start = probe['start_ns']
events = []
for line in (directory/'trace.txt').read_text().splitlines():
    match = re.search(r'\s(\d+\.\d+): (.+)', line)
    if match:
        seconds, fraction = match[1].split('.')
        events.append(dict(ns=int(seconds)*10**9+int(fraction.ljust(9, '0')), event=match[2]))
assert events == sorted(events, key=lambda r:r['ns'])
traces = {kind:[r for r in probe['trace'] if r['kind']==kind] for kind in ('select','send','receive')}
checks = {}
select_pairs = []
for kind, name in (('select','pselect6'),('send','sendto'),('receive','recvfrom')):
    entries = [r for r in events if r['event'].startswith(f'sys_{name}(')]
    exits = [r for r in events if r['event'].startswith(f'sys_{name} ->')]
    assert len(entries)==len(exits)==len(traces[kind])
    for wrapper, entry, exit in zip(traces[kind], entries, exits):
        assert wrapper['before']['wall_ns']-2000 <= entry['ns'] <= exit['ns'] <= wrapper['after']['wall_ns']+2000
        if kind=='select':
            select_pairs.append((wrapper, entry, exit))
    checks[kind] = len(entries)
lag = [r['t_send_ms']-r['t_plan_ms'] for r in probe['sent_records']]
late = []
roots = []
for identity, value in enumerate(lag):
    if value < 10:
        continue
    due = start + identity*10_000_000
    send = traces['send'][identity]
    previous = traces['send'][identity-1]['after']['wall_ns'] if identity else start
    preceding = [pair for pair in select_pairs if previous <= pair[0]['before']['wall_ns'] <= send['before']['wall_ns']]
    row = dict(id=identity, lag_ms=value, due_ns=due)
    if not preceding:
        row['kind'] = 'catch-up'
        late.append(row)
        continue
    wrapper, entry, exit = preceding[-1]
    timeline = [e for e in events if entry['ns'] <= e['ns'] <= wrapper['after']['wall_ns']+2000]
    wakes = [e for e in timeline if e['event'].startswith('sched_wakeup:')]
    switches = [e for e in timeline if e['event'].startswith('sched_switch:') and f'next_pid={target} ' in e['event']]
    state = 'running'
    since = entry['ns']
    durations = dict(running=0, runnable=0, sleeping=0)
    for event in timeline:
        if event['ns'] > exit['ns']:
            break
        next_state = None
        text = event['event']
        if text.startswith('sched_switch:'):
            if f'prev_pid={target} ' in text:
                previous_state = re.search(r'prev_state=(\S+)',text)[1]
                next_state = 'runnable' if previous_state.startswith('R') else 'sleeping'
            elif f'next_pid={target} ' in text:
                next_state = 'running'
        elif text.startswith('sched_wakeup:') and state != 'running':
            next_state = 'runnable'
        if next_state is not None:
            durations[state] += event['ns']-since
            state, since = next_state, event['ns']
    durations[state] += exit['ns']-since
    row.update(kind='timeout' if not wrapper['ready'] else 'response',
               timeout_ms=wrapper['timeout_ns']/1e6,
               wrapper_wall_ms=(wrapper['after']['wall_ns']-wrapper['before']['wall_ns'])/1e6,
               wrapper_cpu_ms=(wrapper['after']['cpu_ns']-wrapper['before']['cpu_ns'])/1e6,
               schedstat_wait_ms=(wrapper['after']['schedstat'][1]-wrapper['before']['schedstat'][1])/1e6,
               syscall_ms=(exit['ns']-entry['ns'])/1e6,
               exit_to_wrapper_after_ms=(wrapper['after']['wall_ns']-exit['ns'])/1e6,
               syscall_phase_ms={k:v/1e6 for k,v in durations.items()},
               timeline=timeline)
    if wakes and switches:
        wake = wakes[-1]
        switch = next(e for e in switches if e['ns'] >= wake['ns'])
        row.update(wakeup_after_due_ms=(wake['ns']-due)/1e6,
                   wakeup_to_scheduled_ms=(switch['ns']-wake['ns'])/1e6)
    late.append(row)
    roots.append(row)
(out/'late-decomposition.json').write_text(json.dumps(late,indent=2)+'\n')
coverage = {}
for role in ('browser','server'):
    samples = [json.loads(line) for line in (directory/f'{role}-resources.jsonl').read_text().splitlines()]
    coverage[role] = dict(before_start_ms=(start-samples[0]['wall_ns'])/1e6,
                          after_probe_ms=(samples[-1]['wall_ns']-probe['usage_after']['wall_ns'])/1e6)
    assert all(v>0 for v in coverage[role].values())
ready = next(e for e in events if 'sender-trace-ready' in e['event'])
stop = next(e for e in events if 'sender-trace-stop' in e['event'])
bracket = json.loads((directory/'trace-ready.json').read_text())
assert bracket['before_ns']-1000 <= ready['ns'] <= bracket['after_ns']+1000
assert ready['ns'] < start < probe['usage_after']['wall_ns'] < stop['ns']
router = (directory/'router-resources.txt').read_text().splitlines()
uptime = [float(line) for line in router if re.fullmatch(r'\d+\.\d+',line)]
assert uptime[0]*1e9 < start and uptime[-1]*1e9 > probe['usage_after']['wall_ns']
coverage['router'] = dict(first_uptime=uptime[0],last_uptime=uptime[-1],snapshots=router.count('snapshot-end'))
rows = json.loads((run/'captured.json').read_text())
assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in rows)
before,after=[json.loads((run/f'sources-{s}.json').read_text()) for s in ('before','after')]
assert before==after
assert all(hashlib.sha256((run/'sources'/name).read_bytes()).hexdigest()==value for name,value in before.items())
old=Path('results/verify/diagnostic/sender-diagnostic.T6NngDpB/captured.json')
old_rows=json.loads(old.read_text())
assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in old_rows)
assert all(v==0 for row in json.loads((directory/'trace-loss.json').read_text()).values() for v in row.values())
result = dict(seal_verified=len(rows), previous_seal_verified=len(old_rows), sources_equal=True,
              source_copies_verified=len(before), paired_syscalls=checks, resource_coverage=coverage,
              target_host_tid=target, late_slots=len(late), root_intervals=len(roots),
              timeout_roots=sum(r['kind']=='timeout' for r in roots),
              response_roots=sum(r['kind']=='response' for r in roots))
(out/'integrity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
for r in roots:
    print(r['id'],r['kind'],*[round(r[k],6) for k in ('lag_ms','syscall_ms','wakeup_after_due_ms','wakeup_to_scheduled_ms','exit_to_wrapper_after_ms','wrapper_cpu_ms')])
