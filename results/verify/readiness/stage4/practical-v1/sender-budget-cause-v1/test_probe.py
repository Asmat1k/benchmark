import importlib.util
from pathlib import Path
import struct
import unittest
from unittest.mock import patch


PATH = Path(__file__).with_name('probe.py')
spec = importlib.util.spec_from_file_location('budget_probe',PATH)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class ProbeTests(unittest.TestCase):
    def test_observer_runs_after_real_send_and_preserves_result(self):
        events = []
        class Recorder:
            def record(self, data, before, after):
                events.append(('record',data,before,after))
        frame = struct.pack('!I',7)
        def send(data):
            events.append(('send',data))
            return 256
        with patch.object(candidate.time,'monotonic_ns',side_effect=[10,20]):
            self.assertEqual(candidate.send_and_record(send,frame,Recorder()),256)
        self.assertEqual(events,[('send',frame),('record',frame,10,20)])

    def test_failed_send_is_not_fabricated(self):
        class Recorder:
            def record(self,*args):
                raise AssertionError('failed send must not create a trace')
        def send(data):
            raise OSError('synthetic failure')
        with self.assertRaises(OSError):
            candidate.send_and_record(send,b'x',Recorder())

    def test_no_select_or_receive_hook_or_production_mutation(self):
        self.assertEqual(candidate.probe.MAX_ECHO_WAIT_NS,0)
        self.assertEqual(candidate.probe.COUNT,10000)
        self.assertEqual(candidate.probe.MIN_ECHO_GAP_NS,2500000)
        source = PATH.read_text()
        self.assertNotIn('probe.select.select =',source)
        self.assertNotIn('probe.receive =',source)

    def test_counter_trace_integrity(self):
        trace = [dict(id=0,send_call_before_ns=1,send_call_after_ns=2,
                      snapshot=dict(wall_before_ns=3,wall_after_ns=7,schedstat_read_before_ns=4,
                                    schedstat_read_after_ns=6,thread_cpu_before_ns=1,thread_cpu_after_ns=2,
                                    schedstat=[1,2,3]))]
        result = dict(sent_records=[dict(id=0)],sent=1,frequency_hz=100,frame_bytes=256)
        with patch.object(candidate.probe,'COUNT',1):
            candidate.validate(result,trace)
            trace[0]['id']=1
            with self.assertRaises(ValueError): candidate.validate(result,trace)
            trace[0]['id']=0
            trace[0]['snapshot']['schedstat']=[-1,0,0]
            with self.assertRaises(ValueError): candidate.validate(result,trace)


if __name__ == '__main__':
    unittest.main()
