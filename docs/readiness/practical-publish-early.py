from pathlib import Path
import sys

sys.path.insert(0,'src/analysis')
from admission import aggregate
from experiments import main
from raw import read, write

base=Path('results/verify/readiness/stage4/practical-v1/release-v2')
env=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
reports=dict(timer='results/verify/diagnostic/timer-timer.JHhehRVV-report/report.json')
for gate in ('build','tls','path','raw','analysis'):
    output=base/(gate+'-report.json')
    sys.argv=['experiments.py','import-checks','--input',str(base/'primary'/gate/'input.json'),'--output',str(output),'--environment',str(env),'--kind','real']
    assert main()==0
    assert read(output)['status']=='passed'
    reports[gate]=str(output)
write(base/'REPORT_MAP.json',reports)
result,code=aggregate(reports,env,kind='real')
write(base/'verify-pre-calibration.json',result)
assert code==2
assert sum(row['status']=='passed' for row in result['document']['checks'])==6
print('Six source-bound early gates passed; calibration/generator/aa/monitoring not_run; final=false; verify exit2 as expected.')
