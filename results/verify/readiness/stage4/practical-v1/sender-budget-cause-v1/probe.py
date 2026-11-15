import contextlib
import io
import json
import os
from pathlib import Path
import resource
import signal
import struct
import sys
import threading
import time

sys.path.insert(0, str(Path('docker').resolve()))
import calibration_probe as probe


class Recorder:
    def __init__(self):
        self.tid = threading.get_native_id()
        self.path = Path(f'/proc/self/task/{self.tid}/schedstat')
        self.handle = self.path.open()
        self.rows = []

    def snapshot(self):
        wall_before = time.monotonic_ns()
        cpu_before = time.thread_time_ns()
        usage = resource.getrusage(resource.RUSAGE_THREAD)
        read_before = time.monotonic_ns()
        self.handle.seek(0)
        scheduler = [int(v) for v in self.handle.read().split()]
        read_after = time.monotonic_ns()
        if len(scheduler) != 3:
            raise ValueError('Expected three task schedstat cumulative counters')
        cpu_after = time.thread_time_ns()
        wall_after = time.monotonic_ns()
        return dict(wall_before_ns=wall_before, wall_after_ns=wall_after,
                    thread_cpu_before_ns=cpu_before, thread_cpu_after_ns=cpu_after,
                    schedstat_read_before_ns=read_before, schedstat_read_after_ns=read_after,
                    schedstat=scheduler, voluntary=usage.ru_nvcsw, involuntary=usage.ru_nivcsw)

    def record(self, frame, send_before, send_after):
        row = dict(id=struct.unpack_from('!I',frame)[0], send_call_before_ns=send_before, send_call_after_ns=send_after)
        self.rows.append(row)
        row['snapshot'] = self.snapshot()

    def close(self):
        self.handle.close()


def send_and_record(original_send, data, recorder):
    before = time.monotonic_ns()
    result = original_send(data)
    after = time.monotonic_ns()
    recorder.record(data, before, after)
    return result


def validate(result, trace):
    expected = list(range(probe.COUNT))
    if [r['id'] for r in result['sent_records']] != expected or [r['id'] for r in trace] != expected:
        raise ValueError('Complete matching ordered diagnostic IDs required')
    if result['sent'] != probe.COUNT or result['frequency_hz'] != 100 or result['frame_bytes'] != 256:
        raise ValueError('Diagnostic probe contract mismatch')
    for row in trace:
        sample = row['snapshot']
        if not (row['send_call_before_ns'] <= row['send_call_after_ns'] <= sample['wall_before_ns'] <=
                sample['schedstat_read_before_ns'] <= sample['schedstat_read_after_ns'] <= sample['wall_after_ns']):
            raise ValueError('Diagnostic wall clock/order mismatch')
        if sample['thread_cpu_after_ns'] < sample['thread_cpu_before_ns'] or any(v < 0 for v in sample['schedstat']):
            raise ValueError('Invalid diagnostic cumulative counters')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: probe.py PEER COLLECTION_ID')
    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, interrupted)
    Path('/tmp/diagnostic-probe.pid').write_text(str(os.getpid()))
    recorder = Recorder()
    recorder.snapshot()
    original_socket = probe.socket.socket
    class ObservedSocket(original_socket):
        def send(self, data):
            return send_and_record(super().send, data, recorder)
    metadata = dict(pid=os.getpid(), tid=recorder.tid, schedstat_path=str(recorder.path),
                    before_affinity=sorted(os.sched_getaffinity(0)), source='mounted production calibration_probe.py',
                    diagnostic_only=True, count=probe.COUNT, observer='one post-send snapshot, no per-select/receive tracing',
                    schedstat_columns=['runtime_ns','runqueue_wait_ns','timeslices'],
                    limitation='Observer adds CPU/syscalls and possible blocking; wall minus thread CPU and schedstat wait do not identify a host cause; proc/CPU/context reads are not atomic')
    def endpoint_context():
        return dict(cpu_stat=Path('/sys/fs/cgroup/cpu.stat').read_text(),
                    memory_events=Path('/sys/fs/cgroup/memory.events').read_text(),
                    monotonic_ns=time.monotonic_ns(), realtime_ns=time.time_ns())
    metadata['endpoint_before'] = endpoint_context()
    probe.socket.socket = ObservedSocket
    output = io.StringIO()
    started = recorder.snapshot()
    try:
        with contextlib.redirect_stdout(output):
            probe.send(sys.argv[1], False, sys.argv[2])
        finished = recorder.snapshot()
        result = json.loads(output.getvalue())
        validate(result, recorder.rows)
        metadata['after_affinity'] = sorted(os.sched_getaffinity(0))
        metadata['endpoint_after'] = endpoint_context()
        result.update(diagnostic=metadata, usage_before=started, usage_after=finished, send_trace=recorder.rows)
        print(json.dumps(result,allow_nan=False))
    except BaseException as error:
        partial=json.dumps(dict(diagnostic=metadata, status='interrupted_or_failed', error=repr(error),
                                send_trace=recorder.rows, production_stdout=output.getvalue()),allow_nan=False)
        Path('/tmp/diagnostic-probe.partial.json').write_text(partial+'\n')
        print(partial)
        raise
    finally:
        recorder.close()
