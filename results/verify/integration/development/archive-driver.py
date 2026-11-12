import subprocess,time,json,pathlib,hashlib
r=pathlib.Path('results/verify/integration/development');before=set(pathlib.Path('results/archives').glob('images-*.tar'));t=time.monotonic()
with (r/'archive.txt').open('w') as f:p=subprocess.run(['make','archive'],stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0
new=set(pathlib.Path('results/archives').glob('images-*.tar'))-before
assert len(new)==1,new
archive=new.pop();h=hashlib.sha256()
with archive.open('rb') as f:
 for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
assert h.hexdigest() in archive.name
with (r/'archive-load.txt').open('w') as f:p=subprocess.run(['docker','image','load','-i',str(archive)],stdout=f,stderr=subprocess.STDOUT)
(r/'archive-command.json').write_text(json.dumps(dict(command='make archive; independently SHA256 check; docker image load',archive=str(archive),sha256=h.hexdigest(),size=archive.stat().st_size,exit=p.returncode,seconds=time.monotonic()-t),indent=2));print(archive,p.returncode,time.monotonic()-t)
