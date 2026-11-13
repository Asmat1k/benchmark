from pathlib import Path

from raw import read, require

PRIMARY_IDS = {
    'build': ('locked-install','native-platform','versions','archive-hashes'),
    'tls': ('ws-secure','wts-secure','https-wrong-ca','https-wrong-san','https-expired','ws-wrong-ca','ws-wrong-san','ws-expired','wt-wrong-pin','wt-expired'),
    'path': ('routes','tcp-forward','tcp-reverse','udp-forward','udp-reverse','forwarding-off-ws','forwarding-off-wts','offload-mtu','profile-readback'),
    'raw': ('framing','clock-boundaries','slot-accounting','hash-integrity','log-completeness','resource-coverage','replacement-recovery'),
    'analysis': ('metrics-boundaries','full-n-sign','holm4','rank-intervals','paired-bootstrap','null-family','offline-reference'),
    'reproduction': ('archive-hashes','offline-build','offline-analysis','main-negative-guards','environment-gates','interval-decision-drift-review'),
}


def environment(path, kind='real'):
    from admission import checked
    value=read(path)
    if kind=='real':
        require(value.get('kind')!='synthetic' and not any((parent/'SYNTHETIC.json').exists() for parent in [path.parent,*path.parents]), 'synthetic environment')
        require({'bindings','host','vm','leaf','config','services'} <= set(value), 'actual context required')
        require({s['role'] for s in value['services']}=={'browser','server','router'}, 'environment service coverage')
        require(value['bindings'] and value['host'] and value['vm'] and value['leaf'], 'incomplete environment')
    return value


def primary(data):
    from admission import checked
    from jsonschema import Draft202012Validator
    collection=read(checked(data['collection']))
    Draft202012Validator(read(Path('docs/schemas/collection.schema.json'))).validate(collection)
    require(all(collection[k]==data[k] for k in ('kind','gate','collection_id','environment','source_hashes')), 'foreign collection provenance')
    payload=read(checked(collection['payload']))
    Draft202012Validator(read(Path('docs/schemas/primary-payload.schema.json'))).validate(payload)
    require(payload['collection_id']==data['collection_id'] and payload['gate']==data['gate'], 'foreign primary payload')
    return payload,collection


def imported(data):
    from admission import checked, validate_checks
    require(data['gate'] in PRIMARY_IDS, 'unsupported primary gate')
    payload,collection=primary(data)
    document=payload['document']
    require(data['document']==document, 'checks differ from primary document')
    expected=set(PRIMARY_IDS[data['gate']])
    require({r['id'] for r in document['checks']}==expected and all(r['mandatory'] for r in document['checks']), 'mandatory primary gate coverage')
    observations=payload['observations']
    require(set(observations)==expected, 'missing primary observations')
    for row in document['checks']:
        observation=observations[row['id']]
        require(row['expected'] is True, 'primary predicate expectation')
        if row['status'] in ('passed','failed'):
            require(isinstance(row['actual'],bool) and row['status']==('passed' if row['actual'] else 'failed'), 'primary predicate decision')
        require(observation['collection_id']==data['collection_id'] and observation['id']==row['id'], 'foreign primary observation')
        require(row['actual']==observation['actual'] and row['expected']==observation['expected'] and row['status']==observation['status'], 'primary/check mismatch')
        require(row['evidence']==observation['evidence'] and row['evidence'], 'primary evidence association')
        for evidence in observation['evidence']:
            path=checked(evidence)
            trace=read(path)
            require(trace['collection_id']==data['collection_id'] and trace['gate']==data['gate'] and trace['id']==row['id'], 'foreign trace collection')
            require(trace['actual']==row['actual'], 'trace measurement mismatch')
    if data['gate']=='reproduction':
        require(all(isinstance(data[k],str) and data[k].strip() for k in ('author_id','executor_id')) and data['author_id'].strip()!=data['executor_id'].strip(), 'independent reproduction executor required')
        from experiments import reproduction_comparison
        comparison=reproduction_comparison(data)
        code=validate_checks(document)
        status='failed' if code==1 else 'inconclusive' if code==2 else comparison['status']
        return dict(status=status,document=document,freeze=data['freeze'],comparison=comparison)
    code=validate_checks(document)
    return dict(status='passed' if code==0 else 'failed' if code==1 else 'inconclusive',document=document)


def measured(data):
    payload,_=primary(data)
    require(data['gate'] in ('timer','generator','calibration'), 'unsupported measured gate')
    values=payload['values']
    metadata={'kind','gate','collection_id','environment','source_hashes','collection','evidence'}
    require({k:v for k,v in data.items() if k not in metadata}==values, 'summary differs from collected primary records')
    if data['kind']=='real' and data['gate'] in ('timer','generator'):
        from admission import checked
        from diagnostic_input import observations
        actual, extra = observations(data['gate'], data['evidence'], read(checked(data['environment'])), data['source_hashes'])
        require(actual == values and all(payload.get(k) == v for k,v in extra.items()), 'diagnostic raw correspondence')
    if data['gate']=='timer':
        import numpy as np
        samples=payload['clock_samples_ms']
        require(len(samples)==100001 and np.isfinite(samples).all(), 'timer primary calls')
        delta=np.diff(samples)
        positive=delta[delta>0]
        actual=dict(count=100000,monotonic=bool(np.all(delta>=0)),step_ms=float(min(positive)) if len(positive) else None,
                    p99_overhead_ms=float(np.sort(delta)[98999]))
        require(all(values[k]==actual[k] for k in actual), 'timer summary differs from page clock')
    return values
