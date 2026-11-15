import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/analysis'))
from sender_quality import assess


def check(directory):
    root = Path(directory)
    probe = json.loads((root/'probe.json').read_text())
    text = (root/'trace.txt').read_text()
    events = []
    for line in text.splitlines():
        match = re.search(r'\s(\d+\.\d+): (.+)', line)
        if match:
            events.append(dict(ns=round(float(match[1])*1e9), event=match[2]))
    calls = {kind:[r for r in probe['trace'] if r['kind'] == kind] for kind in ('select', 'send', 'receive')}
    counts = {}
    complete = True
    for kind, syscall in (('select', 'pselect6'), ('send', 'sendto'), ('receive', 'recvfrom')):
        entries = [e for e in events if e['event'].startswith(f'sys_{syscall}(')]
        exits = [e for e in events if e['event'].startswith(f'sys_{syscall} ->')]
        paired = len(entries) == len(exits) == len(calls[kind])
        if paired:
            paired = all(r['before']['wall_ns']-2000 <= a['ns'] <= b['ns'] <= r['after']['wall_ns']+2000
                         for r,a,b in zip(calls[kind], entries, exits))
        counts[kind] = dict(wrapper=len(calls[kind]), entry=len(entries), exit=len(exits), paired=paired)
        complete &= paired
    resources = [json.loads(line) for line in (root/'browser-resources.jsonl').read_text().splitlines()]
    server_resources = [json.loads(line) for line in (root/'server-resources.jsonl').read_text().splitlines()]
    end_ns = probe['usage_after']['wall_ns']
    coverage = all(rows[0]['wall_ns'] < probe['start_ns'] and rows[-1]['wall_ns'] > end_ns
                   for rows in (resources, server_resources))
    details = []
    for row in probe['sent_records']:
        if row['t_send_ms']-row['t_plan_ms'] < 10:
            continue
        due = probe['start_ns'] + row['id']*10_000_000
        actual = probe['start_ns'] + round(row['t_send_ms']*1e6)
        prior = row['id']-1
        while prior > 0 and probe['sent_records'][prior]['t_send_ms']-probe['sent_records'][prior]['t_plan_ms'] >= 10:
            prior -= 1
        lower = min(due-10_000_000, calls['send'][prior]['before']['wall_ns']) if calls['send'] else due-50_000_000
        details.append(dict(**row, due_ns=due, send_ns=actual,
                            calls=[r for r in probe['trace'] if r['after']['wall_ns'] >= lower and r['before']['wall_ns'] <= actual],
                            kernel=[e for e in events if lower <= e['ns'] <= actual+100_000]))
    (root/'late-details.json').write_text(json.dumps(details, indent=2)+'\n')
    loss = json.loads((root/'trace-loss.json').read_text())
    lossless = all(v == 0 for row in loss.values() for v in row.values())
    result = dict(sender_quality=assess(probe['sent_records'], 1500), syscalls=counts, endpoint_resource_coverage=coverage, lossless=lossless,
                  late_slots=len(details), slot_criterion_pass=all(0 <= r['t_send_ms']-r['t_plan_ms'] < 10 for r in probe['sent_records']),
                  trace_usable=bool(complete and coverage and lossless), host_scheduling_available=False)
    (root/'trace-check.json').write_text(json.dumps(result, indent=2)+'\n')
    if not result['trace_usable']:
        raise SystemExit('trace/coverage validation failed; see trace-check.json')


if __name__ == '__main__':
    check(sys.argv[1])
