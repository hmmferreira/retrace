"""Collect public package/license metadata from a disposable, networkless image.

Never start the app, mount household data, inspect running containers or include
Apple binary bytes. Metadata is evidence, not an automatic license approval.
"""
import argparse
import json
from pathlib import Path
import struct
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--image',default='dragon/retrace-shared:0.1.14')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
key=(Path.home()/'.config/portainer/api-key').read_text().strip()
base=(Path.home()/'.config/portainer/docker-api-url').read_text().strip()
def api(path,data=None,method=None,raw=False):
    req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),
        headers={'X-API-Key':key,'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=90) as r:value=r.read()
    return value if raw else json.loads(value) if value else None
code=r'''import hashlib,importlib.metadata as md,json,subprocess
from pathlib import Path
packages=[]
for dist in sorted(md.distributions(),key=lambda d:d.metadata['Name'].lower()):
 metadata=dist.metadata;notices=[]
 for item in dist.files or []:
  name=str(item);leaf=Path(name).name.lower()
  if ('/licenses/' in name or leaf.startswith(('license','licence','copying','notice'))):
   path=dist.locate_file(item).resolve()
   if not str(path).startswith('/usr/local/lib/python3.12/site-packages/') or not path.is_file():continue
   data=path.read_bytes()
   if len(data)>1048576:raise RuntimeError('notice_too_large')
   notices.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'text':data.decode('utf-8',errors='replace')})
 packages.append({'name':metadata['Name'],'version':dist.version,
  'license_expression':metadata.get('License-Expression'),
  'license_field':metadata.get('License'),
  'license_classifiers':[v for v in metadata.get_all('Classifier',[]) if v.startswith('License ::')],
  'project_urls':metadata.get_all('Project-URL',[]),'requires':dist.requires or [],'notices':notices})
os_packages=[]
for line in subprocess.check_output(['dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\n'],text=True).splitlines():
 name,version,arch=line.split('\t');path=Path('/usr/share/doc')/name/'copyright'
 data=path.read_bytes() if path.is_file() else None
 os_packages.append({'name':name,'version':version,'architecture':arch,'copyright_sha256':hashlib.sha256(data).hexdigest() if data else None})
print(json.dumps({'schema_version':1,'scope':'disposable shared image; no app runtime state','python':packages,'debian':os_packages}))
'''
image=api('/images/'+args.image+'/json')
spec={'Image':args.image,'User':'1000:1000','Cmd':['python','-c',code],
      'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'CapDrop':['ALL'],
                    'SecurityOpt':['no-new-privileges:true']}}
cid=api('/containers/create',spec,'POST')['Id']
try:
    api('/containers/'+cid+'/start',{},'POST')
    status=api('/containers/'+cid+'/wait',{},'POST')['StatusCode']
    raw=api('/containers/'+cid+'/logs?stdout=1&stderr=1',raw=True);output=b''
    while len(raw)>=8:
        size=struct.unpack('>I',raw[4:8])[0];output+=raw[8:8+size];raw=raw[8+size:]
    if status:raise RuntimeError('inventory_failed')
    value=json.loads(output);value['image_id']=image['Id']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'python_packages':len(value['python']),'debian_packages':len(value['debian']),
                      'python_notice_files':sum(len(d['notices']) for d in value['python'])}))
finally:api('/containers/'+cid+'?force=true',method='DELETE')
