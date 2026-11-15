import datetime
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import sys

BASE=Path(__file__).resolve().parent

def main(output):
    def command(args):
        return subprocess.check_output(args,text=True,timeout=15)
    power=command(['pmset','-g','batt'])
    if 'AC Power' not in power:
        (output/'preflight.json').write_text(json.dumps(dict(status='failed',reason='AC Power required',power=power))+'\n')
        raise RuntimeError('AC Power required; collector not started')
    lid=command(['ioreg','-r','-k','AppleClamshellState','-d','4'])
    assert '\"AppleClamshellState\" = No' in lid
    inventory=json.loads((BASE/'source-inventory.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inventory.items())
    head=command(['git','rev-parse','HEAD']).strip()
    assert head=='d66559066b704fde567b6c9f92f57e2dcde22698'
    assert not command(['git','status','--porcelain','--','docker','src','configs','Makefile','compose.yaml','docs/schemas','docs/protocol.md'])
    cert=Path('build/series-tls-stage2._n__udb0/server/good/cert.pem')
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()=='fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18'
    assert ssl.cert_time_to_seconds(ssl._ssl._test_decode_cert(str(cert))['notAfter'])-datetime.datetime.now(datetime.timezone.utc).timestamp()>8*86400
    images=json.loads(command(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev']))
    expected=json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())
    assert [r['Id'] for r in images]==[r['image_id'] for r in expected]
    containers=command(['docker','ps','--format','{{.Names}} {{.Status}}'])
    assert not any(n.startswith('wswt-') for n in containers.splitlines())
    assert shutil.disk_usage('.').free>2*1024**3
    (output/'preflight.json').write_text(json.dumps(dict(status='passed',head=head,source_count=len(inventory),power=power,lid_open=True,free_bytes=shutil.disk_usage('.').free,image_ids=[r['Id'] for r in images],containers=containers,time=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')

if __name__=='__main__':
    main(Path(sys.argv[1]))
