import copy
import tempfile
import unittest
from pathlib import Path

from reporting.outcomes import compute_outcomes, observations, paired_statistics
from measurement.raw import read, rows, write
from execution.schedule import make_schedule, seeds

import numpy as np

SOURCE = Path('results/verify/raw/finite-aa-20261115')


class AllOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.directory = Path(self.work.name)/'series'
        self.directory.mkdir()
        self.source = SOURCE/'raw/b5-a0-m0'
        self.schedule = read(SOURCE/'schedule.json')
        self.run = next(r for r in self.schedule['runs'] if r['run_id']=='b5-a0-m0')

    def checkpoint(self):
        folder=self.directory/'quarantine/crashed'
        folder.mkdir(parents=True)
        write(folder/'run.json',read(self.source/'run.json'))
        slots=rows(self.source/'slots.jsonl')
        first=copy.deepcopy(slots[0])
        second=copy.deepcopy(slots[1])
        for key in ('t_send_ms','send_lag_ms','api_return_ms','write_fulfilled_ms','first_correct_echo_ms','echo_bytes','queue_before_bytes','desired_size'):
            second[key]=None
        second.update(send_state='scheduler_miss',terminal_reason='scheduler_miss',completed_by_horizon=False,ontime=False)
        write(folder/'page.partial.json',dict(schema_version=1,status='partial',run_id=self.run['run_id'],
            captured_page_ms=first['first_correct_echo_ms'],slots=[first,second],events=[]))
        return folder

    def test_checkpoint_future_and_unobserved_slots_are_unknown_not_missing(self):
        summary,packets=observations(self.checkpoint(),self.run,1200)
        self.assertEqual(summary['observed_completed'],1)
        self.assertEqual(summary['unknown_slots'],1199)
        self.assertEqual(summary['observed_uncompleted_after_horizon'],0)
        self.assertIsNone(summary['U_observed_pct'])
        self.assertIsNone(summary['S_observed_pct'])
        self.assertEqual(len(packets),1)

    def test_interrupted_publication_falls_back_to_retained_checkpoint(self):
        folder=self.checkpoint()
        (folder/'slots.jsonl').write_text('{truncated')
        (folder/'page.json').write_text('{truncated')
        summary,packets=observations(folder,self.run,1200)
        self.assertEqual(summary['source'],'page.partial.json')
        self.assertEqual(len(summary['source_errors']),2)
        self.assertEqual(summary['observed_completed'],1)
        self.assertEqual(len(packets),1)

    def test_malformed_checkpoint_rejects_only_its_run_and_retains_all_assignments(self):
        folder=self.checkpoint()
        (folder/'page.partial.json').write_text('{incomplete')
        write(self.directory/'schedule.json',self.schedule)
        write(self.directory/'context.json',read(SOURCE/'context.json'))
        output=Path(self.work.name)/'output'
        output.mkdir()
        result=compute_outcomes(self.directory,output)
        self.assertEqual(result['planned_runs'],24)
        self.assertEqual(result['status_counts'],dict(not_run=23,rejected=1))
        self.assertEqual(result['unknown_planned_slots'],28800)
        item=next(r for r in result['runs'] if r['run_id']==self.run['run_id'])
        self.assertTrue(item['artifact_errors'])
        self.assertIsNone(item['Q_ms'])
        self.assertIsNone(item['U_pct'])
        self.assertTrue((output/'report.md').exists())

    def test_mixed_partial_and_corrupt_published_raw_survive_report(self):
        self.checkpoint()
        write(self.directory/'schedule.json',self.schedule)
        write(self.directory/'context.json',read(SOURCE/'context.json'))
        other=next(r for r in self.schedule['runs'] if r['run_id'] != self.run['run_id'])
        bad=self.directory/'raw'/other['run_id']
        bad.mkdir(parents=True)
        (bad/'run.json').write_text('broken')
        output=Path(self.work.name)/'output'
        output.mkdir()
        result=compute_outcomes(self.directory,output)
        self.assertEqual(result['status_counts'],dict(not_run=22,interrupted=1,rejected=1))
        self.assertEqual(result['accepted_totals']['completed'],0)
        self.assertEqual(result['unknown_planned_slots'],28800)
        partial=next(r for r in result['runs'] if r['run_id']==self.run['run_id'])
        self.assertEqual(partial['observations']['observed_completed'],1)
        self.assertIsNone(partial['Q_ms'])

    def test_real_stopped_aa_preserves_14_complete_1_rejected_9_not_run(self):
        output=Path(self.work.name)/'actual-aa-report'
        output.mkdir()
        result=compute_outcomes(SOURCE,output)
        self.assertEqual(result['planned_runs'],24)
        self.assertEqual(result['status_counts'],dict(complete=14,rejected=1,not_run=9))
        self.assertEqual(result['planned_slots'],28800)
        self.assertEqual(result['accepted_totals']['planned_slots'],16800)
        self.assertEqual(result['unknown_planned_slots'],12000)
        rejected=next(r for r in result['runs'] if r['status']=='rejected')
        self.assertEqual(rejected['observations']['recorded_slot_rows'],1200)
        self.assertIsNone(rejected['Q_ms'])
        self.assertIsNotNone(rejected['observations']['Q_observed_ms'])
        self.assertTrue(all(p['inference']=='unavailable' for p in result['profiles']))
        self.assertEqual(len(read(output/'analysis.json')['runs']),24)
        self.assertTrue((output/'figures/runs.png').exists())
        self.assertTrue((output/'figures/outcomes.svg').exists())

    def test_hash_corruption_cannot_produce_observed_rtt(self):
        folder=self.checkpoint()
        (folder/'SHA256SUMS').write_text('0'*64+'  page.partial.json\n')
        write(self.directory/'schedule.json',self.schedule)
        write(self.directory/'context.json',read(SOURCE/'context.json'))
        output=Path(self.work.name)/'output'
        output.mkdir()
        result=compute_outcomes(self.directory,output)
        item=next(r for r in result['runs'] if r['run_id']==self.run['run_id'])
        self.assertEqual(item['status'],'rejected')
        self.assertIsNone(item['observations'])

    def test_late_after_horizon_reply_remains_in_packet_csv(self):
        folder=self.checkpoint()
        checkpoint=read(folder/'page.partial.json')
        slot=checkpoint['slots'][0]
        slot['first_correct_echo_ms']=slot['t_plan_ms']+5010
        slot['completed_by_horizon']=False
        slot['ontime']=False
        checkpoint['captured_page_ms']=slot['first_correct_echo_ms']
        write(folder/'page.partial.json',checkpoint)
        write(self.directory/'schedule.json',self.schedule)
        write(self.directory/'context.json',read(SOURCE/'context.json'))
        output=Path(self.work.name)/'output'
        output.mkdir()
        result=compute_outcomes(self.directory,output)
        item=next(item for item in result['runs'] if item['run_id']==self.run['run_id'])
        self.assertEqual(item['observations']['observed_completed'],0)
        self.assertEqual(item['observations']['observed_late_after_horizon'],1)
        self.assertIsNone(item['observations']['Q_observed_ms'])
        self.assertIn('late_after_horizon',(output/'rtt.csv').read_text())

    def statistical_items(self):
        schedule=make_schedule('main','statistical-test-v2',20,4,True)
        items=[dict(run_id=run['run_id'],attempt_id=run['attempt_id'],profile=run['profile'],mode=run['mode'],
            status='complete',Q_ms={'WS':20,'WT-S':10,'WT-D':25}[run['mode']],
            S_pct={'WS':100,'WT-S':99.5,'WT-D':98}[run['mode']],U_pct=.5,metrics=dict(disconnects=0)) for run in schedule['runs']]
        config={name:read(Path(f'configs/{name}.json')) for name in ('plan','thresholds')}
        return schedule,items,config

    def test_full_main_retains_exact_sign_holm_rank_and_seeded_bootstrap(self):
        schedule,items,config=self.statistical_items()
        output=Path(self.work.name)/'statistics'
        output.mkdir()
        result=paired_statistics(schedule,items,config,output)
        self.assertEqual(result['status'],'available')
        self.assertEqual(len(result['pairs']),80)
        for profile in result['profiles']:
            self.assertEqual(profile['n'],20)
            self.assertEqual(profile['theta_ms'],-10)
            self.assertEqual(profile['sign']['p_raw'],2/2**20)
            self.assertEqual(profile['sign']['p_Holm'],8/2**20)
            self.assertEqual(profile['CI9875']['bounds'],[-10,-10])
            self.assertEqual(profile['fullness']['bounds'],[-.5,-.5])
            self.assertEqual(profile['WT_D']['Q']['bounds'],[25,25])
            self.assertEqual(profile['useful_gain'],'WT-S')
        rng=seeds('main',schedule['series_id'],6,0)
        expected=rng.integers(0,20,size=(config['plan']['bootstrap_replicates'],20))
        actual=np.load(output/'bootstrap-r20p0.npz')['indices']
        np.testing.assert_array_equal(actual,expected)

    def test_failed_or_null_main_run_never_uses_other_complete_pairs(self):
        schedule,items,config=self.statistical_items()
        output=Path(self.work.name)/'statistics'
        output.mkdir()
        items[0]['status']='failed'
        self.assertEqual(paired_statistics(schedule,items,config,output)['status'],'unavailable')
        items[0]['status']='complete'
        items[0]['Q_ms']=None
        self.assertEqual(paired_statistics(schedule,items,config,output)['status'],'unavailable')
        self.assertEqual(list(output.iterdir()),[])
