import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path('src/analysis').resolve()))

import test_analysis
from raw import digest, read, write
from synthetic import make_fixture, rehash
from series import context_snapshot


def current_protocol_fixture(*args, **kwargs):
    directory = make_fixture(*args, **kwargs)
    for folder in (directory / 'raw').iterdir():
        manifest = read(folder / 'manifest.json')
        manifest['protocol_sha256'] = digest(Path('docs/protocol.md'))
        write(folder / 'manifest.json', manifest)
        context = context_snapshot(folder)
        write(folder / 'context.json', context)
        write(directory / 'context.json', context)
        rehash(folder)
    return directory


test_analysis.make_fixture = current_protocol_fixture
print('SYNTHETIC ONLY: new temporary fixtures use current protocol hashes and recomputed synthetic contexts.', flush=True)
unittest.main(module=test_analysis, defaultTest='SeriesTests.test_null_profiles_and_mixed_release_are_not_silently_removed', verbosity=2)
