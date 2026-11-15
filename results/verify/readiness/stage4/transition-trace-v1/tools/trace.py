import json
from pathlib import Path
import re
import subprocess
import sys
import time


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    token, output = sys.argv[1], Path(sys.argv[2])
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', token):
        raise ValueError('invalid instance token')
    indexes = [int(value) for value in sys.argv[3].split(',')] if len(sys.argv) > 3 else []
    mount = Path('/tmp/transition-tracefs')
    mount.mkdir()
    subprocess.run(['mount', '-t', 'tracefs', 'tracefs', str(mount)], check=True)
    instance = mount / 'instances' / token
    try:
        (output / 'available-events.txt').write_text((mount / 'available_events').read_text())
        candidates = []
        for process in Path('/proc').glob('[0-9]*'):
            try:
                args = (process / 'cmdline').read_bytes().split(b'\0')
                if any(arg.endswith(b'/server.py') for arg in args) and token.encode() in args:
                    candidates.append(process)
            except (FileNotFoundError, ProcessLookupError):
                pass
        if len(candidates) != 1:
            raise RuntimeError(f'expected one server, found {candidates}')
        process = candidates[0]
        pid = int(process.name)
        status = (process / 'status').read_text()
        nspid = re.search(r'^NSpid:\s+(.+)$', status, re.M)
        if nspid is None:
            raise RuntimeError('missing NSpid')
        save(output / 'target.json', dict(host_tid=pid, nspid=[int(v) for v in nspid[1].split()],
                                         status=status, cmdline=(process / 'cmdline').read_bytes().decode().split('\0')))
        instance.mkdir()

        def write(name, value):
            (instance / name).write_text(str(value))

        write('tracing_on', 0)
        write('trace_clock', 'mono')
        write('buffer_size_kb', 16384)
        write('options/overwrite', 0)
        clock = (instance / 'trace_clock').read_text()
        if '[mono]' not in clock:
            raise RuntimeError('mono trace clock not active')
        events = {'sched/sched_switch': f'prev_pid == {pid} || next_pid == {pid}',
                  'sched/sched_wakeup': f'pid == {pid}',
                  'sched/sched_waking': f'pid == {pid}'}
        for syscall in ('recvfrom', 'sendto'):
            for edge in ('enter', 'exit'):
                events[f'syscalls/sys_{edge}_{syscall}'] = f'common_pid == {pid}'
        for name in ('net_dev_queue', 'net_dev_start_xmit', 'net_dev_xmit', 'netif_receive_skb'):
            events[f'net/{name}'] = 'name == "to_server" || name == "to_browser"'
            if name == 'netif_receive_skb':
                events[f'net/{name}'] += ' || name == "bench0"'
        if indexes:
            predicate = '(' + ' || '.join(f'ifindex == {index}' for index in indexes) + ')'
            for name in ('qdisc_enqueue', 'qdisc_dequeue'):
                events[f'qdisc/{name}'] = predicate
        for name, predicate in events.items():
            event = instance / 'events' / name
            (output / (name.replace('/', '-') + '.format')).write_text((event / 'format').read_text())
            (event / 'filter').write_text(predicate)
            (event / 'enable').write_text('1')
        save(output / 'trace-config.json', dict(events=events, clock=clock, buffer_kb_per_cpu=16384,
                                                overwrite=False, timeout_seconds=160,
                                                qdisc_ifindex_namespace_ambiguous=True))
        save(output / 'stats-before.json', {p.parent.name: p.read_text() for p in instance.glob('per_cpu/cpu*/stats')})
        write('tracing_on', 1)
        before = time.monotonic_ns()
        write('trace_marker', 'transition-trace-ready')
        save(output / 'trace-ready.json', dict(before_ns=before, after_ns=time.monotonic_ns(), realtime_ns=time.time_ns()))
        deadline = time.monotonic() + 160
        timed_out = False
        while not (output / 'trace-stop').exists():
            if time.monotonic() > deadline:
                timed_out = True
                break
            time.sleep(.05)
        before = time.monotonic_ns()
        write('trace_marker', 'transition-trace-stop')
        save(output / 'trace-stopped.json', dict(before_ns=before, after_ns=time.monotonic_ns(),
                                                 realtime_ns=time.time_ns(), timed_out=timed_out))
        write('tracing_on', 0)
        stats = {p.parent.name: p.read_text() for p in instance.glob('per_cpu/cpu*/stats')}
        save(output / 'stats-after.json', stats)
        (output / 'trace.txt').write_text((instance / 'trace').read_text())
        losses = {}
        for cpu, content in stats.items():
            counters = dict(line.split(':', 1) for line in content.splitlines() if ':' in line)
            losses[cpu] = {key: int(counters[key]) for key in ('overrun', 'commit overrun', 'dropped events')}
        save(output / 'trace-loss.json', losses)
        if not losses or any(value for row in losses.values() for value in row.values()):
            raise RuntimeError('missing stats or lost trace events')
        if timed_out:
            raise TimeoutError('trace-stop')
    finally:
        if instance.exists():
            (instance / 'tracing_on').write_text('0')
            (instance / 'events/enable').write_text('0')
            instance.rmdir()
        subprocess.run(['umount', str(mount)], check=True)


if __name__ == '__main__':
    main()
