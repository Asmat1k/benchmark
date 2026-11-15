import unittest

from observer_only import interval_summary


class ObserverIntervalsTest(unittest.TestCase):
    def rows(self):
        return [dict(sample_index=i,end_usec=(i+1)*1000000,interval_usec=1000000,cpu_usage_usec=10000 if i != 2 else 250000) for i in range(6)]

    def test_boundary_spike_retained_and_complete_intervals_explicit(self):
        rows = self.rows()
        result = interval_summary(rows,1500000,5500000)
        self.assertEqual(result['sample_ids'],[2,3,4])
        self.assertEqual(result['max_cpu_pct'],25)
        self.assertEqual(len(rows),6)
        self.assertEqual(interval_summary(rows,2500000,5500000)['sample_ids'],[3,4])
        self.assertEqual(rows[2]['cpu_usage_usec'],250000)

    def test_incomplete_or_nonmonotone_sampler_rejected(self):
        for rows in (self.rows()[2:], self.rows()[:-1], self.rows()[::-1], self.rows()[:2]+self.rows()[3:]):
            with self.assertRaises(ValueError):
                interval_summary(rows,1000000,6000000)


if __name__ == '__main__':
    unittest.main()
