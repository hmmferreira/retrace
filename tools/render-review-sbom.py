"""Render CycloneDX installed-component evidence; declarations are not clearance."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
v=json.loads(args.inventory.read_text());components=[]
for item in v['python']:
    name=re.sub('[-_.]+','-',item['name']).lower()
    value={'type':'library','name':item['name'],'version':item['version'],
        'purl':'pkg:pypi/'+name+'@'+quote(item['version'],safe=''),
        'properties':[{'name':'retrace:license-review','value':'wheel declarations; embedded components require separate source review'}]}
    if item['license_expression']:value['licenses']=[{'expression':item['license_expression']}]
    components.append(value)
for item in v['debian']:
    components.append({'type':'library','name':item['name'],'version':item['version'],
        'purl':'pkg:deb/debian/'+quote(item['name'],safe='')+'@'+quote(item['version'],safe='')+'?arch='+quote(item['architecture'],safe='')+'&distro=debian-12'})
for name,repo,revision,license_id in [
    ('FindMy.py shared protocol','parawanderer/FindMy.py','8ecfae6cb34b29caf0bd8176ee73155ca81415a8','MIT'),
    ('Retained macOS engine source','parawanderer/os-findmy-e','595d39810639d750715babc30b063d4ac8f2c437','GPL-2.0-only')]:
    components.append({'type':'library','name':name,'version':revision,'purl':'pkg:github/'+repo+'@'+revision,
                       'licenses':[{'expression':license_id}]})
value={'bomFormat':'CycloneDX','specVersion':'1.6','version':1,
    'metadata':{'component':{'type':'application','name':'Retrace shared runtime review snapshot','version':'2026.11.22-review'},
    'properties':[{'name':'retrace:scope','value':'installed Python/OS plus retained source; Apple private runtime artifact excluded'},
                  {'name':'retrace:image-id','value':v['image_id']}]},'components':components}
args.output.write_text(json.dumps(value,indent=2)+'\n')
