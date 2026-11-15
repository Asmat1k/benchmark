import unittest

import numpy as np

from acceptance import calibration
from calibration_blocks import METHOD, bootstrap_interval, process_diagnostics
import test_acceptance


class CalibrationBlocksTests(unittest.TestCase):
    def fixture(self):
        data = test_acceptance.AcceptanceTests().calibration_fixture()
        data['method'] = METHOD
        data['trace_review'].update(stationarity_reviewed=True, short_memory_reviewed=True, bernoulli_loss_reviewed=True, independent_units=False)
        return data

    def test_fixed_contract_joint_loss_family_and_legacy_guard(self):
        data = self.fixture()
        result = calibration(data)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['block_inference']['block_slots'], [100, 200, 500])
        self.assertTrue(all(row['confidence'] == .99875 for row in result['loss']))
        data['trace_review']['short_memory_reviewed'] = False
        self.assertEqual(calibration(data)['status'], 'inconclusive')
        del data['method']
        self.assertEqual(calibration(data)['status'], 'inconclusive')
        data['kind'] = 'real'
        with self.assertRaisesRegex(ValueError, 'approved block method'):
            calibration(data)

    def test_long_dependence_and_drift_remain_inconclusive(self):
        data = self.fixture()
        for probe in data['echo'].values():
            for i, record in enumerate(probe['reply_records']):
                record['rtt_ms'] += i/2000
            probe['rtt_ms'] = [r['rtt_ms'] for r in probe['reply_records']]
        from unittest.mock import patch
        with patch('calibration_blocks.bootstrap_interval', side_effect=lambda values, *args: [float(np.nanmedian(values))]*2):
            result = calibration(data)
        self.assertEqual(result['status'], 'inconclusive')
        self.assertTrue(all(d['suspect'] for d in result['block_inference']['dependence'].values()))
        self.assertTrue(all(d['suspect'] for d in result['dependence'].values()))

    def test_bootstrap_keeps_blocks_missingness_and_seed(self):
        values = np.repeat(np.arange(20, dtype=float), 10)
        values[::11] = np.nan
        original = values.copy()
        first = bootstrap_interval(values, 10, 123, replicates=200)
        self.assertEqual(first, bootstrap_interval(values, 10, 123, replicates=200))
        self.assertLess(first[0], first[1])
        np.testing.assert_equal(values, original)
        self.assertEqual(bootstrap_interval([np.nan]*10+[1]*10, 10, 1, replicates=200), [None, None])

    def test_diagnostics_use_time_order_and_reject_slow_process(self):
        values = np.random.Generator(np.random.PCG64(123)).normal(size=10000)
        self.assertFalse(process_diagnostics(values)['suspect'])
        self.assertTrue(process_diagnostics(np.arange(10000, dtype=float)/1000)['suspect'])
        self.assertTrue(process_diagnostics(np.r_[np.full(500, np.nan), np.ones(9500)])['suspect'])

    def test_block_envelope_and_source_slot_ids(self):
        from unittest.mock import patch
        data = self.fixture()
        with patch('calibration_blocks.bootstrap_interval', side_effect=lambda values, block, seed: [float(np.nanmedian(values))-block/1000, float(np.nanmedian(values))+block/1000]):
            result = calibration(data)
        self.assertEqual(result['intervals']['before'], [.5, 1.5])
        data['echo']['before']['sent_records'][0]['id'] = 10001
        with self.assertRaises(ValueError):
            calibration(data)
