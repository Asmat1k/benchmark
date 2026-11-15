import json
from pathlib import Path
import sys

sys.path[:0] = ['src/analysis','docker']
from admission import sources
from browser_bandwidth import package

run=Path('results/verify/diagnostic/browser-bandwidth-v4.9r51339s')
old=Path('results/verify/diagnostic/calibration.lShojabe')
assert not (run/'STOP').exists() and json.loads((run/'queue.json').read_text()) == []
result=package(run,old)
assert result['status']=='passed'
Path('/out/historical-bandwidth-replay.json').write_text(json.dumps(dict(result=result,source_hashes=sources(),scope='Historical494e1a99 replay, not current gate'),indent=2)+'\n')
print('Historical immutable BW and calibration integrity replay passed; no current calibration claim.')
