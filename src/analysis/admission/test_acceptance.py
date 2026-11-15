import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from admission.acceptance import calibration, equivalence, exact_binomial, generator_gate, paired_schedule, timer_gate
from admission.admission import GATES, admit, aggregate, checked, execution_state, leaf_covers, phase_path, ref, release, sources, validate_gate, validate_schedule_extension, verify
from admission.collection import PRIMARY_IDS, environment, imported
from execution.experiments import completed_series, report
from reporting.power import simulate
from measurement.raw import digest, read, write
from execution.schedule import PROFILES, block_runs, make_schedule


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.env=self.root/'ENV.json'
        write(self.env,dict(kind='synthetic',purpose='isolated offline D5 fixture'))

    def tearDown(self):
        self.temp.cleanup()

    def cli(self,*args):
        return subprocess.run([sys.executable,'-B','-m','execution.experiments',*map(str,args)],capture_output=True,text=True)

    def collection(self,gate,values,extra=None):
        identity='fixture-'+gate
        common=dict(kind='synthetic',gate=gate,collection_id=identity,environment=ref(self.env),source_hashes=sources())
        payload=self.root/(gate+'-primary.json')
        write(payload,dict(collection_id=identity,gate=gate,**({} if extra and 'document' in extra else {'values':values}),**(extra or {})))
        collection=self.root/(gate+'-collection.json')
        write(collection,dict(common,payload=ref(payload)))
        data=dict(common,**values,collection=ref(collection),evidence=[ref(payload),ref(collection)])
        path=self.root/(gate+'-input.json')
        write(path,data)
        return path

    def primary(self,gate):
        identity='fixture-'+gate
        observations={}
        checks=[]
        for identifier in PRIMARY_IDS[gate]:
            trace=self.root/(gate+'-'+identifier+'.json')
            write(trace,dict(collection_id=identity,gate=gate,id=identifier,actual=True))
            observation=dict(collection_id=identity,id=identifier,actual=True,expected=True,status='passed',evidence=[ref(trace)])
            observations[identifier]=observation
            checks.append(dict(id=identifier,mandatory=True,actual=True,expected=True,status='passed',evidence=[ref(trace)],
                               units='predicate',tolerance=0,reason=None,utc='2026-11-11T00:00:00Z'))
        document=dict(schema_version=1,checks=checks)
        path=self.collection(gate,dict(document=document),dict(document=document,observations=observations))
        return path

    def timer(self):
        clock=np.arange(100001,dtype=float)/100
        delta=np.diff(clock)
        values=dict(count=100000,monotonic=True,step_ms=float(min(delta)),p99_overhead_ms=float(np.sort(delta)[98999]))
        return self.collection('timer',values,dict(clock_samples_ms=clock.tolist()))

    def probe(self,returned=10000,rtt=1):
        return dict(sent_records=[dict(id=i,t_plan_ms=i*10,t_send_ms=i*10) for i in range(10000)],
                    reply_records=[dict(id=i,rtt_ms=rtt) for i in range(10000-returned,10000)])

    def calibration_fixture(self):
        echo={}
        for key in ('before','after',*PROFILES):
            value=1 if key in ('before','after') else 21 if key.startswith('r20') else 81
            count=9801 if key.endswith('p1') else 10000
            echo[key]=dict(collection_id='latency-'+key,sent=10000,frame_bytes=256,frequency_hz=100,rtt_ms=[value]*count,**self.probe(count,value))
        egress=[]
        for profile in PROFILES:
            for when in ('before','after'):
                lossy=profile.endswith('p1')
                probe=self.probe(9801 if lossy else 10000)
                for direction in ('forward','reverse'):
                    entered=list(range(100 if lossy and direction=='reverse' else 0,10000))
                    drops=list(range(100 if direction=='reverse' else 0,199 if direction=='reverse' else 100)) if lossy else []
                    egress.append(dict(profile=profile,when=when,direction=direction,entered_ids=entered,dropped_ids=drops,
                                       collection_id='loss-'+profile+'-'+when,probe=probe))
        saturation=[dict(loss=p,direction=d,duration_s=60,offered_bytes=90000000,forwarded_bytes=75000000,accounting_level='tc IP bytes') for p in (0,.01) for d in ('forward','reverse')]
        trace_review={k:True for k in ('independent_units','mtu_1500','no_fragmentation','no_unexpected_overflow','headers_accounted','survivor_bias_reviewed','reverse_denominator_reviewed','independent_direction_seeds','backlog_reviewed')}
        trace_review['main_bandwidth_fraction']=.01
        return dict(echo=echo,egress=egress,saturation=saturation,trace_review=trace_review)

    def generator_fixture(self):
        runs=[]
        for frequency in (20,100):
            slots=[dict(t_plan_ms=i*1000/frequency,t_send_ms=i*1000/frequency,send_state='sent') for i in range(1200)]
            samples=[dict(role=role,sample_index=i,end_usec=(i+1)*1000000,interval_usec=1000000,cpu_usage_usec=200000,throttled_usec=0,oom=0,cpu_limit=2) for role in ('browser','server','router') for i in range(60)]
            runs.append(dict(frequency_hz=frequency,profile='baseline',measurement_slots=1200,resources_complete=True,router_backlog_reviewed=True,
                miss=0,oom=0,browser_cpu_pct_limit=10,server_cpu_pct_limit=10,browser_throttling_pct=0,server_throttling_pct=0,
                lag_p99_ms=0,observed_hz=frequency,slots=slots,resource_samples=samples,resource_window=dict(start_usec=0,end_usec=60000000)))
        return runs

    def pairs(self,kind):
        schedule=paired_schedule(kind,'roundtrip-'+kind)
        result=[]
        for block in schedule['blocks']:
            sides=[dict(run_id=r['run_id'],mode=r['mode'],seeds=[r['forward_seed'],r['reverse_seed']],monitoring=r.get('monitoring')=='on',Q_ms=10,S_pct=100,U_pct=0,disconnects=0) for r in schedule['runs'] if r['attempt_id']==block['attempt_id']]
            result.append(dict(attempt_id=block['attempt_id'],mode=block['modes'][0],profile=block['profile'],fresh_processes=True,independence_reviewed=True,sides=sides))
        return result

    def test_r1_persisted_calibration_roundtrip_and_tamper(self):
        path=self.collection('calibration',self.calibration_fixture())
        output=self.root/'calibration-report.json'
        result=self.cli('calibrate','--input',path,'--output',output,'--environment',self.env)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        validate_gate(read(output))
        changed=read(output)
        changed['result']['expected_echo_loss']=0
        with self.assertRaisesRegex(ValueError,'calculation'): validate_gate(changed)
        data=read(path)
        data['trace_review']['independent_units']=False
        payload=read(checked(read(checked(data['collection']))['payload']))
        payload['values']['trace_review']['independent_units']=False
        self.assertEqual(calibration(data)['status'],'inconclusive')

    def test_r1_persisted_aa_monitoring_roundtrip(self):
        for kind in ('aa','monitoring'):
            path=self.collection(kind,dict(design=kind,pairs=self.pairs(kind)))
            output=self.root/(kind+'-report.json')
            result=self.cli(kind,'--input',path,'--output',output,'--environment',self.env)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            validate_gate(read(output))
            document=read(output)
            document['result']['groups'][0]['n']=21
            with self.assertRaises(ValueError): validate_gate(document)

    def test_r2_primary_subject_trace_coverage_and_synthetic_rejection(self):
        for gate in ('build','tls','path','raw','analysis'):
            path=self.primary(gate)
            output=self.root/(gate+'-report.json')
            result=self.cli('import-checks','--input',path,'--output',output,'--environment',self.env)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            validate_gate(read(output))
            with self.assertRaisesRegex(ValueError,'synthetic environment'): aggregate({gate:str(output)},self.env)
            data=read(path)
            data['gate']='analysis' if gate!='analysis' else 'tls'
            with self.assertRaises(ValueError): imported(data)
        data=read(self.primary('tls'))
        data['document']['checks'].pop()
        with self.assertRaises(ValueError): imported(data)
        data=read(self.primary('path'))
        trace=checked(data['document']['checks'][0]['evidence'][0])
        wrong=read(trace); wrong['collection_id']='another'; write(trace,wrong)
        with self.assertRaises(ValueError): imported(data)

    def test_reproduction_repeat_tolerances_and_incomplete_profiles(self):
        from execution.experiments import compare_reproduction_profiles
        frozen=dict(repeat_effect_ms=2,repeat_fullness_pp=1)
        reference=[dict(profile=p,n=5,theta_ms=0,fullness=dict(estimate=0),completeness_gate='passed') for p in PROFILES]
        repeat=copy.deepcopy(reference)
        row=repeat[0]
        row['theta_ms']=-2
        row['fullness']['estimate']=1
        compare=lambda: compare_reproduction_profiles(reference,repeat,frozen)['status']
        self.assertEqual(compare(),'passed')
        row['theta_ms']=-2.001
        self.assertEqual(compare(),'inconclusive')
        row['theta_ms']=0
        row['fullness']['estimate']=1.001
        self.assertEqual(compare(),'inconclusive')
        row['theta_ms']=None
        row['fullness']['estimate']=0
        self.assertEqual(compare(),'inconclusive')
        row['completeness_gate']='failed'
        self.assertEqual(compare(),'failed')
        row['n']=6
        with self.assertRaisesRegex(ValueError,'block counts'): compare()
        with self.assertRaisesRegex(ValueError,'four-profile'): compare_reproduction_profiles([],[],frozen)

    def test_frozen_schedule_survives_replacements_and_rejects_aliases(self):
        from admission.admission import separate_frozen_schedule
        from execution.schedule import replace_block
        directory=self.root/'main-id'
        directory.mkdir()
        schedule=make_schedule('main',directory.name,20,4)
        original=self.root/'frozen-plan.json'
        current=directory/'schedule.json'
        write(original,schedule)
        write(current,schedule)
        separate_frozen_schedule(original,directory)
        frozen=ref(original)
        remaining=[b['attempt_id'] for b in schedule['blocks'][1:]]
        replace_block(schedule,schedule['blocks'][0]['attempt_id'],'path',remaining)
        write(current,schedule)
        self.assertEqual(ref(original),frozen)
        self.assertNotEqual(read(original),read(current))
        alias=self.root/'alias.json'
        os.link(current,alias)
        for bad in (current,alias):
            with self.assertRaisesRegex(ValueError,'separate immutable'):
                separate_frozen_schedule(bad,directory)

    def test_prepare_validates_reproduction_before_publishing(self):
        from execution.experiments import main
        from unittest.mock import patch
        directory=self.root/'main-id'
        schedule=make_schedule('main',directory.name,20,4)
        original=self.root/'frozen-plan.json'
        write(original,schedule)
        freeze=self.root/'freeze.json'
        write(freeze,dict(bindings=dict(schedule=ref(original))))
        receipt=self.root/'reproduction.json'
        args=['experiments.py','prepare','--phase','main','--kind','real','--output',str(directory),
              '--freeze',str(freeze),'--reproduction',str(receipt),'--environment',str(self.env),'--verify',str(self.env)]
        with patch('sys.argv',args), patch('execution.experiments.verify'):
            with patch('admission.admission.release',return_value='0'*40):
                for preseeded in (False,True):
                    if preseeded:
                        directory.mkdir()
                        write(directory/'schedule.json',schedule)
                    for attempt in range(2):
                        with self.assertRaises(FileNotFoundError): main()
                        self.assertEqual(directory.exists(),preseeded)
                        if preseeded: self.assertEqual(set(directory.iterdir()),{directory/'schedule.json'})
                    self.assertFalse(list(self.root.glob('.prepare-*')))
                write(receipt,{})
                with self.assertRaisesRegex(ValueError,'synthetic environment'):
                    main()
                self.assertEqual(set(directory.iterdir()),{directory/'schedule.json'})

    def test_prepared_series_publication_can_resume_interrupted_link(self):
        from execution.experiments import publish_prepared
        staged=self.root/'staged'
        dest=self.root/'dest'
        staged.mkdir()
        dest.mkdir()
        for name in ('schedule','ledger','admission'):
            write(staged/(name+'.json'),dict(name=name))
        for name in ('schedule','ledger'):
            shutil.copy(staged/(name+'.json'),dest)
        publish_prepared(staged,dest,'main')
        self.assertEqual(read(dest/'admission.json'),dict(name='admission'))
        with self.assertRaisesRegex(ValueError,'immutable'): publish_prepared(staged,dest,'main')

    def test_reproduction_checks_alone_cannot_publish_report(self):
        path=self.primary('reproduction')
        data=read(path)
        data.update(author_id='author',executor_id='reviewer')
        write(path,data)
        output=self.root/'report.json'
        result=self.cli('import-checks','--input',path,'--output',output,'--environment',self.env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('freeze',result.stdout)
        self.assertFalse(output.exists())

    def test_r2_timer_primary_and_cli(self):
        path=self.timer(); output=self.root/'timer-report.json'
        result=self.cli('timer','--input',path,'--output',output,'--environment',self.env)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        validate_gate(read(output))
        data=read(path); data['step_ms']=.001; write(path,data)
        altered=read(output); altered['evidence'][0]=ref(path)
        with self.assertRaises(ValueError): validate_gate(altered)

    def test_r3_git_inventory_without_container_git(self):
        if not shutil.which('git'): self.skipTest('host git boundary tested separately')
        original=Path.cwd()
        repo=self.root/'git-repo'; repo.mkdir()
        for name in sources():
            target=repo/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(original/name,target)
        for args in (('init',),('add','.'),('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Test fixture release')):
            subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        snapshot=dict(commit=sha,files=sources())
        (repo/'build').mkdir(); write(repo/'build/release-state.json',snapshot)
        (repo/'results/main/generated').mkdir(parents=True); (repo/'.agents/plan').mkdir(parents=True)
        try:
            os.chdir(repo)
            self.assertEqual(release(),sha)
            if os.environ.get('RUN_DOCKER_BOUNDARY')=='1':
                boundary=subprocess.run(['/bin/sh','docker/lib/release-state.sh'],capture_output=True,text=True)
                self.assertEqual(boundary.returncode,0,boundary.stderr)
                check=subprocess.run(['docker','run','--rm','--network','none','-v',str(repo)+':/bench','-w','/bench','wswt-bench-analyzer:dev','python','-B','-c','import sys;sys.path.insert(0,"src/analysis");from admission.admission import release;print(release())'],capture_output=True,text=True)
                self.assertEqual(check.returncode,0,check.stderr)
                self.assertEqual(check.stdout.strip(),sha)
            (repo/'src/analysis/new-executable.py').write_text('pass\n')
            with self.assertRaises(ValueError): release()
            (repo/'src/analysis/new-executable.py').unlink()
            (repo/'src/analysis/reporting/power.py').write_text('changed\n')
            with self.assertRaises(ValueError): release()
        finally: os.chdir(original)

    def test_r5_current_extra_runs_queue_ledger_and_phase_path(self):
        directory=self.root/'series'; directory.mkdir()
        original=make_schedule('pilot','series',5)
        write(directory/'schedule.json',original)
        write(directory/'ledger.json',dict(schema_version=1,series_id='series',attempts=original['blocks']))
        validate_schedule_extension(directory,original,original)
        current=copy.deepcopy(original); current['runs'].append(dict(current['runs'][0],run_id='EXTRA'))
        with self.assertRaises(ValueError): validate_schedule_extension(directory,original,current)
        for queue in ([],[original['blocks'][1]['attempt_id'],original['blocks'][0]['attempt_id']]):
            write(directory/'queue.json',queue)
            with self.assertRaises(ValueError): execution_state(directory,original,original)
        (directory/'queue.json').unlink()
        self.assertEqual(len(execution_state(directory,original,original)),20)
        ledger=read(directory/'ledger.json'); ledger['attempts'][1]['status']='complete'; write(directory/'ledger.json',ledger)
        with self.assertRaises(ValueError): execution_state(directory,original,original)
        for series in ('verify','smoke'):
            with self.assertRaises(ValueError): phase_path(self.root/'results/main/test',dict(series=series))

    def test_r6_official_rejects_synthetic_or_missing_admission(self):
        directory=self.root/'official'; directory.mkdir()
        write(directory/'SYNTHETIC.json',dict(kind='synthetic'))
        with self.assertRaisesRegex(ValueError,'synthetic'): completed_series(directory,'aa',dict(kind='real'))
        (directory/'SYNTHETIC.json').unlink()
        with self.assertRaisesRegex(ValueError,'admission'): completed_series(directory,'comparison',dict(kind='real'))

    def test_r8_calibration_impossible_ids_and_survivors(self):
        data=self.calibration_fixture()
        self.assertEqual(calibration(data)['status'],'passed')
        data['egress'][0]['entered_ids']=[0]
        with self.assertRaisesRegex(ValueError,'completeness'): calibration(data)
        data=self.calibration_fixture(); data['echo']['r20p1']['rtt_ms']=[21]*10000
        with self.assertRaisesRegex(ValueError,'survivor'): calibration(data)
        data=self.calibration_fixture(); data['egress'][0]['probe']['reply_records'].pop()
        with self.assertRaisesRegex(ValueError,'survivors'): calibration(data)
        data=self.calibration_fixture(); data['trace_review']['main_bandwidth_fraction']=-.01
        with self.assertRaises(ValueError): calibration(data)

    def test_r8_generator_true_100hz_and_nonnegative(self):
        runs=self.generator_fixture()
        self.assertEqual(generator_gate(runs)['status'],'passed')
        runs[1]['observed_hz']=20
        with self.assertRaises(ValueError): generator_gate(runs)
        for field in ('browser_cpu_pct_limit','server_throttling_pct','lag_p99_ms'):
            runs=self.generator_fixture(); runs[0][field]=-1
            with self.assertRaises(ValueError): generator_gate(runs)
        runs=self.generator_fixture(); runs[1]['slots']=[dict(s,t_send_ms=i*50) for i,s in enumerate(runs[1]['slots'])]; runs[1]['observed_hz']=20
        with self.assertRaises(ValueError): generator_gate(runs)

    def test_r9_minimum_certificate_budget(self):
        certificate=Path('results/verify/measurement/smoke.OWQv8a3D/raw/b0-a0-m0/leaf.pem')
        now=datetime(2026,11,12,12,tzinfo=timezone.utc)
        with self.assertRaises(ValueError): leaf_covers(certificate,(now+timedelta(seconds=60)).isoformat(),160*80,now)
        self.assertEqual(len(leaf_covers(certificate,(now+timedelta(hours=5)).isoformat(),160*80,now)),64)
        self.assertEqual(len(leaf_covers(certificate,(now+timedelta(seconds=81)).isoformat(),80,now)),64)
        from unittest.mock import patch
        with patch('admission.admission.ssl._ssl._test_decode_cert',return_value=dict(notBefore='Nov 12 13:00:00 2026 GMT',notAfter='Nov 24 13:00:00 2026 GMT')):
            with self.assertRaises(ValueError): leaf_covers(certificate,(now+timedelta(hours=5)).isoformat(),80,now)

    def test_r10_contiguous_balanced_random_sessions(self):
        for kind in ('aa','monitoring'):
            schedule=paired_schedule(kind,'sessions-'+kind)
            self.assertEqual(schedule,paired_schedule(kind,'sessions-'+kind))
            self.assertEqual([b['session_id'] for b in schedule['blocks']],[f's{s}' for s in range(4) for _ in range(40)])
            for session in range(4):
                blocks=[b for b in schedule['blocks'] if b['session_id']==f's{session}']
                self.assertEqual({(mode,p):sum(b['modes'][0]==mode and b['profile']==p for b in blocks) for mode in ('WS','WT-S') for p in PROFILES},{(mode,p):5 for mode in ('WS','WT-S') for p in PROFILES})
            for block in schedule['blocks']:
                a,b=[r for r in schedule['runs'] if r['attempt_id']==block['attempt_id']]
                self.assertEqual(a['forward_seed']==b['forward_seed'],kind=='monitoring')
                if kind=='monitoring': self.assertEqual({a['monitoring'],b['monitoring']},{'on','off'})


    def produce(self,gate,path):
        from execution.experiments import evaluate
        data=read(path)
        from admission.admission import deep_validation
        with deep_validation():
            result=imported(data) if gate in PRIMARY_IDS else evaluate('calibrate' if gate=='calibration' else gate,data)[0]
        output=self.root/(gate+'-calculated.json')
        write(output,report(gate,result,[path],'synthetic',self.env))
        validate_gate(read(output))
        return output

    def verification_fixture(self):
        from reporting.synthetic import SOURCE
        context=read(SOURCE/'context.json')
        context['config']={name:read(Path('configs')/f'{name}.json') for name in ('plan','thresholds','profiles')}
        write(self.env,context)
        write(self.root/'SYNTHETIC.json',dict(kind='synthetic'))
        paths={gate:str(self.produce(gate,self.primary(gate))) for gate in PRIMARY_IDS if gate!='reproduction'}
        paths['timer']=str(self.produce('timer',self.timer()))
        paths['calibration']=str(self.produce('calibration',self.collection('calibration',self.calibration_fixture())))
        paths['generator']=str(self.produce('generator',self.collection('generator',dict(runs=self.generator_fixture()))))
        for gate in ('aa','monitoring'):
            paths[gate]=str(self.produce(gate,self.collection(gate,dict(design=gate,pairs=self.pairs(gate)))))
        result,code=aggregate(paths,self.env,kind='synthetic')
        self.assertEqual(code,0)
        output=self.root/'synthetic-verification.json'
        write(output,result)
        verify(output,self.env,kind='synthetic')
        return output

    def test_r4_r6_r7_actual_replacement_to_persisted_reports(self):
        from reporting.synthetic import make_fixture,rehash
        from reporting.analyze import validate_series
        from execution.experiments import evaluate
        persistent=Path('build/d5-r7-synthetic').resolve()
        persistent.mkdir(parents=True,exist_ok=True)
        self.root=Path(tempfile.mkdtemp(prefix='fixture-',dir=persistent))
        self.env=self.root/'ENV.json'
        print('R7 retained fixture',self.root,flush=True)
        verification=self.verification_fixture()
        for phase in ('aa','monitoring','pilot'):
            print('R7 phase',phase,'start',flush=True)
            identity='replacement-'+phase
            schedule=make_schedule('pilot',identity,5,4) if phase=='pilot' else paired_schedule(phase,identity)
            directory=make_fixture(self.root/identity,schedule=schedule)
            original=directory/'schedule-original.json'; write(original,schedule)
            def prepare_raw(target):
                for folder in (target/'raw').iterdir():
                    manifest=read(folder/'manifest.json'); manifest['dirty']=False; write(folder/'manifest.json',manifest)
                    (folder/'service-names.txt').write_text(folder.name+' fresh-project')
                    if manifest.get('monitoring')=='off':
                        write(folder/'monitoring-window.json',dict(monitoring='off',unobserved_start_usec=0,unobserved_end_usec=500000,resource_metrics_available=False))
                        for role in ('browser','server','router'):
                            (folder/f'{role}-oom-before.txt').write_text('oom 0\n'); (folder/f'{role}-oom-after.txt').write_text('oom 0\n')
                    rehash(folder)
            prepare_raw(directory)
            manifest=read(next((directory/'raw').iterdir())/'manifest.json')
            write(directory/'admission.json',dict(kind='synthetic',phase=phase,schedule=ref(original),source_hashes=sources(),environment=ref(self.env),verify=ref(verification),release_commit=manifest['commit']))
            run=schedule['runs'][0]; folder=directory/'raw'/run['run_id']
            network=read(folder/'network_before.json'); network['forwarding']=0; write(folder/'network_before.json',network); rehash(folder)
            proof=directory/'proof.json'
            for command in ([sys.executable,'-B','-m','execution.violation',str(folder),str(directory/'schedule.json'),str(proof)],
                            [sys.executable,'-B','-m','execution.replace',str(directory),run['attempt_id'],'path',str(proof)]):
                process=subprocess.run(command,capture_output=True,text=True)
                self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            changed=read(directory/'schedule.json')
            ready=make_fixture(self.root/('ready-'+phase),schedule=changed)
            prepare_raw(ready)
            shutil.rmtree(directory/'raw'); shutil.copytree(ready/'raw',directory/'raw')
            shutil.copyfile(ready/'ledger.json',directory/'ledger.json'); write(directory/'queue.json',[])
            print('R7 phase',phase,'replacement files ready',flush=True)
            active={a['attempt_id'] for a in read(directory/'ledger.json')['attempts'] if a['status']=='complete'}
            selected=[r for r in changed['runs'] if r['attempt_id'] in active]
            data=dict(kind='synthetic',gate=phase,collection_id=identity,design=phase,schedule=ref(directory/'schedule.json'),
                      source_hashes=sources(),environment=ref(self.env),independence_reviewed=True,evidence=[ref(directory/'schedule.json')])
            path=self.root/(phase+'-series-input.json'); write(path,data)
            if phase=='pilot':
                pilot=self.produce('pilot',path)
                data['gate']='power'; power_path=self.root/'power-series-input.json'; write(power_path,data)
                power=self.produce('power',power_path)
                from admission.admission import experiment_reports,inventory,coverage
                experiment_reports(dict(pilot=ref(pilot),power=ref(power)),{'WS','WT-S'},ref(self.env),'synthetic')
                with self.assertRaisesRegex(ValueError,'pilot report'): experiment_reports(dict(pilot=ref(self.root/'timer-calculated.json'),power=ref(power)),{'WS','WT-S'},ref(self.env),'synthetic')
                with self.assertRaises(ValueError): coverage(read(verification),{'WS','WT-S','WT-D'})
                unrelated=self.root/'unrelated.json'; write(unrelated,{})
                for category in ('analysis','locks'):
                    with self.assertRaises(ValueError): inventory(ref(unrelated),category)
            else:
                output=self.root/(phase+'-official-report.json')
                process=self.cli(phase,'--input',path,'--output',output,'--environment',self.env)
                self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                validate_gate(read(output))
                print('R7 phase',phase,'persisted report passed',flush=True)
                a,b=[directory/'raw'/r['run_id'] for r in selected[:2]]
                a.rename(directory/'hold'); b.rename(a); (directory/'hold').rename(b)
                with self.assertRaises(ValueError): completed_series(directory,phase,data)
                a.rename(directory/'hold'); b.rename(a); (directory/'hold').rename(b)
            archived=directory/'audit'/run['attempt_id']/run['run_id']
            backup=self.root/('archive-backup-'+phase)
            shutil.copytree(archived,backup)
            shutil.rmtree(archived)
            with self.assertRaises(Exception): validate_series(directory,'comparison' if phase=='pilot' else phase)
            shutil.copytree(backup,archived)
            print('R7 phase',phase,'passed',flush=True)


    def test_preserved_numeric_null_completeness_and_exit_states(self):
        self.assertTrue(timer_gate(dict(count=100000,monotonic=True,step_ms=.1,p99_overhead_ms=.1)))
        self.assertFalse(timer_gate(dict(count=100000,monotonic=True,step_ms=.100001,p99_overhead_ms=.1)))
        self.assertFalse(timer_gate(dict(count=100000,monotonic=False,step_ms=.1,p99_overhead_ms=.1)))
        with self.assertRaises(ValueError): exact_binomial(-1,10000)
        data=self.calibration_fixture(); data['saturation'][0]['forwarded_bytes']=67500000
        self.assertEqual(calibration(data)['status'],'passed')
        data['saturation'][0]['forwarded_bytes']=67499999
        self.assertEqual(calibration(data)['status'],'failed')
        pairs=self.pairs('aa'); pairs[0]['sides'][0]['Q_ms']=None
        self.assertEqual(equivalence(pairs,'aa','null')['status'],'inconclusive')
        pairs[0]['sides'][0]['disconnects']=1
        self.assertEqual(equivalence(pairs,'aa','null')['status'],'failed')
        for pair in pairs:
            for side in pair['sides']: side['Q_ms']=None; side['disconnects']=0
        self.assertEqual(equivalence(pairs,'aa','all-null')['status'],'inconclusive')
        empty,code=aggregate({},self.env,kind='synthetic')
        self.assertEqual(code,2)
        self.assertTrue(all(c['status']=='not_run' and c['reason']=='gate_report_not_provided' for c in empty['document']['checks']))
        path=self.primary('build'); data=read(path)
        document=data['document']; document['checks'][0]['status']='failed'; document['checks'][0]['actual']=False
        from admission.admission import validate_checks
        self.assertEqual(validate_checks(document),1)
        document['checks'][0]['status']='inconclusive'
        self.assertEqual(validate_checks(document),2)

    def test_preserved_executor_pause_and_direct_freeze_refusal(self):
        from execution.experiments import execute
        from admission.admission import freeze
        from unittest.mock import patch
        directory=self.root/'pause'; directory.mkdir()
        schedule=make_schedule('pilot','pause',5)
        write(directory/'schedule.json',schedule); write(directory/'ledger.json',dict(schema_version=1,series_id='pause',attempts=schedule['blocks']))
        def executor(d,i):
            (d/'PENDING_REPLACEMENT').write_text('b0-a0')
            raise subprocess.CalledProcessError(3,['offline-stub'])
        with patch('execution.experiments.admit'):
            self.assertEqual(execute(directory,executor),2)
            self.assertFalse((directory/'STOP').exists())
        with self.assertRaises(ValueError): freeze(dict(kind='synthetic'),self.root/'forbidden-freeze.json')
        self.assertFalse((self.root/'forbidden-freeze.json').exists())
        from jsonschema import Draft202012Validator
        schema=read(Path('configs/schemas/freeze.schema.json'))
        for value in ({},{'kind':'synthetic'},{'dirty':True},{'extra':'field'}):
            self.assertFalse(Draft202012Validator(schema).is_valid(value))


    def test_r2a_r5a_r8a_r11_publication_and_shallow_integrity(self):
        from unittest.mock import patch
        path=self.primary('build')
        from reporting.synthetic import SOURCE
        actual_env=SOURCE/'context.json'
        output=self.root/'forbidden-real.json'
        result=self.cli('import-checks','--input',path,'--output',output,'--environment',actual_env,'--kind','real')
        self.assertEqual(result.returncode,2)
        self.assertFalse(output.exists())
        timer=self.timer(); data=read(timer); data['step_ms']=.000001; write(timer,data)
        result=self.cli('timer','--input',timer,'--output',output,'--environment',self.env)
        self.assertEqual(result.returncode,2)
        self.assertFalse(output.exists())
        generated=self.produce('build',path)
        with patch('execution.experiments.evaluate',side_effect=AssertionError('scientific recalculation forbidden')):
            validate_gate(read(generated),recalculate=False)
        trace=self.root/'build-locked-install.json'; trace.write_text('{}')
        with self.assertRaises(ValueError): validate_gate(read(generated),recalculate=False)
        directory=self.root/'ledger-bypass'; directory.mkdir()
        original=make_schedule('pilot','ledger-bypass',5)
        write(directory/'ledger.json',dict(schema_version=1,series_id='ledger-bypass',attempts=copy.deepcopy(original['blocks'])))
        ledger=read(directory/'ledger.json'); ledger['attempts'][0].update(status='quarantined',reason='path'); write(directory/'ledger.json',ledger)
        with self.assertRaisesRegex(ValueError,'quarantine'): execution_state(directory,original,original)
        write(directory/'ledger.json',dict(schema_version=1,series_id='ledger-bypass',attempts=original['blocks']))
        (directory/'raw'/original['runs'][0]['run_id']).mkdir(parents=True)
        with self.assertRaises(Exception): execution_state(directory,original,original)
        runs=self.generator_fixture()
        for slot in runs[1]['slots'][1:-1]: slot['t_send_ms']=None
        with self.assertRaisesRegex(ValueError,'state'): generator_gate(runs)
        runs=self.generator_fixture()
        runs[0]['resource_window']['end_usec']=1000000
        with self.assertRaisesRegex(ValueError,'coverage'): generator_gate(runs)

    def test_power_complete_protocol(self):
        result=simulate({p:[-2,-1,0,1,2] for p in PROFILES},'synthetic-power')
        self.assertEqual(len(result['results']),48)
        for row in result['results']:
            if row['scenario']=='iid' and row['shift_ms']==0: self.assertLess(row['familywise_rejection'],.05)
            if row['scenario']=='iid' and row['shift_ms']!=0: self.assertTrue(all(p['power']>.8 for p in row['profiles'].values()))


if __name__=='__main__': unittest.main()
