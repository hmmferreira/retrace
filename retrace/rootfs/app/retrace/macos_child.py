"""Executed only inside the existing networkless native worker boundary."""
import base64
import hashlib
import json
from pathlib import Path
import sys
from macos_memory import MemoryCore

DIGEST='2eafc3c79c7f41a8afbfbeaaf23ee5dab5ad5bda55ec8e54dbc0ddf1d20ce630'

def create(library,host_uuid,saved=None):
    if hashlib.sha256(library).hexdigest()!=DIGEST:raise ValueError()
    source=Path(__file__).with_name('mac_engine')
    pins=json.loads((source/'PROVENANCE.json').read_text())['files']
    for name in ('adi_run.py','harness.py','stubs.py','macho.py'):
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=pins[name]:raise ValueError()
    sys.path.insert(0,str(source))
    from adi_run import CoreADI,identify_build
    from harness import MachOImage,Harness
    from stubs import MacStubs
    # Construct the pinned engine from brokered bytes; never call its path loader.
    core=CoreADI.__new__(CoreADI)
    core.build,core.dispatch=identify_build(library)
    core.harness=Harness(MachOImage('verified-coreadi',data=library))
    core.stubs=MacStubs(core.harness,log=False)
    core.last_insns=0
    return MemoryCore(core,host_uuid,saved=saved)
