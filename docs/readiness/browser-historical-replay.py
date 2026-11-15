import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('commit')
parser.add_argument('report', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = Path.cwd()
args.output.mkdir(parents=True, exist_ok=False)
stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
report = json.loads(args.report.read_text())
record = dict(schema_version=1, validation='validate-gate-exact-source-v1', started_utc=stamp(),commit=args.commit,
              report=ref(args.report),environment=report['environment'],source_hashes=report['source_hashes'],
              historical_status=report['status'],runner=ref(Path(__file__)))
code = 2
with (args.output/'stdout.log').open('x') as stdout,(args.output/'stderr.log').open('x') as stderr:
    try:
        view = args.output/'source'
        view.mkdir()
        archive = args.output/'source.tar'
        with archive.open('wb') as stream:
            subprocess.run(['git','archive',args.commit,'src','docker','docs/schemas','docs/protocol.md','configs','Makefile','compose.yaml'],stdout=stream,stderr=stderr,check=True,timeout=30)
        subprocess.run(['tar','-xf',str(archive),'-C',str(view)],stdout=stdout,stderr=stderr,check=True,timeout=30)
        program = '''import json,sys
sys.path.insert(0,'src/analysis')
from admission import sources,validate_gate,ref
from raw import read,require
path=__import__('pathlib').Path(sys.argv[1]);report=read(path)
require(report['source_hashes']==sources(),'replay exact source inventory')
validate_gate(report)
print(json.dumps(dict(validated_report=ref(path),source_hashes=sources(),environment=report['environment'],status=report['status'])))
'''
        argv = ['docker','run','--rm','--network','none','-v',str(view.resolve())+':/bench',
                '-v',str(root/'results')+':/bench/results:ro','-v',str(root/'build')+':/bench/build:ro',
                '-v',str(root)+':'+str(root)+':ro','-w','/bench','wswt-bench-analyzer:dev','python','-B','-c',program,str(args.report)]
        record['argv'] = argv
        code = subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=900).returncode
    except BaseException:
        import traceback
        traceback.print_exc(file=stderr)
    finally:
        record.update(ended_utc=stamp(),exit=code)
record.update(stdout=ref(args.output/'stdout.log'),stderr=ref(args.output/'stderr.log'))
(args.output/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
(args.output/'exit').write_text(str(code)+'\n')
if code:
    (args.output/'STOP').write_text('Exact-source replay did not complete successfully; preserve logs.\n')
raise SystemExit(code)
