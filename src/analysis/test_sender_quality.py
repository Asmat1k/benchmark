import copy
import unittest

from acceptance import calibration, probe_records
from sender_quality import assess, evaluate, policy, window_peak


class SenderQualityTest(unittest.TestCase):
    def records(self, count=1000):
        return [dict(id=i,t_plan_ms=i*10,t_send_ms=i*10) for i in range(count)]

    def test_late_fraction_boundary(self):
        for count, passed in ((9,True),(10,True),(11,False)):
            rows=self.records()
            for i in range(10,10+count*20,20): rows[i]['t_send_ms']+=10
            self.assertEqual(evaluate(rows,1000)['status']=='passed',passed)

    def test_lag_boundary_with_acceptable_late_fraction(self):
        for lag, passed in ((49.999,True),(50,True),(50.001,False)):
            rows=self.records(10000)
            for i in range(100,111): rows[i]['t_send_ms']=max(i*10,1000+lag+(i-100)*5)
            result=evaluate(rows,10000)
            lag_failure=any('maximum lag' in r for r in result['reasons'])
            self.assertEqual(not lag_failure,passed)
            self.assertLess(result['metrics']['late_pct'],policy()['max_late_pct'])

    def test_burst_boundaries_and_half_open_window(self):
        self.assertEqual(window_peak([0,10,20],10),1)
        for size, passed in ((3,True),(4,True),(5,False)):
            rows=self.records()
            for i in range(100,100+size): rows[i]['t_send_ms']=(100+size-1)*10
            result=evaluate(rows,1000)
            self.assertEqual(result['status']=='passed',passed)
            self.assertLess(result['metrics']['late_pct'],1)

    def test_bad_data_never_passes(self):
        base=self.records()
        cases=[base[:-1]]
        for field,value in (('id',99),('t_plan_ms',11),('t_send_ms',float('nan')),('t_send_ms',-1)):
            rows=copy.deepcopy(base); rows[0][field]=value; cases.append(rows)
        rows=copy.deepcopy(base); rows[2]['t_send_ms']=9; cases.append(rows)
        for rows in cases:
            self.assertEqual(assess(rows,1000)['status'],'inconclusive')

    def test_probe_integrity_and_same_rules_for_all_profiles(self):
        rows=self.records(10000); rows[100]['t_send_ms']+=10
        probe=dict(sent_records=rows,reply_records=[dict(id=i,rtt_ms=1) for i in range(10000)])
        for profile in ('before','after','r20p0','r20p1','r80p0','r80p1'):
            probe_records(dict(probe,profile=profile))
        for replies in ([dict(id=1,rtt_ms=1)]*2,[dict(id=10000,rtt_ms=1)],[dict(id=1,rtt_ms=-1)]):
            with self.assertRaises(ValueError): probe_records(dict(probe,reply_records=replies))
        result=evaluate(rows,10000)
        self.assertEqual(result['criteria_version'],'udp-sender-v2')
        self.assertFalse(result['historical_every_slot_pass'])
        self.assertEqual(result['status'],'passed')

    def test_calibration_keeps_timing_failures_and_integrity(self):
        from test_acceptance import AcceptanceTests
        data=AcceptanceTests().calibration_fixture()
        data['echo']['before']['sent_records'][100]['t_send_ms']+=10
        result=calibration(data)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(len(result['sender_quality']),14)
        self.assertFalse(result['sender_quality']['before']['historical_every_slot_pass'])
        for i in range(100,105):
            data['egress'][0]['probe']['sent_records'][i]['t_send_ms']=1040
        result=calibration(data)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(any('burst' in reason for row in result['sender_quality'].values() for reason in row['reasons']))
        data['echo']['before']['reply_records'][1]['id']=0
        with self.assertRaisesRegex(ValueError,'reply IDs'): calibration(data)
