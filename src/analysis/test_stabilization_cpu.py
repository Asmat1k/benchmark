import copy
import unittest

from stabilization_cpu import compare, quiet_summary


class QuietCpuTests(unittest.TestCase):
    def records(self):
        return [dict(schema_version=1,run_id="quiet-test",throttled_usec=0,memory_current=1000,role=role,sample_index=i-1,end_usec=i*1000000+500000,interval_usec=1000000,
                     cpu_usage_usec=5000,oom=0,cpu_start_lower_usec=i*1000000-500000,
                     cpu_end_upper_usec=i*1000000+510000)
                for role in ('browser','server','router') for i in range(1,6)]

    def test_complete_brackets_exclude_observer_but_retain_raw(self):
        rows = self.records()
        for row in rows:
            if row['sample_index'] in (0,3,4): row['cpu_usage_usec']=250000
        before = copy.deepcopy(rows)
        result = quiet_summary(rows,1000000)
        self.assertEqual(rows,before)
        self.assertTrue(all(r['count']==2 and r['peak_ceil_pct']==1 for r in result['roles'].values()))
        self.assertEqual([r['sample_index'] for r in result['roles']['router']['selected']],[1,2])
        self.assertEqual(compare(result,result)['status'],'passed')
        idle = copy.deepcopy(result)
        idle['roles']['router']['peak_ceil_pct']=2
        self.assertEqual(compare(result,idle)['status'],'failed')

    def test_cpu_read_delay_and_clock_boundaries_are_not_selected(self):
        rows = self.records()
        rows[1]['cpu_start_lower_usec']=900000
        with self.assertRaisesRegex(ValueError,'insufficient complete'):
            quiet_summary(rows,1000000)
        rows = self.records()
        rows[2]['cpu_end_upper_usec']=4500000
        with self.assertRaisesRegex(ValueError,'insufficient complete'):
            quiet_summary(rows,1000000)

    def test_missing_stale_gaps_and_unbracketed_cannot_pass(self):
        for mutation in ('missing','stale','gap','brackets'):
            rows = self.records()
            if mutation=='missing': rows=[r for r in rows if r['role']!='router']
            if mutation=='stale': rows=[r for r in rows if r['sample_index']<3]
            if mutation=='gap': rows.pop(2)
            if mutation=='brackets': del rows[0]['cpu_start_lower_usec']
            from jsonschema import ValidationError
            with self.assertRaises((ValueError,KeyError,ValidationError)):
                quiet_summary(rows,1000000)

    def test_invalid_cpu_and_mixed_identity_never_pass(self):
        from jsonschema import ValidationError
        for value in (-1,float('nan'),True):
            records = self.records()
            records[1]['cpu_usage_usec']=value
            with self.assertRaises(ValidationError): quiet_summary(records,1000000)
        records = self.records()
        records[1]['run_id']='another'
        with self.assertRaisesRegex(ValueError,'identity'): quiet_summary(records,1000000)

    def test_actual_sampler_produces_compatible_bracketed_rows(self):
        import json
        import subprocess
        from pathlib import Path
        from jsonschema import Draft202012Validator
        from raw import read
        result = subprocess.run(['timeout','4','sh','docker/sample.sh'],env=dict(__import__('os').environ,ROLE='browser',RUN_ID='sample-test'),capture_output=True,text=True)
        self.assertEqual(result.returncode,124,result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertGreaterEqual(len(rows),2)
        validator = Draft202012Validator(read(Path('docs/schemas/resource.schema.json')))
        for row in rows:
            validator.validate(row)
            self.assertLessEqual(row['cpu_start_lower_usec'],row['end_usec']-row['interval_usec'])
            self.assertEqual(row['cpu_end_upper_usec'],row['end_usec']+10000)


if __name__ == '__main__':
    unittest.main()
