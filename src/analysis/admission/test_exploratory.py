import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from admission import exploratory
from admission.admission import admit, ref
from measurement.raw import read, write
from execution.schedule import make_schedule


class ExploratoryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.previous = Path.cwd()
        os.chdir(self.work.name)
        self.addCleanup(os.chdir, self.previous)
        self.addCleanup(self.work.cleanup)
        self.directory = Path('results/main/fixed-main')
        self.directory.mkdir(parents=True)
        self.schedule = make_schedule('main', self.directory.name, 20, 4, True)
        write(self.directory/'schedule.json', self.schedule)
        write(self.directory/'frozen-schedule.json', self.schedule)
        write(self.directory/'ledger.json', dict(schema_version=1, series_id=self.directory.name, attempts=self.schedule['blocks']))
        (self.directory/'policy.md').write_text('fixed exploratory policy')
        write(self.directory/'policy.json', dict(execution_policy=exploratory.VERSION, document=ref(self.directory/'policy.md')))
        write(self.directory/'env.json', {})
        (self.directory/'leaf.pem').write_text('actual-leaf')
        history = {}
        for gate in exploratory.HISTORY:
            path = self.directory/(gate+'.json')
            write(path, dict(gate=gate, status='failed' if gate != 'aa' else 'partial'))
            history[gate] = ref(path)
        self.value = dict(schema_version=1, kind='real', phase='main', execution_policy=exploratory.VERSION,
            source_hashes={'actual.py':'actual-sha'}, schedule=ref(self.directory/'frozen-schedule.json'),
            policy=ref(self.directory/'policy.json'), limits=exploratory.LIMITS,
            environment=ref(self.directory/'env.json'), history=history,
            unperformed=['monitoring','pilot','power','reproduction'],
            limitations='exploratory-observed-system-no-confirmatory-readiness-or-power-claim',
            leaf_pem=str(self.directory/'leaf.pem'), series_end_utc='2099-01-01T00:00:00+00:00')
        write(self.directory/'admission.json', self.value)
        self.sources = patch('admission.exploratory.sources', return_value={'actual.py':'actual-sha'}).start()
        patch('admission.exploratory.current_environment', return_value={'leaf':'actual-leaf'}).start()
        patch('admission.exploratory.leaf_covers', return_value='leaf-sha').start()
        self.addCleanup(patch.stopall)

    def test_failed_history_and_unperformed_stages_allow_explicit_exploratory_scope(self):
        result = admit(self.directory)
        self.assertEqual(result['execution_policy'], exploratory.VERSION)
        self.assertEqual(len(read(self.directory/'schedule.json')['runs']), 240)
        self.assertEqual(result['history'], self.value['history'])

    def test_source_tamper_rejected_before_run(self):
        self.sources.return_value = {'actual.py':'changed-sha'}
        with self.assertRaisesRegex(ValueError, 'source changed'):
            admit(self.directory)

    def test_schedule_shortening_rejected(self):
        changed = copy.deepcopy(self.schedule)
        changed['runs'].pop()
        write(self.directory/'schedule.json', changed)
        with self.assertRaisesRegex(ValueError, 'fixed schedule changed'):
            admit(self.directory)

    def test_historical_report_tamper_rejected(self):
        write(self.directory/'calibration.json', dict(gate='calibration', status='passed'))
        with self.assertRaisesRegex(ValueError, 'evidence hash mismatch'):
            admit(self.directory)

    def test_measured_environment_leaf_must_match_mounted_leaf(self):
        (self.directory/'leaf.pem').write_text('other-leaf')
        with self.assertRaisesRegex(ValueError, 'TLS differs'):
            admit(self.directory)

    def test_synthetic_marker_cannot_use_real_exploratory_admission(self):
        (self.directory/'SYNTHETIC.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'synthetic main forbidden'):
            admit(self.directory)


if __name__ == '__main__':
    unittest.main()
