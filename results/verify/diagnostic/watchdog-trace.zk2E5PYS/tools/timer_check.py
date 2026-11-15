import json
from pathlib import Path
import re
import sys


root = Path(sys.argv[1])
read = lambda name: json.loads((root / name).read_text())
assert read('sender-target.json')['nspid'][-1] == read('sender-ready.json')['pid']
config = read('trace-config.json')
assert '[mono]' in config['clock']
address = read('watchdog-symbol.json')['address']
for event in ('timer/hrtimer_start', 'timer/hrtimer_expire_entry'):
    assert config['events'][event] == f'function == {address}'
loss = read('trace-loss.json')
assert loss and all(value == 0 for row in loss.values() for value in row.values())
pending, pairs, replaced = {}, [], []
for line in (root / 'trace.txt').read_text().splitlines():
    match = re.search(r'(\d+)\.(\d+): (hrtimer_start|hrtimer_expire_entry): (.+)', line)
    if not match:
        continue
    seconds, fraction, event, payload = match.groups()
    timestamp = int(seconds) * 1_000_000_000 + int(fraction.ljust(9, '0')[:9])
    fields = dict(re.findall(r'(\w+)=(\S+)', payload))
    assert fields['function'] == 'qdisc_watchdog' or fields['function'].startswith('qdisc_watchdog+')
    pointer = fields['hrtimer']
    if event == 'hrtimer_start':
        record = dict(timer=pointer, start_ns=timestamp, expires_ns=int(fields['expires']),
                      softexpires_ns=int(fields['softexpires']), mode=fields['mode'])
        assert record['expires_ns'] >= record['softexpires_ns']
        if pointer in pending:
            replaced.append(pending[pointer])
        pending[pointer] = record
    else:
        assert pointer in pending, ('expiry without recorded start', line)
        start = pending.pop(pointer)
        assert timestamp >= start['start_ns']
        pairs.append(dict(**start, callback_ns=timestamp, timer_now_ns=int(fields['now']),
                          callback_lateness_ns=timestamp-start['softexpires_ns'],
                          timer_now_lateness_ns=int(fields['now'])-start['softexpires_ns'],
                          callback_minus_sampled_now_ns=timestamp-int(fields['now'])))
assert pairs, 'no watchdog start/expiry pairs'
result = dict(status='passed', pairs=pairs, pair_count=len(pairs), replacement_starts=replaced,
              unmatched_final_starts=list(pending.values()), zero_trace_loss=True,
              sender_pid_matches=True, function_filter_valid=True,
              cancellation_observed=False, expiry_exit_observed=False,
              direction_association='not established by this checker',
              clock_evidence='trace mono; upstream netem uses CLOCK_MONOTONIC; init not traced')
(root / 'timer-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: result[key] for key in ('status', 'pair_count', 'zero_trace_loss', 'sender_pid_matches')}))
