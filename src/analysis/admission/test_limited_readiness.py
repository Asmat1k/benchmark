import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from admission.acceptance import control_smoke, paired_schedule
from admission.admission import GATES, accepted_schedule, ref, validate_reproduction_outcome
from admission.limited_readiness import historical_report, verify_limited
from measurement.raw import read, write
from execution.schedule import MODES, PROFILES, make_schedule


class FiniteReadinessTests(unittest.TestCase):
    def pairs(self):
        result=[]
        for mode in MODES:
            for profile in PROFILES:
                sides=[dict(run_id=f'{mode}-{profile}-{i}',mode=mode,seeds=[i,i+1],
                            Q_ms=10+i*100,S_pct=100-i*5,U_pct=0,disconnects=0) for i in range(2)]
                result.append(dict(mode=mode,profile=profile,attempt_id=f'{mode}-{profile}',
                                   fresh_processes=True,independence_reviewed=False,sides=sides))
        return result

    def test_smoke_is_fixed_inconclusive_even_with_large_shift(self):
        result=control_smoke(self.pairs(),'aa')
        self.assertEqual(result['status'],'inconclusive')
        self.assertEqual(len(result['groups']),12)
        self.assertEqual(result['repeat_effect_ms'],2)
        self.assertEqual(result['repeat_fullness_pp'],1)
        self.assertTrue(all(g['n']==1 and g['Q_shift_ms']==100 for g in result['groups']))
        with self.assertRaisesRegex(ValueError,'one smoke pair'):
            control_smoke(self.pairs()[:-1],'aa')
        pairs=self.pairs();pairs[0]['fresh_processes']=False
        with self.assertRaisesRegex(ValueError,'fresh processes'):
            control_smoke(pairs,'aa')

    def test_legacy_schedule_rejects_reduced_count_and_finite_accepts_exact_design(self):
        with self.assertRaisesRegex(ValueError,'fixed control sample'):
            paired_schedule('aa','test',True,1)
        schedule=paired_schedule('aa','test',True,1,smoke=True)
        self.assertEqual(len(schedule['runs']),24)
        self.assertEqual({b['session_id'] for b in schedule['blocks']},{'s0'})
        accepted_schedule(schedule,'aa',finite=True)
        with self.assertRaises(ValueError):
            accepted_schedule(schedule,'aa')
        changed=make_schedule('pilot','pilot',6,4,True)
        with self.assertRaisesRegex(ValueError,'planned block count'):
            accepted_schedule(changed,'pilot',finite=True)

    def test_failed_scientific_repeat_does_not_hide_failed_technical_predicate(self):
        from admission.collection import PRIMARY_IDS
        from measurement.raw import now
        document=dict(schema_version=1,checks=[dict(id=key,mandatory=True,expected=True,actual=True,
            units='predicate',tolerance=None,status='passed',reason=None,utc=now(),evidence=[ref(Path('configs/contracts/protocol.json'))])
            for key in PRIMARY_IDS['reproduction']])
        report=dict(status='failed',result=dict(document=document,comparison=dict(status='failed')))
        with self.assertRaisesRegex(ValueError,'independent reproduction'):
            validate_reproduction_outcome(report)
        validate_reproduction_outcome(report,finite=True)
        document['checks'][0]['status']='failed'
        document['checks'][0]['actual']=False
        with self.assertRaisesRegex(ValueError,'technical/review predicates'):
            validate_reproduction_outcome(report,finite=True)

    def test_unexpected_runtime_source_change_cannot_reuse_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'report.json'
            write(path,dict(source_hashes={'src/client/src/measurement.ts':'old'}))
            with patch('admission.limited_readiness.sources',return_value={'src/client/src/measurement.ts':'new'}):
                with self.assertRaisesRegex(ValueError,'unexpected historical source change'):
                    historical_report(dict(report=ref(path)),{})

    def test_historical_cache_requires_deep_issue_and_detects_changed_evidence(self):
        from admission.limited_readiness import _HISTORICAL_APPROVED
        from admission.admission import evidence_closure
        _HISTORICAL_APPROVED.clear()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            env,report_path,receipt_path,stdout,stderr,runner = [root/name for name in
                ('env.json','report.json','receipt.json','stdout.json','stderr.log','runner.py')]
            context=dict(host='host',vm={},leaf='leaf',services=[],config=dict(plan={},profiles={},thresholds={}),bindings={})
            write(env,context)
            report=dict(kind='real',gate='calibration',status='failed',result=dict(status='failed'),
                        environment=ref(env),source_hashes={},evidence=[],integrity=evidence_closure([env]))
            write(report_path,report)
            runner.write_text('exact old-source replay runner')
            stderr.write_text('')
            write(stdout,dict(validated_report=ref(report_path),source_hashes={},environment=ref(env),status='failed'))
            write(receipt_path,dict(schema_version=1,validation='validate-gate-exact-source-v1',
                report=ref(report_path),source_hashes={},environment=ref(env),historical_status='failed',exit=0,
                started_utc='2026-11-15T00:00:00Z',ended_utc='2026-11-15T00:00:01Z',
                runner=ref(runner),stdout=ref(stdout),stderr=ref(stderr)))
            binding=dict(report=ref(report_path),replay=ref(receipt_path))
            with patch('admission.limited_readiness.sources',return_value={}):
                with self.assertRaisesRegex(ValueError,'initial deep'):
                    historical_report(binding,context,recalculate=False)
                self.assertEqual(historical_report(binding,context)['status'],'failed')
                self.assertEqual(historical_report(binding,context,recalculate=False)['status'],'failed')
                stderr.write_text('mutated after validation')
                with self.assertRaisesRegex(ValueError,'hash mismatch'):
                    historical_report(binding,context,recalculate=False)

    def test_final_readiness_cannot_hide_not_run_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            env=Path(temporary)/'env.json';write(env,{})
            report=dict(kind='real',readiness_version='finite-browser-study-v1',source_hashes={},
                environment=ref(env),final=True,policy={},gate_bindings={},document=dict(checks=[
                    dict(id=key,mandatory=True,status='not_run',evidence=[],actual=None) for key in GATES]))
            with patch('admission.limited_readiness.sources',return_value={}), \
                 patch('admission.limited_readiness.policy'), patch('admission.limited_readiness.current_environment',return_value={}):
                with self.assertRaisesRegex(ValueError,'required evidence not collected'):
                    verify_limited(report,env,True,GATES)

    def test_source_and_scope_changes_reject_before_any_historical_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            env=Path(temporary)/'env.json';write(env,{})
            report=dict(kind='real',readiness_version='finite-browser-study-v1',source_hashes={},
                        environment=ref(env),final=False)
            with patch('admission.limited_readiness.sources',return_value={'current':'source'}):
                with self.assertRaisesRegex(ValueError,'source/environment/scope'):
                    verify_limited(report,env,False,())
            with patch('admission.limited_readiness.sources',return_value={}):
                with self.assertRaisesRegex(ValueError,'source/environment/scope'):
                    verify_limited(report,env,True,())


if __name__=='__main__':
    unittest.main()
