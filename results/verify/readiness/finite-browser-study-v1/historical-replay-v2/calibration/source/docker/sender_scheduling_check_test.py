import json
from pathlib import Path
import tempfile
import unittest

from sender_scheduling_check import check


class TraceCheckTest(unittest.TestCase):
    def fixture(self, path):
        probe = dict(start_ns=100_000_000, usage_after=dict(wall_ns=150_000_000),
                     trace=[dict(kind='select', before=dict(wall_ns=101_000_000),
                                 after=dict(wall_ns=130_000_000))],
                     sent_records=[dict(id=1, t_plan_ms=10, t_send_ms=30)])
        (path/'probe.json').write_text(json.dumps(probe))
        (path/'trace.txt').write_text(' python-1 [000] ..... 0.102000: sys_pselect6(n: 0)\n python-1 [000] ..... 0.129000: sys_pselect6 -> 0x0\n')
        for role in ('browser', 'server'):
            (path/f'{role}-resources.jsonl').write_text('{"wall_ns": 90000000}\n{"wall_ns": 160000000}\n')
        (path/'trace-loss.json').write_text('{"cpu0":{"overrun":0,"commit overrun":0,"dropped events":0}}')

    def test_late_slot_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            check(path)
            result = json.loads((path/'trace-check.json').read_text())
            self.assertTrue(result['trace_usable'])
            self.assertFalse(result['slot_criterion_pass'])
            self.assertEqual(len(json.loads((path/'late-details.json').read_text())), 1)

    def test_missing_syscall_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path/'trace.txt').write_text('')
            with self.assertRaises(SystemExit):
                check(path)

    def test_incomplete_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path/'browser-resources.jsonl').write_text('{"wall_ns": 101000000}\n')
            with self.assertRaises(SystemExit):
                check(path)

    def test_trace_loss_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            (path/'trace-loss.json').write_text('{"cpu0":{"overrun":1}}')
            with self.assertRaises(SystemExit):
                check(path)


if __name__ == '__main__':
    unittest.main()
