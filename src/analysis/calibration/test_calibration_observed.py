import copy
import unittest
from pathlib import Path

from admission.acceptance import calibration
from calibration.calibration_observed import CONTRACT, METHOD, sender_check
from measurement.raw import read
from calibration.sender_quality import evaluate
from admission import test_acceptance


class ObservedCalibrationTests(unittest.TestCase):
    def fixture(self):
        data = test_acceptance.AcceptanceTests().calibration_fixture()
        data.update(method=METHOD, kind='real')
        for row in data['egress']:
            row['probe'].update(sent=10000, frame_bytes=256, frequency_hz=100)
        data['trace_review'].update(observed_period_reviewed=True, independent_units=False)
        return data

    def test_contract_all_windows_and_no_mutation(self):
        self.assertEqual(read(Path('configs/plan.json'))['calibration'], CONTRACT)
        data = self.fixture()
        before = copy.deepcopy(data)
        result = calibration(data)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(data['echo'], before['echo'])
        self.assertEqual(data['egress'], before['egress'])
        self.assertIsNone(result['block_inference'])
        self.assertEqual(len(result['sender_quality']), 14)
        for row in result['sender_quality'].values():
            self.assertEqual(sum(len(p['counts']['sender_overdue']) for p in row['shadow_phases']),4005)
        self.assertTrue(all(len(w)==20 for w in result['observed_profile']['window_medians'].values()))
        self.assertTrue(all('confidence' not in row and 'CI99' not in row for row in result['loss']))

    def test_small_drift_is_described_and_three_ms_regime_fails(self):
        data = self.fixture()
        probe = data['echo']['r80p1']
        for r in probe['reply_records']:
            r['rtt_ms'] += .134 if r['id'] >= 5000 else 0
        probe['rtt_ms'] = [r['rtt_ms'] for r in probe['reply_records']]
        result = calibration(data)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['dependence']['r80p1']['suspect'])
        for r in probe['reply_records']:
            r['rtt_ms'] += 3 if 500 <= r['id'] < 1000 else 0
        probe['rtt_ms'] = [r['rtt_ms'] for r in probe['reply_records']]
        self.assertEqual(calibration(data)['status'],'failed')

    def pause(self, duration):
        probe = self.fixture()['echo']['before']
        last = -10
        for r in probe['sent_records']:
            r['t_send_ms'] = max(r['t_plan_ms']+(duration if r['id']==5000 else 0), last+2.5)
            last = r['t_send_ms']
        return probe

    def test_single_lag_kept_and_500ms_catchup_fails(self):
        probe = self.pause(70)
        self.assertEqual(evaluate(probe['sent_records'],10000)['status'],'failed')
        result = sender_check(probe,False)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['metrics']['lag_ms']['max'],70)
        probe = self.pause(500)
        result = sender_check(probe,False)
        self.assertEqual(result['status'],'failed')
        self.assertEqual([max(p['counts']['known_timing_bad']) for p in result['shadow_phases']],[13,12,12,12,12])
        self.assertTrue(result['shadow_phases'][0]['violations'])
        self.assertEqual(sender_check(self.pause(499),False)['status'],'passed')

    def test_deadline_unknown_and_tail_preserved(self):
        probe = self.fixture()['echo']['before']
        probe['reply_records'][0]['rtt_ms'] = 100
        self.assertEqual(max(sender_check(probe,False)['shadow_phases'][0]['counts']['known_timing_bad']),0)
        probe['reply_records'][0]['rtt_ms'] = 101
        result = sender_check(probe,False)
        self.assertEqual(result['tail']['tail_records'],[dict(id=0,rtt_ms=101)])
        probe['reply_records'].pop(0)
        self.assertEqual(sender_check(probe,False)['status'],'failed')
        lossy = sender_check(probe,True)
        self.assertEqual(lossy['status'],'passed')
        self.assertFalse(lossy['joint_deadline_complete'])
        self.assertEqual(lossy['tail']['missing_ids'],[0])
        self.assertEqual(max(lossy['shadow_phases'][0]['counts']['unknown_reply']),1)

    def test_loss_boundaries_and_empty_window_json(self):
        import json
        from calibration.calibration_observed import loss_fidelity
        for count in (9900,10000):
            for drops in (0,49,50,149,150,151):
                self.assertEqual(loss_fidelity(drops,count,.01), .005 <= drops/count <= .015)
        self.assertTrue(loss_fidelity(0,10000,0))
        self.assertFalse(loss_fidelity(1,10000,0))
        data = self.fixture()
        probe = data['echo']['r20p1']
        probe['reply_records'] = [r for r in probe['reply_records'] if r['id'] >= 500]
        probe['rtt_ms'] = [r['rtt_ms'] for r in probe['reply_records']]
        result = calibration(data)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['intervals']['r20p1'],[None,None])
        json.dumps(result,allow_nan=False)

    def test_late_burst_spacing_and_repeated_deadlines(self):
        probe = self.fixture()['echo']['before']
        for r in probe['sent_records'][:101]:
            r['t_send_ms'] += 10
        self.assertEqual(sender_check(probe,False)['status'],'failed')
        probe = self.fixture()['echo']['before']
        probe['sent_records'][0]['t_send_ms'] = 8
        self.assertEqual(sender_check(probe,False)['status'],'failed')
        probe = self.fixture()['echo']['before']
        for r in probe['reply_records'][:65]:
            r['rtt_ms'] = 101
        result = sender_check(probe,False)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(any(p['violations'] for p in result['shadow_phases']))
        probe = self.fixture()['echo']['before']
        for i in range(5):
            probe['sent_records'][i]['t_send_ms'] = 40+i
        self.assertEqual(sender_check(probe,False)['status'],'failed')

    def test_integrity_and_explicit_review(self):
        data = self.fixture()
        del data['trace_review']['observed_period_reviewed']
        with self.assertRaisesRegex(ValueError,'explicit observed'):
            calibration(data)
        data = self.fixture()
        data['egress'][0]['entered_ids'].pop()
        with self.assertRaises(ValueError):
            calibration(data)
        data = self.fixture()
        data['echo']['before']['sent_records'][1]['id']=0
        with self.assertRaises(ValueError):
            calibration(data)


if __name__ == '__main__':
    unittest.main()
