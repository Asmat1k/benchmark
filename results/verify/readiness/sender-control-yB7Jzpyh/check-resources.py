import json
from pathlib import Path
import re
import struct

out=Path(__file__).parent
results={}
for run in sorted(Path('results/verify/diagnostic').glob('sender-diagnostic.*')):
    row={}
    for role in ('browser','server'):
        with (next(run.glob('*/'+role+'.pcap'))).open('rb') as f:
            endian='<' if f.read(4)==b'\xd4\xc3\xb2\xa1' else '>'
            f.read(20)
            while record:=f.read(16):
                frame=f.read(struct.unpack(endian+'IIII',record)[2])
                if frame[12:14]==b'\x08\x00':
                    break
        for prefix,mac,ip,dev in (('router-',frame[6:12],f'172.28.{10 if role=="browser" else 20}.10',f'to_{role}'),
                                  ('',frame[:6],f'172.28.{10 if role=="browser" else 20}.2','bench0')):
            for suffix in ('','-after'):
                path=run/f'{prefix}{role}-neighbors{suffix}.json'
                records=json.loads(path.read_text())
                assert len(records)==1
                value=records[0]
                assert value['dst']==ip and value.get('dev',dev)==dev and value['state']==['PERMANENT']
                assert value['lladdr']==':'.join(f'{x:02x}' for x in mac)
    row['neighbor_mac_ip_dev_permanent_before_after']=True
    for path in sorted(run.glob('*/probe.json')):
        collection={}
        for role in ('browser','server'):
            samples=[json.loads(x) for x in (path.parent/f'{role}-resources.jsonl').read_text().splitlines()]
            def snmp(s):
                lines=s['/proc/net/snmp'].splitlines()
                keys=next(x.split()[1:] for x in lines if x.startswith('Udp:') and 'InDatagrams' in x)
                values=next(x.split()[1:] for x in lines if x.startswith('Udp:') and 'InDatagrams' not in x)
                return dict(zip(keys,map(int,values)))
            a,b=snmp(samples[0]),snmp(samples[-1])
            queue_max=[0,0]
            for s in samples:
                for line in s['/proc/net/udp'].splitlines()[1:]:
                    values=[int(x,16) for x in line.split()[4].split(':')]
                    queue_max=[max(x,y) for x,y in zip(queue_max,values)]
            collection[role]=dict(udp_counters_delta={k:b[k]-v for k,v in a.items()},
                                  socket_queue_max_sampled_tx_rx_bytes=queue_max)
        text=(path.parent/'router-resources.txt').read_text()
        qs=[q for line in text.splitlines() if line.startswith('[') for q in json.loads(line) if q['kind']=='netem']
        throttle=[int(x) for x in re.findall(r'^nr_throttled (\d+)$',text,re.M)]
        throttled=[int(x) for x in re.findall(r'^throttled_usec (\d+)$',text,re.M)]
        collection['router']=dict(max_qlen_sampled=max(q['qlen'] for q in qs),max_backlog_sampled=max(q['backlog'] for q in qs),
                                  nr_throttled_delta=throttle[-1]-throttle[0],throttled_usec_delta=throttled[-1]-throttled[0])
        row[path.parent.name]=collection
    results[run.name]=row
(out/'resource-checks.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
