import contextlib,copy,shutil,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'src/analysis')
import admission
from raw import read,write
from admission import ref,sources
from record import run_spec
from series import bind_context
root=Path('/bench/build/d5-r7-synthetic/fixture-9l51pfgl')
from synthetic import make_fixture,rehash
from schedule import make_schedule,block_runs
target=root/'early'/'per-run-synthetic'
if target.exists():shutil.rmtree(target)
schedule=make_schedule('verify',target.name,1,1)
for block in schedule['blocks']:block.update(design='aa',modes=['WS','WS'])
schedule['runs']=[r for i,b in enumerate(schedule['blocks']) for r in block_runs(schedule,b,i)]
make_fixture(target,schedule=schedule)
write(target/'schedule-original.json',schedule)
ledger=read(target/'ledger.json')
for attempt in ledger['attempts']:attempt['status']='planned'
write(target/'ledger.json',ledger)
(target/'queue.json').unlink()
first=schedule['runs'][0]
for folder in (target/'raw').iterdir():
    if folder.name!=first['run_id']:shutil.rmtree(folder)
manifest=read(target/'raw'/first['run_id']/'manifest.json')
write(target/'admission.json',dict(kind='synthetic',phase='aa',schedule=ref(target/'schedule-original.json'),source_hashes=sources(),environment=ref(root/'ENV.json'),verify=ref(root/'synthetic-verification.json'),release_commit=manifest['commit']))
partial=root/'next-partial'
if partial.exists():shutil.rmtree(partial)
partial.mkdir()
published=target/'raw'/first['run_id']
context_partial=root/'context-stage'
if context_partial.exists():shutil.rmtree(context_partial)
shutil.copytree(published,context_partial)
original=admission.admit
counter={k:0 for k in ('evaluate','rows','bootstrap','power')}
def forbidden(name):
    def call(*args,**kwargs):counter[name]+=1;raise AssertionError(name+' called per-run')
    return call
def synthetic_admit(directory,kind='real',**kwargs):return original(directory,kind='synthetic',**kwargs)
with contextlib.ExitStack() as stack:
    for where,name in (('experiments.evaluate','evaluate'),('raw.rows','rows'),('inference.bootstrap','bootstrap'),('power.simulate','power')):
        stack.enter_context(patch(where,side_effect=forbidden(name)))
    stack.enter_context(patch('admission.admit',side_effect=synthetic_admit))
    original(target,kind='synthetic');original(target,kind='synthetic')
    index=next(i for i,r in enumerate(schedule['runs']) if r['attempt_id']==first['attempt_id'] and r['run_id']!=first['run_id'])
    run_spec(target,index,partial)
    bind_context(target,context_partial);bind_context(target,context_partial)
    data=read(target/'admission.json')
    fake=root/'wrong-ENV.json';write(fake,dict(kind='synthetic',wrong=True))
    write(target/'admission.json',dict(data,environment=ref(fake)))
    try:original(target,kind='synthetic');raise AssertionError('wrong ENV accepted')
    except ValueError:pass
    write(target/'admission.json',data)
    raw=published/'slots.jsonl';before=raw.read_bytes();raw.write_bytes(before+b'\n')
    try:original(target,kind='synthetic');raise AssertionError('raw mutation accepted')
    except ValueError:pass
    raw.write_bytes(before)
    observation=root/'build-locked-install.json';before=observation.read_bytes();observation.write_text('{}')
    try:original(target,kind='synthetic');raise AssertionError('primary swap accepted')
    except ValueError:pass
    observation.write_bytes(before)
assert not any(counter.values()),counter
print('PER-RUN PASSED',counter,'admit twice; actual record.prepare; context twice; ENV/raw/underlying observation negatives')
