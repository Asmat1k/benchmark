import json
import sys
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from execution.execution import VERSION, bounded_process, cleanup_run, collect, finish_run, load_outcomes, recover_artifacts, save_outcomes


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)
        (self.directory/'schedule.json').write_text(json.dumps(dict(runs=[dict(run_id=f'r{i}') for i in range(3)])))
        (self.directory/'admission.json').write_text(json.dumps(dict(execution_policy=VERSION,
            limits=dict(run_timeout_seconds=360,cleanup_timeout_seconds=30,series_budget_seconds=54000))))

    def test_failure_continues_and_resume_does_not_repeat(self):
        calls=[]
        def execute(index,out,err):
            calls.append(index)
            return 124 if index==1 else 0
        self.assertEqual(collect(self.directory,execute,lambda name:name!='r1',lambda name:None),0)
        self.assertEqual(calls,[0,1,2])
        rows=load_outcomes(self.directory)['runs']
        self.assertEqual([r['status'] for r in rows],['complete','failed','complete'])
        self.assertEqual(rows[1]['exit_code'],124)
        self.assertEqual(collect(self.directory,execute,lambda name:True,lambda name:None),0)
        self.assertEqual(calls,[0,1,2])
        with self.assertRaisesRegex(ValueError,'immutable'):
            finish_run(self.directory,0,'failed',2,'changed')

    def test_orphan_before_run_spec_is_cleaned_and_remains_attributed(self):
        folder=self.directory/'wswt-d3-wswt-measure-orphan.partial'
        folder.mkdir()
        load_outcomes(self.directory,create=True)
        recover_artifacts(self.directory,'r0')
        with patch('execution.execution.harvest_checkpoint') as harvest, patch('execution.execution.bounded_process',return_value=0) as down, patch('execution.execution.subprocess.run') as inspect:
            inspect.return_value.stdout=''
            cleanup_run(self.directory,'r0',30)
            self.assertEqual(harvest.call_args.args[:2],('wswt-d3-wswt-measure-orphan',folder))
            self.assertIn('down',down.call_args.args[0])
        finish_run(self.directory,0,'interrupted',130,'interrupted before prepare')
        self.assertEqual(load_outcomes(self.directory)['runs'][0]['artifacts'],[folder.name])

    def test_interrupted_current_run_preserved_remaining_run_executes(self):
        value=load_outcomes(self.directory,create=True)
        value['runs'][0]['status']='running'
        save_outcomes(self.directory,value)
        calls=[]
        collect(self.directory,lambda i,out,err:calls.append(i) or 0,lambda name:name!='r0',lambda name:None)
        self.assertEqual(calls,[1,2])
        self.assertEqual(load_outcomes(self.directory)['runs'][0]['status'],'interrupted')

    def test_crash_after_publication_recovers_complete_without_retry(self):
        value=load_outcomes(self.directory,create=True)
        value['runs'][0]['status']='running'
        save_outcomes(self.directory,value)
        calls=[]
        collect(self.directory,lambda i,out,err:calls.append(i) or 0,lambda name:True,lambda name:None)
        self.assertEqual(calls,[1,2])
        self.assertEqual(load_outcomes(self.directory)['runs'][0]['status'],'complete')

    def test_cleanup_failure_blocks_until_recovered(self):
        def broken(name): raise RuntimeError('cleanup failed')
        with self.assertRaisesRegex(RuntimeError,'cleanup failed'):
            collect(self.directory,lambda i,out,err:0,lambda name:False,broken)
        self.assertEqual(load_outcomes(self.directory)['runs'][0]['status'],'running')
        calls=[]
        collect(self.directory,lambda i,out,err:calls.append(i) or 0,lambda name:False,lambda name:None)
        self.assertEqual(calls,[1,2])
        self.assertEqual(load_outcomes(self.directory)['runs'][0]['status'],'interrupted')

    def test_budget_deadline_survives_resume(self):
        value=load_outcomes(self.directory,create=True)
        value['deadline_utc']='2000-01-01T00:00:00+00:00'
        save_outcomes(self.directory,value)
        calls=[]
        self.assertEqual(collect(self.directory,lambda i,out,err:calls.append(i) or 0,lambda name:False,lambda name:None),124)
        self.assertFalse(calls)
        self.assertEqual([r['status'] for r in load_outcomes(self.directory)['runs']],['planned']*3)

    def test_changed_schedule_and_journal_identity_refused(self):
        value=load_outcomes(self.directory,create=True)
        value['runs'][1]['run_id']='foreign'
        save_outcomes(self.directory,value)
        with self.assertRaisesRegex(ValueError,'identity'):
            load_outcomes(self.directory)

    def test_timeout_kills_process_group_before_next_run(self):
        marker=self.directory/'orphan'
        child='import time;from pathlib import Path;time.sleep(.4);Path('+repr(str(marker))+').touch()'
        parent='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(10)'
        self.assertEqual(bounded_process([sys.executable,'-c',parent],.15,.1),124)
        time.sleep(.5)
        self.assertFalse(marker.exists())
