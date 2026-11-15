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
        write(self.directory/'policy.md', dict(historical=dict(calibration='failed', generator='failed', aa='partial')))
        write(self.directory/'policy.json', dict(execution_policy=exploratory.VERSION, document=ref(self.directory/'policy.md')))
        write(self.directory/'env.json', {})
        (self.directory/'leaf.pem').write_text('actual-leaf')
        history = dict(calibration='failed', generator='failed', aa='partial')
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

    def test_historical_status_tamper_rejected(self):
        self.value['history']['calibration'] = 'passed'
        write(self.directory/'admission.json', self.value)
        with self.assertRaisesRegex(ValueError, 'historical disclosure changed'):
            admit(self.directory)

    def test_prepare_without_historical_results(self):
        directory = Path('results/main/clean-main')
        policy = Path('configs/policies/exploratory.json')
        policy.parent.mkdir(parents=True)
        write(policy, dict(execution_policy=exploratory.VERSION,
            historical=dict(calibration='failed', generator='failed', aa='partial')))
        leaf = Path('build/tls/server/good/cert.pem')
        leaf.parent.mkdir(parents=True)
        leaf.write_text('actual-leaf')
        self.sources.return_value = {str(policy): ref(policy)['sha256']}
        with patch.dict(os.environ, BENCH_RELEASE_COMMIT='a'*40):
            exploratory.prepare(directory, self.directory/'env.json', Path('build/tls'))
        self.assertEqual(read(directory/'admission.json')['history'], self.value['history'])
        self.assertFalse(Path('results/verify').exists())

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
