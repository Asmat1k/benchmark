import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from admission import validate_freeze
from raw import digest, read, validate_raw, write
from test_measurement import fixture, rehash


class ThresholdContractTest(unittest.TestCase):
    def test_boolean_states_preserve_numeric_contract(self):
        validator = Draft202012Validator(read(Path('docs/schemas/thresholds.schema.json')))
        original = read(Path('configs/thresholds.json'))
        for state in (True, False):
            value = dict(original, preliminary=state)
            validator.validate(value)
            value['calibration_margin_ms'] = 3
            self.assertFalse(validator.is_valid(value))
        for state in (None, 0, 1, 'false'):
            self.assertFalse(validator.is_valid(dict(original, preliminary=state)))

    def test_raw_accepts_both_states_with_matching_config_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fixture(directory)
            config_root = directory/'configs'
            config_root.mkdir()
            folder = directory/'raw/b0-a0-m0'
            for state in (True, False):
                config = read(folder/'config.json')
                config['thresholds']['preliminary'] = state
                for name, value in config.items():
                    write(config_root/f'{name}.json', value)
                write(folder/'config.json', config)
                manifest = read(folder/'manifest.json')
                manifest['config_sha256'] = digest(folder/'config.json')
                write(folder/'manifest.json', manifest)
                rehash(folder)
                validate_raw(folder, directory/'schedule.json', config_root)

    def test_freeze_still_requires_final_thresholds(self):
        bindings = {k: dict(path=k, sha256='a'*64) for k in
                    ('protocol','plan','profiles','thresholds','analysis','locks','environment','leaf_der',
                     'schedule','verify','pilot','power')}
        value = dict(schema_version=1, protocol_version=1, frozen_utc='2026-11-13T00:00:00Z',
                     release_commit='a'*40, dirty=False, bindings=bindings, blocks_per_profile=20,
                     include_wt_d=False, repeat_effect_ms=2, repeat_fullness_pp=1, kind='real',
                     source_hashes={}, leaf_pem='leaf.pem', series_end_utc='2026-11-14T00:00:00Z',
                     rationale='offline contract test',
                     aa_shift_algorithm='paired side2-side1; linear p95 absolute shifts')
        actual_read = read
        for state, error in ((True, 'final thresholds required'), (False, 'canonical config/protocol bindings')):
            def fixture_read(path):
                if path == Path('configs/thresholds.json'):
                    return dict(actual_read(path), preliminary=state)
                if path == Path('schedule'):
                    return dict(series_id='offline', runs=[])
                return actual_read(path)
            with patch('admission.read', side_effect=fixture_read), \
                    patch('admission.checked', side_effect=lambda r: Path(r['path'])), \
                    patch('admission.verify'), patch('admission.sources', return_value={}), \
                    patch('admission.release', return_value='a'*40), \
                    patch('admission.separate_frozen_schedule'), \
                    patch('admission.leaf_covers', return_value='a'*64), \
                    patch('admission.digest', return_value='a'*64), \
                    patch('admission.ref', return_value={}):
                with self.assertRaisesRegex(ValueError, error):
                    validate_freeze(value)


if __name__ == '__main__':
    unittest.main()
