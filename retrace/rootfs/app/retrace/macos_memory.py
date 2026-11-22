"""Candidate in-memory CoreADI adapter; no imports of the upstream CLI.

The restricted native child constructs/injects the pinned CoreADI engine.
This layer has no HTTP or disk interface. Its caller must broker provisioning and
persist encrypted snapshots, and discard a failed worker rather than replay it.
"""
import base64
import re

STORE='/Users/Shared/adi/'
LIMIT=1024*1024

class CandidateBlocked(RuntimeError):
    pass

def blob(value):
    if not isinstance(value,bytes) or not 0<len(value)<=LIMIT:
        raise CandidateBlocked('invalid_binary')
    return value

def result(value):
    if value.rc<0 or value.ret<0:raise CandidateBlocked('native_operation_failed')
    return value.outputs

def valid_store_name(name):
    # Names are keys in an in-memory virtual filesystem, never host paths.
    return (isinstance(name,str) and name not in ('.','..','adi.pb') and
            re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',name) is not None)

class MemoryCore:
    def __init__(self,core,host_uuid,*,saved=None):
        if not isinstance(host_uuid,str) or not re.fullmatch('[a-f0-9]{32}',host_uuid):
            raise CandidateBlocked('invalid_host_uuid')
        self.core=core
        self.phase='closed'
        self.session=None
        core.stubs.hostuuid=bytes.fromhex(host_uuid)
        if saved is not None:
            if not isinstance(saved,dict) or not 0<len(saved)<=32:
                raise CandidateBlocked('invalid_snapshot')
            decoded={}
            for name,encoded in saved.items():
                if (not valid_store_name(name)
                        or not isinstance(encoded,str) or not 0<=len(encoded)<=4*((LIMIT+2)//3)):
                    raise CandidateBlocked('invalid_snapshot')
                try:
                    raw=base64.b64decode(encoded,validate=True)
                    if len(raw)>LIMIT:raise ValueError()
                    decoded[STORE+name]=bytearray(raw)
                except (ValueError,TypeError):raise CandidateBlocked('invalid_snapshot') from None
            if sum(map(len,decoded.values()))>4*LIMIT:raise CandidateBlocked('snapshot_too_large')
            core.stubs.files.update(decoded)
        result(core.initialize())
        provisioned=core.is_machine_provisioned(-2)
        if provisioned.rc<0:raise CandidateBlocked('native_operation_failed')
        if saved is not None:
            if provisioned.ret!=0:raise CandidateBlocked('saved_machine_not_provisioned')
            self.phase='ready'
        else:
            if provisioned.ret==0:raise CandidateBlocked('unexpected_provisioned_machine')
            self.phase='new'

    def __repr__(self):return '<MacMemoryCore redacted>'

    def begin(self,spim,*,consent=False):
        if self.phase!='new' or consent is not True:raise CandidateBlocked('explicit_provisioning_required')
        blob(spim)
        self.phase='closed'
        output=result(self.core.provisioning_start(-2,spim))
        cpim=blob(output.get('cpim'))
        handle=output.get('session_id')
        if type(handle) is not int or not 0<=handle<2**32:raise CandidateBlocked('invalid_native_session')
        self.session=handle
        self.phase='provisioning'
        return cpim

    def finish(self,ptm,tk,routing):
        if self.phase!='provisioning':raise CandidateBlocked('invalid_phase')
        blob(ptm);blob(tk)
        if type(routing) is not int or not 0<=routing<2**64:raise CandidateBlocked('invalid_routing')
        self.phase='closed'
        handle,self.session=self.session,None
        result(self.core.provisioning_end(handle,ptm,tk))
        result(self.core.set_routing(-2,routing))
        result(self.core.is_machine_provisioned(-2))
        self.phase='ready'
        try:return self.snapshot()
        except BaseException:
            self.phase='closed';raise

    def headers(self):
        if self.phase!='ready':raise CandidateBlocked('invalid_phase')
        self.phase='closed'
        output=result(self.core.request_otp(-2))
        otp=blob(output.get('otp'));mid=blob(output.get('mid'))
        routing=result(self.core.get_routing(-2)).get('routing')
        if type(routing) is not int or not 0<=routing<2**64:raise CandidateBlocked('invalid_routing')
        self.phase='ready'
        state=self.snapshot()
        return {'X-Apple-I-MD':base64.b64encode(otp).decode(),
                'X-Apple-I-MD-M':base64.b64encode(mid).decode(),
                'X-Apple-I-MD-RINFO':str(routing)},state

    def snapshot(self):
        if self.phase!='ready':raise CandidateBlocked('invalid_phase')
        data={}
        for path,value in self.core.stubs.files.items():
            if not path.startswith(STORE):continue
            name=path[len(STORE):]
            if name=='adi.pb':continue
            if not valid_store_name(name):raise CandidateBlocked('invalid_snapshot')
            value=bytes(value)
            if len(value)>LIMIT:raise CandidateBlocked('invalid_snapshot')
            data[name]=value
        if not 0<len(data)<=32 or not 0<sum(map(len,data.values()))<=4*LIMIT:raise CandidateBlocked('invalid_snapshot')
        return {name:base64.b64encode(value).decode() for name,value in data.items()}
