import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

ROOT = Path('/Users/dobrov/Desktop/Code/ITMO/benchmark')
BASE = ROOT/'results/verify/readiness/stage4/practical-v1/timer-diagnostic'
ORDER = [(0,0),(1,0),(1,1),(0,1),(0,1),(1,1),(1,0),(0,0)]
ROLES = ('browser','server','router')
QUEUE_TEST = '[.[] | select(.kind=="netem")] | length==2 and all(.[]; .backlog==0 and .qlen==0)'


def interval_summary(rows, start, end):
    if not rows or any(r['interval_usec'] <= 0 for r in rows):
        raise ValueError('missing or invalid intervals')
    if any(a['end_usec'] >= b['end_usec'] or b['sample_index'] != a['sample_index']+1 for a,b in zip(rows,rows[1:])):
        raise ValueError('sample order or gap')
    if rows[0]['end_usec']-rows[0]['interval_usec'] > start or rows[-1]['end_usec'] < end:
        raise ValueError('phase not bracketed')
    selected = [r for r in rows if start <= r['end_usec']-r['interval_usec'] and r['end_usec'] <= end]
    if not selected:
        raise ValueError('no complete phase intervals')
    values = [100*r['cpu_usage_usec']/r['interval_usec'] for r in selected]
    return dict(sample_ids=[r['sample_index'] for r in selected], count=len(selected),
                mean_cpu_pct=100*sum(r['cpu_usage_usec'] for r in selected)/sum(r['interval_usec'] for r in selected),
                max_cpu_pct=max(values), complete_intervals=selected)


