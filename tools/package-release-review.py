"""Prepare a deterministic source review archive; never publish an approved app.

The existing stable renderer/workflow gate is deliberately not bypassed. Packages
contain source/notices/review evidence only and no Apple binaries or private state.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import gzip
from build_context import allowed_path

ROOT=Path(__file__).resolve().parents[1]

def package(root,output):
    root=Path(root);output=Path(output)
    revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain']).strip():raise ValueError('Commit the reviewed source first')
    paths=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
    selected=[]
    for name in paths:
        if not name:continue
        path=Path(name)
        if not allowed_path(path):continue
        if path.parts[0] not in ('retrace','custom_components','docs','tools','security','tests','experiments') and name not in ('LICENSE','README.md','AGENTS.md','CLAUDE.md','repository.yaml','hacs.json'):continue
        if (root/path).is_symlink():raise ValueError('Symlinks are not review archive inputs')
        selected.append(name)
    manifest={'schema_version':1,'source_revision':revision,'release_status':'review-only-not-approved',
              'installable_release':False,'intended_version':'0.2.0','intended_channel':'stable',
              'apple_native_permission':'unresolved','public_prebuilt_images':False,
              'history_migration':False,'stable_edge_state':'independent',
              'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in selected}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as gz,tarfile.open(fileobj=gz,mode='w') as archive:
        def add(name,data):
            info=tarfile.TarInfo('retrace-release-review/'+name);info.size=len(data);info.mode=0o644;info.mtime=0
            archive.addfile(info,io.BytesIO(data))
        add('REVIEW_MANIFEST.json',json.dumps(manifest,indent=2,sort_keys=True).encode()+b'\n')
        for name in selected:add(name,(root/name).read_bytes())
    return {'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'source_revision':revision,'files':len(selected),'installable_release':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(package(ROOT,args.output)))
