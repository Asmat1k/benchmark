import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'src/analysis'))
sys.path.insert(0, str(ROOT/'docker'))
from sender_quality import evaluate
from calibration_report import directions


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


run = ROOT/'results/verify/diagnostic/sender-diagnostic.LwaxQMJP'
folder = run/'baseline-q1'
inventory = {str(p.relative_to(run)):digest(p) for p in run.rglob('*') if p.is_file()}
entries = json.loads((run/'captured.json').read_text())
assert all(digest(ROOT/r['path']) == r['sha256'] for r in entries)
assert json.loads((run/'sources-before.json').read_text()) == json.loads((run/'sources-after.json').read_text())
probe = json.loads((folder/'probe.json').read_text())
assert {r['id'] for r in probe['reply_records']} == set(range(10000))
assert len(probe['reply_records']) == 10000
network = directions(folder, probe)
assert all('0 packets dropped by kernel' in (folder/f'{role}.log').read_text() for role in ('browser','server'))
original = evaluate(probe['sent_records'], 10000)
assert original == json.loads((folder/'sender-quality.json').read_text())
reply = {r['id']:r['rtt_ms'] for r in probe['reply_records']}
cluster = [dict(r, rtt_ms=reply[r['id']]) for r in probe['sent_records'][5186:5196]]
paced = []
last = None
for row in probe['sent_records']:
    ns = round(row['t_send_ms']*1e6)
    ns = max(ns, last+2_500_000) if last is not None else ns
    paced.append(dict(row, t_send_ms=ns/1e6))
    last = ns
result = dict(raw=str(run.relative_to(ROOT)), sealed_files_verified=len(entries),
              source_inventories_equal=True, network=network,
              observed=original, cluster=cluster,
              pacing_scenario=dict(min_spacing_ms=2.5, evaluation=evaluate(paced,10000),
                  limitation='Offline timing scenario: original send times are lower bounds, each later send also follows prior adjusted send by >=2.5ms. Future OS pauses, receive processing, RTT and loss are not simulated. This is not a measured passing run.'),
              decision='Keep v2 failed. Propose separately versioned bounded catch-up pacing; no sender change or new measurement performed.')
assert inventory == {str(p.relative_to(run)):digest(p) for p in run.rglob('*') if p.is_file()}
Path(__file__).with_name('analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
