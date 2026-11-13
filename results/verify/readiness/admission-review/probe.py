import json
import os
import sys
import tempfile
from pathlib import Path

from acceptance import paired_schedule
from admission import accepted_schedule, checked, phase_path, ref, validate_schedule_extension
from experiments import publish_prepared
from raw import read, write
from schedule import make_schedule

with tempfile.TemporaryDirectory() as workspace:
    root = Path(workspace)
    for phase, parent, count in (('aa','verify',20), ('monitoring','verify',20), ('pilot','pilot',5), ('main','main',20)):
        dest = root/'results'/parent/('fixture-'+phase)
        stage = dest.parent/'.prepare-test'/dest.name
        stage.mkdir(parents=True)
        schedule = (paired_schedule(phase,dest.name,False,count) if phase in ('aa','monitoring')
                    else make_schedule(phase,dest.name,count,4))
        accepted_schedule(schedule,phase)
        phase_path(stage,schedule)
        phase_path(dest,schedule)
        write(stage/'schedule.json',schedule)
        write(stage/'ledger.json',dict(schema_version=1,series_id=dest.name,attempts=schedule['blocks']))
        frozen = root/'frozen-plan.json'
        original = frozen if phase=='main' else stage/'schedule-original.json'
        write(original,schedule)
        link=ref(original)
        if phase!='main':
            link['path']=str(dest/'schedule-original.json')
        write(stage/'admission.json',dict(schedule=link))
        validate_schedule_extension(stage,schedule,schedule)
        publish_prepared(stage,dest,phase)
        assert checked(read(dest/'admission.json')['schedule']).read_bytes() == (dest/'schedule.json').read_bytes()
        print(phase, 'schedule publication and final reference pass')
    for name in ('pilot','main'):
        for where in (root/'results'/name/'.prepare-test'/'aa',root/'results'/name/'aa'):
            try:
                phase_path(where,{'series':'verify'})
            except ValueError:
                continue
            raise AssertionError('accepted wrong phase')
    print('all four staged/final phase-path conflicts refused')
