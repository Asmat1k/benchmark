import ast
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

root = Path.cwd()
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=False)
stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
record = dict(started_utc=stamp(),scope='committed executable source and finite study documents; images and raw remain separately bound')
code = 2
with (output/'stdout.log').open('x') as stdout,(output/'stderr.log').open('x') as stderr:
    try:
        head = subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=10).strip()
        record['commit'] = head
        archive = output/('source-'+head+'.tar')
        paths = ['src','docker','docs/schemas','docs/protocol.md','configs/plan.json','configs/profiles.json',
                 'configs/thresholds.json','Makefile','compose.yaml','docs/readiness/finite-browser-study-v1.md',
                 'docs/experiments.md','docs/verification.md']
        with archive.open('xb') as stream:
            subprocess.run(['git','archive',head,*paths],stdout=stream,stderr=stderr,check=True,timeout=30)
        tree = ast.parse((root/'src/analysis/admission.py').read_text())
        tracked = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and
                       any(isinstance(target,ast.Name) and target.id=='TRACKED' for target in node.targets))
        files = [root/name for name in tracked]+[root/'Makefile',root/'compose.yaml']
        files += [p for category in ('src','docker','docs/schemas') for p in (root/category).rglob('*') if p.is_file() and
                  'node_modules' not in p.parts and '__pycache__' not in p.parts and 'dist' not in p.parts]
        current = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
        with tarfile.open(archive) as bundle:
            members = {m.name:hashlib.sha256(bundle.extractfile(m).read()).hexdigest() for m in bundle if m.isfile()}
        if not all(members.get(name)==sha for name,sha in current.items()):
            raise ValueError('Current executable inventory differs from committed archive')
        if subprocess.check_output(['git','rev-parse','HEAD'],text=True,timeout=10).strip()!=head:
            raise ValueError('HEAD changed during source archiving')
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output/(archive.name+'.sha256')).write_text(sha+'  '+archive.name+'\n')
        record.update(archive=dict(path=str(archive),sha256=sha,bytes=archive.stat().st_size),
                      source_hashes=current,archive_members=members,source_count=len(current))
        stdout.write('Exact committed source inventory verified: '+str(len(current))+' files\n')
        code = 0
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
    finally:
        record.update(ended_utc=stamp(),exit=code)
(output/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
(output/'exit').write_text(str(code)+'\n')
print(output)
raise SystemExit(code)
