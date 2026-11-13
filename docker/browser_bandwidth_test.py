import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from browser_bandwidth import fractions, load_rates, package
from schedule import make_schedule


class BandwidthTest(unittest.TestCase):
    def test_package_rejects_foreign_sources_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostic, calibration = root/'diagnostic', root/'calibration'
            diagnostic.mkdir()
            calibration.mkdir()
            schedule = make_schedule('diagnostic', diagnostic.name, 1, 1, datagrams=True, baseline=True)
            schedule['generator_hz'] = 20
            (diagnostic/'schedule.json').write_text(json.dumps(schedule))
            (diagnostic/'ledger.json').write_text(json.dumps(dict(schema_version=1, series_id=diagnostic.name,
                attempts=[dict(b,status='complete') for b in schedule['blocks']])))
            for phase in ('before', 'after'):
                (calibration/f'sources-{phase}.json').write_text(json.dumps(dict(foreign='hash')))
            with patch('browser_bandwidth.sources', return_value={}):
                with self.assertRaisesRegex(ValueError, 'source mismatch'): package(diagnostic, calibration)
                for phase in ('before', 'after'):
                    (calibration/f'sources-{phase}.json').write_text('{}')
                    (calibration/f'context-{phase}.json').write_text('{"foreign":true}')
                (diagnostic/'context.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'environment mismatch'): package(diagnostic, calibration)

    def test_counters_include_both_directions_and_all_run_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'run.json').write_text(json.dumps(dict(warmup_slots=200, measurement_slots=1200, interval_ms=50)))
            row = json.dumps(dict(send_state='sent', first_correct_echo_ms=1))+'\n'
            (folder/'warmup.jsonl').write_text(row*200)
            (folder/'slots.jsonl').write_text(row*1200)
            first = [dict(kind='netem', dev=dev, bytes=100, packets=1, drops=0, qlen=0, backlog=0,
                          handle='10:', options=dict(rate=1250000)) for dev in ('to_server','to_browser')]
            last = [dict(q, bytes=100+(i+1)*750000, packets=1401) for i,q in enumerate(first)]
            for when, value in (('before', first), ('stable', last)):
                (folder/f'qdisc-{when}.json').write_text(json.dumps(value))
            result = load_rates(folder)
            self.assertEqual([r['mbit_s_upper'] for r in result], [.1, .2])
            self.assertEqual([r['denominator_s'] for r in result], [60,60])
            for field, value, error in (('bytes', 99, 'counters'), ('drops', 1, 'loss'),
                                        ('backlog', 1, 'undrained'), ('handle','20:','changed')):
                changed = copy.deepcopy(last)
                changed[0][field] = value
                (folder/'qdisc-stable.json').write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, error): load_rates(folder)
            (folder/'qdisc-stable.json').write_text(json.dumps(last))
            (folder/'slots.jsonl').write_text(row*1199+json.dumps(dict(send_state='scheduler_miss',first_correct_echo_ms=None))+'\n')
            with self.assertRaisesRegex(ValueError, 'incomplete'): load_rates(folder)

    def test_directional_conservative_denominator_and_strict_boundary(self):
        capacity = [dict(loss=loss, direction=d, forwarded_bytes=rate*1e6*60/8, duration_s=60)
                    for loss,rate in ((0,10),(.01,9)) for d in ('forward','reverse')]
        for offered, status in ((.899999,'passed'),(.9,'failed'),(.900001,'failed')):
            loads = [dict(mode=m, rates=[dict(direction=d, mbit_s_upper=offered)
                                        for d in ('forward','reverse')]) for m in ('WS','WT-S','WT-D')]
            result = fractions(loads, capacity)
            self.assertEqual(result['status'], status)
            self.assertAlmostEqual(result['main_bandwidth_fraction'], offered/9)
        with self.assertRaisesRegex(ValueError, 'all approved'): fractions(loads[:1], capacity)
        with self.assertRaisesRegex(ValueError, 'coverage'): fractions(loads, capacity[:2])
        capacity[0]['forwarded_bytes'] = 0
        with self.assertRaisesRegex(ValueError, 'outside'): fractions(loads, capacity)


if __name__ == '__main__':
    unittest.main()
