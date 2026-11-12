import json,shutil,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'src/analysis')
from test_acceptance import AcceptanceTests
from synthetic import make_fixture,rehash
from schedule import make_schedule
from raw import read,write
from admission import ref,sources,validate_gate,admit,verify,experiment_reports
from experiments import report
root=Path('/bench/build/d5-r7-synthetic/fixture-9l51pfgl')
test=AcceptanceTests();test.setUp();test.root=root;test.env=root/'ENV.json'
started=time.monotonic();verification=root/'synthetic-verification.json'
if verification.exists():verify(verification,test.env,kind='synthetic',recalculate=False)
else:verification=test.verification_fixture()
print('fresh synthetic prerequisites',flush=True)
for phase in ('aa','monitoring','pilot'):
    directory=root/('replacement-'+phase)
    if phase=='pilot' and not directory.exists():
        schedule=make_schedule('pilot',directory.name,5,4)
        make_fixture(directory,schedule=schedule)
        write(directory/'schedule-original.json',schedule)
        def prepare(target):
            for folder in (target/'raw').iterdir():
                value=read(folder/'manifest.json');value['dirty']=False;write(folder/'manifest.json',value)
                (folder/'service-names.txt').write_text(folder.name+' fresh-project');rehash(folder)
        prepare(directory)
        run=schedule['runs'][0];folder=directory/'raw'/run['run_id']
        data=read(folder/'network_before.json');data['forwarding']=0;write(folder/'network_before.json',data);rehash(folder)
        for command in ([sys.executable,'-B','src/analysis/violation.py',str(folder),str(directory/'schedule.json'),str(directory/'proof.json')],
                        [sys.executable,'-B','src/analysis/replace.py',str(directory),run['attempt_id'],'path',str(directory/'proof.json')]):
            subprocess.run(command,check=True)
        ready=root/'ready-pilot';make_fixture(ready,schedule=read(directory/'schedule.json'));prepare(ready)
        shutil.rmtree(directory/'raw');shutil.copytree(ready/'raw',directory/'raw');shutil.copyfile(ready/'ledger.json',directory/'ledger.json');write(directory/'queue.json',[])
    schedule=read(directory/'schedule.json')
    manifest=read(next((directory/'raw').iterdir())/'manifest.json')
    write(directory/'admission.json',dict(kind='synthetic',phase=phase,schedule=ref(directory/'schedule-original.json'),source_hashes=sources(),environment=ref(test.env),verify=ref(verification),release_commit=manifest['commit']))
    data=dict(kind='synthetic',gate=phase,collection_id=directory.name,design=phase,schedule=ref(directory/'schedule.json'),source_hashes=sources(),environment=ref(test.env),independence_reviewed=True,evidence=[ref(directory/'schedule.json')])
    input_file=root/(phase+'-current-input.json');write(input_file,data)
    actions=('pilot','power') if phase=='pilot' else (phase,)
    for action in actions:
        output=root/(action+'-current-report.json')
        if output.exists():
            try:
                validate_gate(read(output),recalculate=False)
                print(action,'retained report integrity passed',flush=True)
                continue
            except ValueError:output.unlink()
        data['gate']=action
        input_file=root/(action+'-immutable-input.json')
        write(input_file,data)
        print(action,'publication start',round(time.monotonic()-started,2),flush=True)
        subprocess.run([sys.executable,'-B','src/analysis/experiments.py',action,'--input',str(input_file),'--output',str(output),'--environment',str(test.env)],check=True)
        validate_gate(read(output),recalculate=False)
        print(action,'publication and immutable readback passed',round(time.monotonic()-started,2),flush=True)
    # Check per-run evidence integrity without scientific re-evaluation.
    with patch('experiments.evaluate',side_effect=AssertionError('per-run scientific recalculation')):
        verify(verification,test.env,kind='synthetic',recalculate=False)
    print(phase,'counter check passed',flush=True)
print('REUSE PASSED elapsed',round(time.monotonic()-started,2),flush=True)
