import shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'src/analysis')
from raw import read, write, digest, validate_hashes
source = Path('results/verify/measurement/smoke.pT5919A1')
with tempfile.TemporaryDirectory(prefix='d6-review-synthetic-') as temp:
    series = Path(temp) / source.name
    shutil.copytree(source, series)
    write(series/'SYNTHETIC.json', {'kind':'synthetic','purpose':'test targeting existing raw'})
    schedule = read(series/'schedule.json')
    first, second = schedule['runs']
    published = series/'raw'/first['run_id']
    shutil.rmtree(series/'raw'/second['run_id'])
    ledger = read(series/'ledger.json')
    ledger['attempts'][0]['status'] = 'planned'
    write(series/'ledger.json',ledger)
    write(series/'queue.json',[first['attempt_id']])
    validate_hashes(published)
    before = digest(published/'run.json')
    result = subprocess.run([sys.executable,'-B','src/analysis/record.py','prepare',str(series),'1',str(published)],capture_output=True,text=True)
    print('prepare exit', result.returncode,'published raw changed',digest(published/'run.json') != before)
    try: validate_hashes(published)
    except ValueError as e: print(e)
