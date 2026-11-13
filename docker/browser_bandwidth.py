import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/analysis'))

from admission import checked, ref, sources
from calibration_report import rate
from diagnostic_input import diagnostic_raw
from raw import read, require, rows
from schedule import make_schedule


ACCOUNTING = 'router netem dequeued skb bytes including Ethernet header; excludes FCS/preamble/IFG'


def load_rates(folder):
    spec = read(folder/'run.json')
    require((spec['warmup_slots'], spec['measurement_slots'], spec['interval_ms']) == (200, 1200, 50),
            'bandwidth requires ordinary 20Hz load')
    slots = rows(folder/'warmup.jsonl') + rows(folder/'slots.jsonl')
    require(len(slots) == 1400 and all(s['send_state']=='sent' and s['first_correct_echo_ms'] is not None
                                      for s in slots), 'incomplete ordinary browser load')
    snapshots = []
    for when in ('before', 'stable'):
        queues = [q for q in read(folder/f'qdisc-{when}.json') if q['kind']=='netem']
        require(len(queues)==2 and {q['dev'] for q in queues}=={'to_server','to_browser'}, 'qdisc coverage')
        require(all(q['qlen']==0 and q['backlog']==0 for q in queues), 'undrained browser queue')
        snapshots.append({q['dev']: q for q in queues})
    result = []
    duration = spec['measurement_slots']*spec['interval_ms']/1000
    for direction, dev in (('forward','to_server'), ('reverse','to_browser')):
        first, last = [snapshot[dev] for snapshot in snapshots]
        require(first['options']==last['options'] and first['handle']==last['handle'], 'qdisc changed')
        require(last['drops']==first['drops'], 'browser qdisc loss')
        require(all(type(q[k]) is int and q[k]>=0 for q in (first,last) for k in ('bytes','packets')) and
                last['bytes']>first['bytes'] and last['packets']>first['packets'], 'invalid browser counters')
        count = last['bytes']-first['bytes']
        result.append(dict(direction=direction, bytes=count, denominator_s=duration,
                           mbit_s_upper=count*8/duration/1e6,
                           first=first, last=last))
    return result


def fractions(loads, capacity):
    require({r['mode'] for r in loads}=={'WS','WT-S'} and len(loads)==2, 'both ordinary browser modes required')
    require(len(capacity)==4 and {(c['loss'], c['direction']) for c in capacity}==
            {(loss, d) for loss in (0,.01) for d in ('forward','reverse')}, 'capacity coverage')
    ratios = []
    for load in loads:
        require(len(load['rates'])==2 and {r['direction'] for r in load['rates']}=={'forward','reverse'}, 'load directions')
        for sample in load['rates']:
            rates = [c['forwarded_bytes']*8/c['duration_s']/1e6 for c in capacity
                     if c['direction']==sample['direction']]
            require(all(math.isfinite(v) and 9<=v<=11 for v in rates), 'capacity outside calibration limits')
            offered = sample['mbit_s_upper']
            require(math.isfinite(offered) and offered>0, 'invalid browser rate')
            ratios.append(dict(mode=load['mode'], direction=sample['direction'],
                               capacity_mbit_s=min(rates), fraction=offered/min(rates)))
    maximum = max(r['fraction'] for r in ratios)
    return dict(accounting_level=ACCOUNTING, main_bandwidth_fraction=maximum,
                status='passed' if maximum<.1 else 'failed', ratios=ratios,
                limitation='Conservative bound: all setup/warmup/measurement/drain bytes divided by 60 s; baseline only')


def package(directory, calibration):
    hashes = sources()
    schedule = read(directory/'schedule.json')
    expected = make_schedule('diagnostic', directory.name, 1, 1, baseline=True)
    expected['generator_hz'] = 20
    require(schedule==expected, 'ordinary baseline diagnostic schedule required')
    require(not (directory/'STOP').exists() and read(directory/'ledger.json')==
            dict(schema_version=1, series_id=directory.name,
                 attempts=[dict(b,status='complete') for b in schedule['blocks']]), 'incomplete diagnostic ledger')
    require(not (directory/'SYNTHETIC.json').exists(), 'synthetic bandwidth collection')
    require(read(calibration/'sources-before.json')==read(calibration/'sources-after.json')==hashes,
            'calibration source mismatch')
    context = read(directory/'context.json')
    require(context==read(calibration/'context-before.json')==read(calibration/'context-after.json'),
            'bandwidth/calibration environment mismatch')
    require((calibration/'exit').read_text().strip()=='0', 'incomplete calibration collection')
    evidence = [ref(directory/'schedule.json'), ref(directory/'context.json'), ref(calibration/'captured.json')]
    for binding in read(calibration/'captured.json'):
        checked(binding)
    loads = []
    for run in schedule['runs']:
        folder = diagnostic_raw(directory, run, schedule, context, hashes)
        loads.append(dict(mode=run['mode'], rates=load_rates(folder)))
        evidence.extend(ref(p) for p in sorted(folder.iterdir()) if p.is_file())
    capacity = [rate(calibration/f'saturation-{loss}-{direction}', direction, loss/100)
                for loss in (0,1) for direction in ('forward','reverse')]
    return dict(fractions(loads, capacity), loads=loads, capacity=capacity, evidence=evidence,
                source_hashes=hashes, environment=context)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('diagnostic', type=Path)
    parser.add_argument('calibration', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = package(args.diagnostic, args.calibration)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
    raise SystemExit(0 if result['status']=='passed' else 1)
