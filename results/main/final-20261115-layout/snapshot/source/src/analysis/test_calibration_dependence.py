import unittest

from acceptance import calibration
import test_acceptance


class CalibrationDependenceTest(unittest.TestCase):
    def test_independence_flag_cannot_override_ordered_rtt_dependence(self):
        data = test_acceptance.AcceptanceTests().calibration_fixture()
        for probe in data['echo'].values():
            for index, reply in enumerate(probe['reply_records']):
                reply['rtt_ms'] += index/100000
            probe['rtt_ms'] = [r['rtt_ms'] for r in probe['reply_records']]
        original = list(data['echo']['before']['rtt_ms'])
        for flag in (False, True):
            data['trace_review']['independent_units'] = flag
            result = calibration(data)
            self.assertEqual(result['status'], 'inconclusive')
            self.assertTrue(all(d['suspect'] for d in result['dependence'].values()))
            self.assertEqual(data['echo']['before']['rtt_ms'], original)


if __name__ == '__main__':
    unittest.main()
