import json
from pathlib import Path
import sys

sys.path[:0]=['src/analysis','docker']
from admission import aggregate, checked, ref, sources
from calibration_report import collection_plan
from raw import read

base=Path('results/verify/readiness/stage4/practical-v1')
release=base/'release-v2'
env=Path('results/verify/diagnostic/timer-timer.JHhehRVV/context.json')
assert sources()==read(release/'source-inventory.json')
reports=read(release/'REPORT_MAP.json')
assert set(reports)=={'build','tls','path','timer','raw','analysis'}
result,code=aggregate(reports,env,kind='real')
assert code==2 and not result['final']
assert all(row['status']==('passed' if row['id'] in reports else 'not_run') for row in result['document']['checks'])
bridge=read(base/'applicability/qualification-and-bw-bridge-v2.json')
assert bridge['current_sources']==sources() and bridge['environment']==ref(env)
assert len(bridge['default_sender_results'])==3 and all(r['quality']['status']=='passed' for r in bridge['default_sender_results'])
for entry in read(checked(bridge['qualification'])): checked(entry)
checked(bridge['historical_bw_replay'])
assert read(base/'full-calibration/collection-plan.json')==collection_plan()
review=read(release/'timer-independent-review.json')
assert review['status']=='passed_internal_independent_raw_review'
assert review['source_commit']==read(release/'release.json')['head']
assert review['collection']=='results/verify/diagnostic/timer-timer.JHhehRVV'
assert review['report']==ref(Path(reports['timer']))
checked(review['report'])
print(json.dumps(dict(status='passed',scope='six early gates and dependency applicability; not stage4/main acceptance',source_count=len(sources()))))
