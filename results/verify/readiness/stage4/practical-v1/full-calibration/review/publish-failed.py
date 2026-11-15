import json
from pathlib import Path
import sys

sys.path[:0]=['src/analysis','docker']
from admission import aggregate, ref
from calibration_report import package
from experiments import main
from raw import read, write

base=Path('results/verify/readiness/stage4/practical-v1/full-calibration')
review=base/'review'
run=Path('results/verify/diagnostic/calibration.sFWOAzbo')
env=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
independent=read(review/'integrity-independent-with-neighbors.json')
numeric=read(review/'method-results.json')
preview=read(review/'numeric-preview.json')
assert independent['status']=='passed_internal_independent_integrity_review'
assert numeric['status']=='failed_independent_numeric_review'
assert preview['sealed_files']==independent['sealed_files']==146
bandwidth=read(review/'bandwidth-new-capacity.json')
assert bandwidth['status']=='passed'
trace_review=dict(independent_units=False, observed_period_reviewed=True,
    mtu_1500=True,no_fragmentation=True,no_unexpected_overflow=True,headers_accounted=True,
    survivor_bias_reviewed=True,reverse_denominator_reviewed=True,independent_direction_seeds=True,
    backlog_reviewed=True,main_bandwidth_fraction=bandwidth['main_bandwidth_fraction'])
review_path=review/'collection-review.json'
write(review_path,dict(collection_id=run.name,reviewer='Codex root integration with separate internal integrity and numeric reviewers; not external review',
    rationale='146sealedfiles and all14echo+4saturation checked. Setup enforces MTU1500; offload readbacks preserved, complete echo pcap header/ID/prefix parsing found no fragmentation. Echo dropped IDs exactly match netem counters; saturation overflow is deliberate offered>capacity and disclosed separately. RTT uses every returned packet, missing loss1 timing remains unknown; no sender-lag subtraction. Observed medians/proxy only, no CI/stationarity claim. Sender r80p1-after fails fixed late and shadow budgets; no repeat, exclusion or threshold change.',
    trace_review=trace_review,evidence=[ref(review/p) for p in ('integrity-independent-with-neighbors.json','integrity-independent.md','method-results.json','method-results.md','bandwidth-new-capacity.json')],
    limitations=['MTU verified by successful exact setup assertions, not separately saved numeric readback','Pcap snaplen96 does not retain complete payload; returned-payload checks are in sender','No endpoint resource or UDP-error counters exist in full calibration collector; causal scheduler attribution not claimed','Saturation intentionally overdrives rate and drops packets; no_unexpected_overflow is echo accounting assessment','ACF/drift retained descriptively; missing loss1 replies are not timely observations']))
package(run,review_path,env)
report=base/'calibration-sFWOAzbo-report.json'
sys.argv=['experiments.py','calibrate','--input',str(run/'publication/input.json'),'--environment',str(env),'--output',str(report),'--kind','real']
assert main()==1
actual=read(report)
assert actual['status']=='failed'
quality=actual['result']['sender_quality']['r80p1-after']
assert quality['status']=='failed' and quality['metrics']['late_slots']==242
mapping=read(Path('results/verify/readiness/stage4/practical-v1/release-v2/REPORT_MAP.json'))
mapping['calibration']=str(report)
write(base/'REPORT_MAP-failed-sFWOAzbo.json',mapping)
result,code=aggregate(mapping,env,kind='real')
assert code==1 and not result['final']
write(base/'verify-failed-sFWOAzbo.json',result)
write(base/'STOP-sFWOAzbo.json',dict(status='failed',collection=run.name,source_commit='acce5946499b7471bc35965919f3cdc910a7922c',
    reason='r80p1-after late242/10000=2.42%>1%; all4005lagproxywindows fail12countbudget',
    report=ref(report),verification=ref(base/'verify-failed-sFWOAzbo.json'),
    generator='not_run',stage4_complete=False,new_network_repeat_authorized_by_this_record=False,
    criteria_changed=False,raw_excluded=False,next_step='Specific causal evidence review; no unchanged full repeat or downstream prerequisite bypass'))
print('Published actual failed calibration; verify exit1 expected. Generator/aa/monitoring remain not_run.')
