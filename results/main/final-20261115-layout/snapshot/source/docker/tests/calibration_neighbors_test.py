import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


STUB = """import json, os, sys
args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as handle:
    handle.write(json.dumps(args)+'\\n')
if args[0]=='compose':
    args=args[1:]
    if args[:2]==['ps','-q']:
        print('container-'+args[2])
    elif 'cat' in args:
        role=args[2]
        target=args[-1]
        print({'browser':'02:00:00:00:10:10','server':'02:00:00:00:20:10'}.get(role,
              '02:00:00:00:10:02' if 'to_browser' in target else '02:00:00:00:20:02'))
elif 'replace' in args and os.environ.get('FAIL_REPLACE')=='1':
    sys.exit(5)
if 'show' in args:
    print('[]')
"""


class CalibrationNeighbors(unittest.TestCase):
    def run_neighbors(self, directory, fail=False):
        stub=directory/'stub.py'
        stub.write_text(STUB)
        docker=directory/'docker'
        docker.write_text('#!/bin/sh\nexec "$TEST_PYTHON" "$TEST_STUB" docker "$@"\n')
        docker.chmod(0o755)
        calls=directory/'calls.jsonl'
        result=subprocess.run(['/bin/sh','-ec',
            'compose() { "$TEST_PYTHON" "$TEST_STUB" compose "$@"; }; . docker/lib/calibration-neighbors.sh'],
            env=dict(os.environ,PATH=str(directory)+os.pathsep+os.environ['PATH'],
                     TEST_PYTHON=sys.executable,TEST_STUB=str(stub),CALLS=str(calls),
                     run_dir=str(directory),FAIL_REPLACE=str(int(fail))),capture_output=True,text=True)
        return result,[json.loads(line) for line in calls.read_text().splitlines()]

    def test_permanent_mappings_use_peer_mac_and_namespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            result,calls=self.run_neighbors(directory)
            self.assertEqual(result.returncode,0,result.stderr)
            changes=[c for c in calls if 'replace' in c]
            self.assertEqual(len(changes),4)
            for index,(role,subnet) in enumerate([('browser',10),('server',20)]):
                router,endpoint=changes[index*2:index*2+2]
                self.assertEqual(router,['compose','exec','-T','router','ip','neigh','replace',
                    f'172.28.{subnet}.10','lladdr',f'02:00:00:00:{subnet}:10','nud','permanent','dev',f'to_{role}'])
                self.assertEqual(endpoint,['docker','run','--rm','--cap-drop','ALL','--cap-add','NET_ADMIN',
                    '--network',f'container:container-{role}','--entrypoint','ip','wswt-bench-router:dev',
                    'neigh','replace',f'172.28.{subnet}.2','lladdr',f'02:00:00:00:{subnet}:02',
                    'nud','permanent','dev','bench0'])
                for filename in (f'router-{role}-neighbors.json',f'{role}-neighbors.json'):
                    self.assertEqual(json.loads((directory/filename).read_text()),[])

    def test_mapping_failure_stops_before_other_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            result,calls=self.run_neighbors(Path(temporary),fail=True)
            self.assertEqual(result.returncode,5)
            self.assertEqual(len([c for c in calls if 'replace' in c]),2)
            self.assertFalse(any(c[:4]==['compose','exec','-T','server'] for c in calls))


if __name__=='__main__':
    unittest.main()
