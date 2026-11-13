import sys,json,struct
from pathlib import Path
sys.path.insert(0,'docker')
from calibration_report import ingress
from calibration_probe import collection_tag
root=Path('results/verify/diagnostic/calibration.ZQRTHB2H/r20p1-before')
probe=json.loads((root/'probe.json').read_text())
tag=collection_tag(probe['collection_id'])
sent={r['id'] for r in probe['sent_records']}
returned={r['id'] for r in probe['reply_records']}
f=ingress(root/'browser.pcap',bytes([172,28,10,10]),bytes([172,28,20,10]),tag)
r=ingress(root/'server.pcap',bytes([172,28,20,10]),bytes([172,28,10,10]),tag)
for dev,entered,delivered in [('to_server',f,r),('to_browser',r,returned)]:
    before=next(q for q in json.loads((root/'qdisc-before.json').read_text()) if q.get('dev')==dev)
    after=next(q for q in json.loads((root/'qdisc-after.json').read_text()) if q.get('dev')==dev)
    print(dev,'entered',len(entered),'delivered',len(delivered),'UDP lost',len(entered-delivered),'tc dropped',after['drops']-before['drops'],'packets delta',after['packets']-before['packets'],'byte delta',after['bytes']-before['bytes'])
    print('lost IDs',sorted(entered-delivered))
for p in root.glob('*.pcap'):
    frame_types={}
    records=[]
    data=p.read_bytes();o=24
    while o<len(data):
        sec,usec,n,total=struct.unpack_from('<IIII',data,o);o+=16
        packet=data[o:o+n];o+=n
        kind=packet[12:14].hex()
        frame_types[kind]=frame_types.get(kind,0)+1
        if kind!='0800':records.append(dict(timestamp=sec+usec/1e6,length=total,type=kind))
    print(p.name,frame_types,records)
