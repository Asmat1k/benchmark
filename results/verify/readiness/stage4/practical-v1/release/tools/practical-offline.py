import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

base = Path('results/verify/readiness/stage4/practical-v1/early-offline')
base.mkdir(parents=True, exist_ok=False)
common = ['docker','run','--rm','--network','none','-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONPATH=src/analysis','-v',str(Path.cwd())+':/bench','-w','/bench','wswt-bench-analyzer:dev','timeout','120','python','-B']
commands = {
    'offline': common+['-m','unittest','-v','test_analysis.StatisticalTests',
        'test_measurement.MeasurementTests.test_r1_contradictions_after_rehash',
        'test_measurement.MeasurementTests.test_r1_valid_loss_late_disconnect',
        'test_measurement.MeasurementTests.test_r2_sampler_stops_and_missing_interval',
        'test_measurement.MeasurementTests.test_r3_series_context_and_after_readback',
        'test_measurement.MeasurementTests.test_r5_evidence_and_normal_replacement',
        'test_measurement.MeasurementTests.test_r6_recovery_and_shared_lock',
        'test_recovery.RecoveryTests.test_complete_clock_violation_keeps_replacement_route',
        'test_recovery.RecoveryTests.test_missing_journal_and_expiry_take_actual_stop_cleanup'],
    'null': common+['docs/readiness/stage3-null-fixture.py'],
}
records = []
for name,argv in commands.items():
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tick = time.monotonic()
    with (base/(name+'.stdout.log')).open('x') as stdout,(base/(name+'.stderr.log')).open('x') as stderr:
        result = subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=125)
    records.append(dict(name=name,argv=argv,start=start,end=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_s=time.monotonic()-tick,exit=result.returncode))
    (base/'execution.json').write_text(json.dumps(records,indent=2)+'\n')
    if result.returncode: sys.exit(result.returncode)