def run(preflight):
    os.chdir(ROOT)
    prior = json.loads((preflight/'result.json').read_text())
    assert prior['status'] == 'passed' and (preflight/'exit').read_text().strip() == '0'
    assert time.time()-datetime.datetime.fromisoformat((preflight/'ended').read_text().strip()).timestamp() < 180
    execution = Path(tempfile.mkdtemp(prefix='observer-only.',dir=BASE))
    project = 'wswt-observer-'+execution.name.split('.')[-1].lower()
    env = dict(os.environ,BENCH_TLS_DIR=str(ROOT/'build/series-tls-stage2._n__udb0'),PROJECT=project,run_dir=str(execution))
    began = time.monotonic()
    deadline = began+220
    stamp = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    def save(name,value):
        (execution/name).write_text(json.dumps(value,indent=2)+'\n')
    def command(argv, timeout=40):
        started = stamp()
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('diagnostic deadline')
        process = subprocess.Popen(argv,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            stdout,stderr = process.communicate(timeout=min(timeout,remaining))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            stdout,stderr = process.communicate()
            with (execution/'commands.jsonl').open('a') as log:
                log.write(json.dumps(dict(argv=argv,start=started,end=stamp(),exit=124,stdout=stdout,stderr=stderr))+'\n')
            raise TimeoutError('command deadline')
        with (execution/'commands.jsonl').open('a') as log:
            log.write(json.dumps(dict(argv=argv,start=started,end=stamp(),exit=process.returncode,stdout=stdout,stderr=stderr))+'\n')
        if process.returncode:
            raise RuntimeError('command failed: '+repr(argv))
        return stdout
    def compose(*argv, timeout=40):
        return command(['docker','compose','-p',project,*argv], timeout=timeout)
    def uptime():
        return float(compose('exec','-T','router','cat','/proc/uptime').split()[0])*1000000
    def wait_until(target):
        if target > deadline:
            raise TimeoutError('insufficient phase budget')
        time.sleep(max(0,target-time.monotonic()))
    lock = None
    code = 1
    phases = []
    (execution/'started').write_text(stamp()+'\n')
    save('plan.json',dict(order=ORDER,phase_seconds=12,action_seconds=[1,7],baseline_seconds=6,total_hardcap_s=240,preflight=str(preflight)))
    try:
        head = command(['git','rev-parse','HEAD']).strip()
        assert head == prior['head']
        command(['sh','docker/check-release.sh',head])
        save('source-inventory.json',json.loads((preflight/'source-inventory.json').read_text()))
        lock = subprocess.Popen(['docker','run','--rm','-i','--network','none','-v',str(ROOT)+':/bench','-w','/bench','wswt-bench-analyzer:dev','python','-B','src/analysis/series.py','hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(execution/'lock.stderr.log').open('w'),text=True)
        import select
        if not select.select([lock.stdout],[],[],10)[0] or lock.stdout.readline().strip() != 'locked':
            raise RuntimeError('measurement lock unavailable')
        compose('up','-d','--no-build','router','server','browser')
        command(['sh','-c','compose() { docker compose -p "$PROJECT" "$@"; }; . docker/links.sh; setup_links'])
        compose('exec','-T','router','sh','/usr/local/bin/network','profile','baseline','20261110','20261111')
        save('inspect.json',json.loads(command(['docker','inspect',*compose('ps','-q').split()])))
        for role in ROLES:
            compose('cp','docker/sample.sh',role+':/tmp/sample.sh')
            compose('cp','docker/check-sample.sh',role+':/tmp/check-sample.sh')
            compose('exec','-d','-e','ROLE='+role,'-e','RUN_ID=observer-only',role,'sh','-c','exec sh /tmp/sample.sh >/tmp/resources.jsonl 2>/tmp/resources-error.txt')
        baseline_start = uptime()
        wait_until(time.monotonic()+6)
        baseline_end = uptime()
        save('baseline.json',dict(start_usec=baseline_start,end_usec=baseline_end))
        for index,(queue,readback) in enumerate(ORDER):
            phase_clock = time.monotonic()
            row = dict(index=index,queue=queue,readback=readback,start_usec=uptime(),actions=[])
            phases.append(row)
            save('phases.json',phases)
            for offset in (1,7):
                wait_until(phase_clock+offset)
                action = dict(start=stamp(),offset_s=offset)
                row['actions'].append(action)
                save('phases.json',phases)
                loop = 'for i in 0 1 2 3 4 5 6 7 8 9 10; do '+('tc -s -j qdisc show | jq -e '+"'"+QUEUE_TEST+"'"+' >/dev/null || exit 1; ' if queue else '')+'[ "$i" = 10 ] || sleep .1; done'
                compose('exec','-T','router','sh','-c',loop)
                time.sleep(2)
                if readback:
                    action['readbacks'] = {role:json.loads(compose('exec','-T',role,'sh','/tmp/check-sample.sh','fresh')) for role in ROLES}
                action['end'] = stamp()
                save('phases.json',phases)
            if time.monotonic() > phase_clock+12:
                raise TimeoutError('action exceeded fixed phase duration')
            wait_until(phase_clock+12)
            row['end_usec'] = uptime()
            save('phases.json',phases)
        time.sleep(2)
        summaries = []
        for role in ROLES:
            raw = compose('exec','-T',role,'cat','/tmp/resources.jsonl')
            (execution/(role+'-resources.jsonl')).write_text(raw)
            (execution/(role+'-sampler-error.txt')).write_text(compose('exec','-T',role,'cat','/tmp/resources-error.txt'))
            rows = [json.loads(line) for line in raw.splitlines()]
            summaries.append(dict(role=role,all_samples=len(rows),baseline=interval_summary(rows,baseline_start,baseline_end),
                                  phases=[dict(index=p['index'],queue=p['queue'],readback=p['readback'],**interval_summary(rows,p['start_usec'],p['end_usec'])) for p in phases]))
        save('analysis.json',dict(status='diagnostic_complete_not_acceptance',roles=summaries,limitations=['No browser workload or timer repeated','Matched probes identify observer costs in this idle run only','No statistical independence or future VM guarantee claimed']))
        code = 0
    except BaseException as error:
        save('STOP.json',dict(error=repr(error),completed_phases=len(phases)))
        raise
    finally:
        deadline = began+240
        for role in ROLES:
            try:
                if not (execution/(role+'-resources.jsonl')).exists():
                    (execution/(role+'-resources.jsonl')).write_text(compose('exec','-T',role,'cat','/tmp/resources.jsonl',timeout=2))
            except Exception:
                pass
        try:
            compose('down','--timeout','2',timeout=10)
        except Exception as error:
            code = 1
            save('cleanup-error.json',dict(error=repr(error),project=project))
        finally:
            if lock:
                lock.stdin.close()
                try:
                    lock.wait(timeout=max(1,deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    lock.kill()
            (execution/'exit').write_text(str(code)+'\n')
            (execution/'ended').write_text(stamp()+'\n')
            print(execution,flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('preflight',type=Path)
    raise SystemExit(run(parser.parse_args().preflight))
