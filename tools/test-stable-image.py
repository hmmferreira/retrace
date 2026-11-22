"""Build a rendered stable app and probe fresh startup without Apple network access."""
import argparse
import io
import json
from pathlib import Path
import struct
import tarfile
import urllib.request
from build_context import allowed_path

p=argparse.ArgumentParser();p.add_argument('app',type=Path);args=p.parse_args()
key=(Path.home()/'.config/portainer/api-key').read_text().strip()
base=(Path.home()/'.config/portainer/docker-api-url').read_text().strip()
def api(path,data=None,method=None,raw=False,content='application/json'):
    body=data if isinstance(data,bytes) else None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(base+path,data=body,headers={'X-API-Key':key,'Content-Type':content},method=method)
    with urllib.request.urlopen(req,timeout=300) as r:result=r.read()
    return result if raw else json.loads(result) if result else None
image='dragon/retrace-stable-review:0.2.0'
context=io.BytesIO()
with tarfile.open(fileobj=context,mode='w') as archive:
    for path in sorted(args.app.rglob('*')):
        if path.is_file() and allowed_path(path.relative_to(args.app)):
            archive.add(path,arcname=str(path.relative_to(args.app)))
req=urllib.request.Request(base+'/build?t='+image+'&rm=1',data=context.getvalue(),
                          headers={'X-API-Key':key,'Content-Type':'application/x-tar'},method='POST')
with urllib.request.urlopen(req,timeout=1800) as r:
    for line in r:
        try:value=json.loads(line)
        except ValueError:continue
        if 'error' in value:raise RuntimeError(value['error'])
        text=value.get('stream','').strip()
        if any(s in text for s in ('Step ','Successfully ')):print(text,flush=True)
script=Path(__file__).with_name('stable-startup-smoke.py').read_text()
spec={'Image':image,'User':'1000:1000','Cmd':['python','-c',script],
      'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'CapDrop':['ALL'],
      'SecurityOpt':['no-new-privileges:true'],'Tmpfs':{'/data':'rw,nosuid,mode=1777,size=64m','/tmp':'rw,nosuid,size=32m'}}}
cid=api('/containers/create',spec,'POST')['Id']
try:
    api('/containers/'+cid+'/start',{},'POST');status=api('/containers/'+cid+'/wait',{},'POST')['StatusCode']
    raw=api('/containers/'+cid+'/logs?stdout=1&stderr=1',raw=True)
    while len(raw)>=8:
        size=struct.unpack('>I',raw[4:8])[0];print(raw[8:8+size].decode(),end='');raw=raw[8+size:]
    if status:raise SystemExit(status)
finally:api('/containers/'+cid+'?force=true',method='DELETE')
