import contextlib
import io
import json
import struct
import unittest
from unittest.mock import patch

import calibration_probe as probe


class EchoClock:
    def __init__(self):
        self.now = 0
        self.sent = []
        self.pending = []
        self.received = []
        self.waits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def connect(self, peer):
        pass

    def send(self, frame):
        self.sent.append((self.now, frame))
        self.pending.append((self.now + 1_000_000, frame))

    def recv(self, size):
        _, frame = self.pending.pop(0)
        self.received.append((self.now, struct.unpack('!I', frame[:4])[0]))
        return frame

    def select(self, readers, writers, errors, timeout):
        self.waits += 1
        deadline = self.now + round(timeout * 1e9)
        if self.waits in (5, 8):
            self.now += 55_000_000
            return [], [], []
        if self.pending and self.pending[0][0] <= deadline:
            self.now = max(self.now, self.pending[0][0])
            return readers, [], []
        self.now = deadline
        return [], [], []


class PacingTest(unittest.TestCase):
    def test_pauses_receives_grid_ids_and_actual_rtt(self):
        clock = EchoClock()
        output = io.StringIO()
        with patch.object(probe.socket, 'socket', return_value=clock), \
                patch.object(probe.time, 'monotonic_ns', side_effect=lambda: clock.now), \
                patch.object(probe.time, 'monotonic', side_effect=lambda: clock.now/1e9), \
                patch.object(probe.select, 'select', side_effect=clock.select), \
                contextlib.redirect_stdout(output):
            probe.send('unused', False, 'offline-pacing')
        result = json.loads(output.getvalue())
        rows = result['sent_records']
        self.assertEqual([r['id'] for r in rows], list(range(10000)))
        self.assertEqual([r['t_plan_ms'] for r in rows], [i*10 for i in range(10000)])
        times = [t for t, _ in clock.sent]
        self.assertTrue(all(b-a >= probe.MIN_ECHO_GAP_NS for a, b in zip(times, times[1:])))
        self.assertTrue(all(r['t_send_ms'] >= r['t_plan_ms'] for r in rows))
        self.assertGreater(max(r['t_send_ms']-r['t_plan_ms'] for r in rows), 50)
        self.assertTrue(any(b-a == probe.MIN_ECHO_GAP_NS for a, b in zip(times, times[1:])))
        tag = probe.collection_tag('offline-pacing')
        self.assertEqual([f for _, f in clock.sent], [probe.packet(i, 256, tag) for i in range(10000)])
        self.assertEqual(len(result['reply_records']), 10000)
        self.assertEqual(result['reply_records'], [dict(id=i, rtt_ms=(t-times[i])/1e6) for t, i in clock.received])
        self.assertTrue(any(times[i] < t < times[i+1] and times[i+1]-times[i] == probe.MIN_ECHO_GAP_NS
                            for t, i in clock.received if i+1 < len(times)))
        from sender_quality import window_peak
        self.assertLessEqual(window_peak([t/1e6 for t in times], 10), 4)
        self.assertEqual(window_peak([0, 2.5, 5, 7.5, 10], 10), 4)
        self.assertEqual(window_peak([0, 2.5, 5, 7.5, 9.999999], 10), 5)


if __name__ == '__main__':
    unittest.main()
