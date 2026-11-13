import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root/'src/analysis'))
from admission import sources
from diagnostic_input import collect
from raw import read, write, digest

with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    for name in ('src','configs','docker','Makefile','compose.yaml','docs'):
        (work/name).symlink_to(root/name)
    original = root/'results/verify/measurement/smoke.yXogitrZ'
    directory = work/'results/verify/diagnostic'/original.name
    shutil.copytree(original,directory)
    os.chdir(work)
    schedule = read(directory/'schedule.json')
    schedule['collect_timer'] = True
    write(directory/'schedule.json',schedule)
    folder = directory/'raw'/schedule['runs'][0]['run_id']
    write(folder/'collection-sources.json',sources())
    write(folder/'clock-samples.json',[i/100 for i in range(100001)])
    (folder/'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(folder.iterdir()) if p.name!='SHA256SUMS'))
    true_env = read(folder/'context.json')
    forged = dict(true_env,host='foreign-host')
    write(directory/'context.json',forged)
    try:
        collect('timer',[directory],directory/'context.json',work/'output','WS')
    except ValueError as exc:
        print('Rejected foreign context:',exc)
        sys.exit(0)
    print('Accepted foreign host despite preserved raw context:',true_env['host']!=forged['host'])
    sys.exit(1)
