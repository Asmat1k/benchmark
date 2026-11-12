import contextlib
import io
import os
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_acceptance as fixtures
from admission import GATES, controller_session, ref, sources, validate_gate
from controller import dispatch
from raw import read,write
from acceptance import paired_schedule
from schedule import make_schedule,block_runs
from synthetic import SOURCE,make_fixture,rehash


class ControllerTests(unittest.TestCase):
    setUp=fixtures.AcceptanceTests.setUp
    tearDown=fixtures.AcceptanceTests.tearDown
    collection=fixtures.AcceptanceTests.collection
    primary=fixtures.AcceptanceTests.primary
    timer=fixtures.AcceptanceTests.timer
    probe=fixtures.AcceptanceTests.probe
    calibration_fixture=fixtures.AcceptanceTests.calibration_fixture
    generator_fixture=fixtures.AcceptanceTests.generator_fixture
    pairs=fixtures.AcceptanceTests.pairs
    produce=fixtures.AcceptanceTests.produce
    verification_fixture=fixtures.AcceptanceTests.verification_fixture

    def test_initial_copied_admission_commit_mismatch_refuses_ready(self):
        from controller import serve
        directory=self.root/'copied-admission';directory.mkdir()
        write(directory/'schedule.json',{})
        original=self.root/'accepted-admission.json'
        write(original,dict(kind='real',source_hashes=sources(),release_commit='a'*40))
        shutil.copyfile(original,directory/'admission.json')
        copied=read(directory/'admission.json');copied['release_commit']='b'*40
        write(directory/'admission.json',copied)
        output=io.StringIO()
        with patch('admission.release',return_value='a'*40),contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError,'initial admission release commit mismatch'):
                serve(directory)
        self.assertNotIn('ready',output.getvalue())

    def test_real_cli_forged_integrity_refuses_next_record_and_boot(self):
        directory=self.root/'forged';directory.mkdir()
        schedule=paired_schedule('aa',directory.name)
        for name,value in (('schedule.json',schedule),('schedule-original.json',schedule),('ledger.json',dict(schema_version=1,series_id=directory.name,attempts=schedule['blocks'])),('SYNTHETIC.json',dict(kind='synthetic'))):write(directory/name,value)
        evidence=Path('results/verify/acceptance/development/checks.json')
        environment=SOURCE/'context.json'
        checks=[]
        for gate in GATES:
            path=directory/(gate+'.json')
            write(path,dict(kind='real',gate=gate,status='passed',source_hashes=sources(),environment=ref(environment),result=dict(status='passed'),evidence=[ref(evidence)],integrity=dict(files={str(evidence.resolve()):ref(evidence)['sha256']},trees={})))
            checks.append(dict(id=gate,mandatory=True,expected='passed',actual='passed',units='gate',tolerance=None,status='passed',reason=None,utc='2026-11-12T00:00:00Z',evidence=[ref(path)]))
        verification=directory/'verify.json';write(verification,dict(kind='real',final=False,source_hashes=sources(),environment=ref(environment),document=dict(schema_version=1,checks=checks)))
        write(directory/'admission.json',dict(kind='real',phase='aa',source_hashes=sources(),schedule=ref(directory/'schedule-original.json'),verify=ref(verification),environment=ref(environment)))
        partial=directory/'partial';partial.mkdir()
        commands=([sys.executable,'-B','src/analysis/experiments.py','next','--output',str(directory),'--kind','real','--execute-real-experiments'],
                  [sys.executable,'-B','src/analysis/record.py','prepare',str(directory),'0',str(partial)])
        for command in commands:
            process=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(process.returncode,0,process.stdout)
        self.assertFalse((partial/'run.json').exists())
        (directory/'SYNTHETIC.json').unlink()
        process=subprocess.run([sys.executable,'-B','src/analysis/controller.py',str(directory)],input='',capture_output=True,text=True)
        self.assertNotEqual(process.returncode,0)
        self.assertNotIn('"value": "ready"',process.stdout)

    def test_memory_controller_deep_once_then_actual_fast_record_context(self):
        verification=self.verification_fixture()
        directory=self.root/'controlled'
        schedule=make_schedule('verify',directory.name,1,1)
        for block in schedule['blocks']:block.update(design='aa',modes=['WS','WS'])
        schedule['runs']=[r for i,b in enumerate(schedule['blocks']) for r in block_runs(schedule,b,i)]
        make_fixture(directory,schedule=schedule)
        write(directory/'schedule-original.json',schedule)
        ledger=read(directory/'ledger.json')
        for attempt in ledger['attempts']:attempt['status']='planned'
        write(directory/'ledger.json',ledger);(directory/'queue.json').unlink()
        first=schedule['runs'][0]
        for folder in (directory/'raw').iterdir():
            if folder.name!=first['run_id']:shutil.rmtree(folder)
        manifest=read(directory/'raw'/first['run_id']/'manifest.json')
        write(directory/'admission.json',dict(kind='synthetic',phase='aa',source_hashes=sources(),release_commit=manifest['commit'],schedule=ref(directory/'schedule-original.json'),verify=ref(verification),environment=ref(self.env)))
        partial=directory/'next.partial';partial.mkdir()
        context=directory/'context.partial';shutil.copytree(directory/'raw'/first['run_id'],context)
        fifo=self.root/'controller-input'
        os.mkfifo(fifo)
        response=self.root/'controller-output'
        script="""set -eu
%s -B -c 'import sys,os;sys.path.insert(0,"src/analysis");from controller import serve;from pathlib import Path;serve(Path(os.environ["CONTROLLER_TEST_DIR"]),"synthetic")' < "$CONTROLLER_TEST_FIFO" > "$BENCH_CONTROLLER_RESPONSE" &
BENCH_CONTROLLER_PID=$!
export BENCH_CONTROLLER_PID
exec 8> "$CONTROLLER_TEST_FIFO"
while [ ! -s "$BENCH_CONTROLLER_RESPONSE" ]; do kill -0 "$BENCH_CONTROLLER_PID"; sleep .1; done
. docker/controller-client.sh
controller_request '{"action":"next"}'
exec 8>&-
wait "$BENCH_CONTROLLER_PID"
""" % shlex.quote(sys.executable)
        process=subprocess.run(['/bin/sh','-c',script],env=dict(os.environ,CONTROLLER_TEST_DIR=str(directory),CONTROLLER_TEST_FIFO=str(fifo),BENCH_CONTROLLER_RESPONSE=str(response)),capture_output=True,text=True,timeout=120)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertEqual(process.stdout.strip(),'1')
        from experiments import evaluate as scientific_evaluate
        bootstrap=patch('experiments.evaluate',wraps=scientific_evaluate)
        initial=bootstrap.start()
        self.addCleanup(bootstrap.stop)
        with controller_session(directory,'synthetic'):
            self.assertCountEqual([call.args[0] for call in initial.call_args_list],['timer','calibrate','generator'])
            bootstrap.stop()
            with contextlib.ExitStack() as stack:
                for name in ('experiments.evaluate','raw.rows','inference.bootstrap','power.simulate'):
                    stack.enter_context(patch(name,side_effect=AssertionError('scientific recalculation '+name)))
                self.assertEqual(dispatch(directory,dict(action='next'),'synthetic'),(0,'1'))
                self.assertEqual(dispatch(directory,dict(action='prepare',index=1,partial=str(partial)),'synthetic')[0],0)
                for _ in range(2):self.assertEqual(dispatch(directory,dict(action='context',index=1,partial=str(context)),'synthetic')[0],0)
                trace=self.root/'build-locked-install.json';before=trace.read_bytes();trace.write_text('{}')
                with self.assertRaises(ValueError):dispatch(directory,dict(action='next'),'synthetic')
                trace.write_bytes(before)
                report_path=self.root/'build-calculated.json';document=read(report_path)
                document['integrity']['files'].pop(next(iter(document['integrity']['files'])))
                with self.assertRaises(ValueError):validate_gate(document,recalculate=False)
        with self.assertRaises(ValueError):dispatch(directory,dict(action='next'),'synthetic')
        with patch('experiments.evaluate',wraps=scientific_evaluate) as restarted:
            with controller_session(directory,'synthetic'):
                self.assertCountEqual([call.args[0] for call in restarted.call_args_list],['timer','calibrate','generator'])
                self.assertEqual(dispatch(directory,dict(action='next'),'synthetic'),(0,'1'))
