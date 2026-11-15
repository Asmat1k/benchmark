import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import tempfile

ROOT = Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
BASE = ROOT/'results/verify/readiness/stage4/practical-v1/release-v2'
TLS = ROOT/'build/series-tls-stage2._n__udb0'
HEAD = 'acce594'


def check():
    os.chdir(ROOT)
    BASE.mkdir(parents=True, exist_ok=True)
    execution = Path(tempfile.mkdtemp(prefix='preflight.', dir=BASE))
    previous_handler = signal.getsignal(signal.SIGALRM)
    def timeout_handler(signum, frame):
        raise TimeoutError('preflight total deadline120s')
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(120)
    def write(name, value):
        (execution/name).write_text(json.dumps(value,indent=2)+'\n')
    def command(argv):
        result = subprocess.run(argv,input='',capture_output=True,text=True,timeout=20)
        with (execution/'commands.jsonl').open('a') as log:
            log.write(json.dumps(dict(argv=argv,exit=result.returncode,stdout=result.stdout,stderr=result.stderr))+'\n')
        result.check_returncode()
        return result.stdout
    stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    (execution/'started').write_text(stamp()+'\n')
    try:
        head = command(['git','rev-parse','HEAD']).strip()
        assert head.startswith(HEAD)
        command(['sh','docker/lib/check-release.sh',head])
        assert 'AC Power' in command(['pmset','-g','batt'])
        assert '"AppleClamshellState" = No' in command(['ioreg','-r','-k','AppleClamshellState','-d','4'])
        assert shutil.disk_usage(ROOT).free >= 30*1024**3
        cert = TLS/'server/good/cert.pem'
        assert hashlib.sha256(cert.read_bytes()).hexdigest() == 'ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9'
        assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest() == 'fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18'
        remaining = ssl.cert_time_to_seconds(ssl._ssl._test_decode_cert(str(cert))['notAfter'])-datetime.datetime.now(datetime.timezone.utc).timestamp()
        assert remaining >= 8*86400
        info = json.loads(command(['docker','info','--format','{{json .}}']))
        assert (info['NCPU'],info['MemTotal'],info['Architecture']) == (2,4109484032,'aarch64')
        expected = json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text())
        tags = ['wswt-bench-'+role+':dev' for role in ('server','browser','router','analyzer')]
        images = json.loads(command(['docker','image','inspect',*tags]))
        assert [r['Id'] for r in images] == [r['image_id'] for r in expected]
        assert all((r['Os'],r['Architecture']) == ('linux','arm64') for r in images)
        containers = json.loads(command(['docker','ps','-a','--format','{{json .}}']).replace('}\n{','},{').join(['[',']']))
        assert not any(r['Names'].startswith('wswt-') for r in containers)
        networks = json.loads(command(['docker','network','inspect',*command(['docker','network','ls','-q']).split()]))
        import ipaddress
        labs = [ipaddress.ip_network(n) for n in ('172.28.10.0/24','172.28.20.0/24')]
        assert not any(ipaddress.ip_network(c['Subnet']).overlaps(lab) for n in networks for c in (n.get('IPAM',{}).get('Config') or []) if c.get('Subnet') for lab in labs if ipaddress.ip_network(c['Subnet']).version == lab.version)
        analyze = ['docker','run','--rm','-i','--network','none','-v',str(ROOT)+':/bench','-w','/bench',tags[-1]]
        assert command(analyze+['python','-B','src/analysis/series.py','hold']).strip() == 'locked'
        vm_disk = command(['docker','run','--rm','--network','none',tags[-1],'df','-B1','/'])
        assert int(vm_disk.splitlines()[-1].split()[3]) >= 30*1024**3
        inventory = json.loads(command(analyze+['python','-B','-c','import sys,json;sys.path.insert(0,"src/analysis");from admission import sources;print(json.dumps(sources()))']))
        release = json.loads(Path('build/release-state.json').read_text())
        assert release['commit'] == head and all(release['files'][p] == h for p,h in inventory.items())
        write('source-inventory.json',inventory)
        write('environment-preflight.json',dict(head=head,images=[dict(tag=t,image_id=r['Id']) for t,r in zip(tags,images)],vm=info,tls_horizon_days=remaining/86400,containers=containers,vm_disk=vm_disk,host_free_bytes=shutil.disk_usage(ROOT).free))
        write('result.json',dict(status='passed',head=head,source_count=len(inventory)))
        (execution/'exit').write_text('0\n')
        print(execution)
    except BaseException as error:
        write('STOP.json',dict(status='failed',error=repr(error)))
        (execution/'exit').write_text('2\n')
        raise
    finally:
        (execution/'ended').write_text(stamp()+'\n')
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
    return execution


if __name__ == '__main__':
    check()
