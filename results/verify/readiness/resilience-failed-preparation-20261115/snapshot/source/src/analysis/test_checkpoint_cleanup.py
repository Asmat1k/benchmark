import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class CheckpointCleanupTests(unittest.TestCase):
    def test_failed_run_harvests_checkpoint_before_removing_containers(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = base / 'container'
            fixture.mkdir()
            checkpoint = dict(status='partial', run_id='fixture', slots=[dict(seq='0')])
            (fixture / 'page.partial.json').write_text(json.dumps(checkpoint))
            series = base / 'series'
            partial = series / 'fixture.partial'
            partial.mkdir(parents=True)
            work = base / 'work'
            work.mkdir()
            script = '''set -eu
series_dir=$1
run_dir=$series_dir/fixture.partial
project=fixture
work=$2
fixture=$3
stage=browser
prepared=1
BENCH_RESILIENT_RUN=1
compose() {
    case "$1" in
        cp) cp "$fixture/${2#*:/tmp/}" "$3" ;;
        logs) echo server-log ;;
        exec) return 1 ;;
        down) rm -rf "$fixture" ;;
    esac
}
analyze() { touch "$series_dir/unexpected-analyze"; }
. "$4/docker/measurement-cleanup.sh"
trap cleanup EXIT
false
'''
            result = subprocess.run(['sh', '-c', script, 'test', str(series), str(work), str(fixture), str(root)], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            saved = series / 'quarantine/fixture/page.partial.json'
            self.assertEqual(json.loads(saved.read_text()), checkpoint)
            self.assertFalse(fixture.exists())
            self.assertFalse((series / 'STOP').exists())
            self.assertFalse((series / 'unexpected-analyze').exists())
