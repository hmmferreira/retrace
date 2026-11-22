"""Async restricted-process Mac signer; one process per uncached signing window."""
import asyncio
import base64
import json
import os
import fcntl
import stat
import time
from .native_worker import _NativeChannel,_encode,_decode
from .offline_signer import OfflineSigner,SignerBlocked
from .macos_artifact import LIBRARY_SHA

class MacSigner(OfflineSigner):
    def __init__(self,library,state,expected_sha256):
        super().__init__(library,state,expected_sha256)
        self._snapshot=state;self._initialized=False;self._operation=asyncio.Lock()
        self._window=None;self._headers_cache=None
    @property
    def ready(self):return self._initialized and not self._closed
    @property
    def machine(self):
        from .macos_identity import validate_machine
        return validate_machine(json.loads(self._snapshot))
    async def initialize(self):
        if self.digest!=LIBRARY_SHA:raise SignerBlocked('artifact_digest_mismatch')
        self.machine
        await asyncio.to_thread(self._read_artifact)
        self._initialized=True
    async def headers(self):
        async with self._operation:
            if not self.ready:raise SignerBlocked('signer_closed')
            window=int(time.time())//30
            if self._window==window and self._headers_cache is not None:return dict(self._headers_cache)
            channel=_NativeChannel();lock_fd=None
            try:
                lock_fd=os.open(self.library.parent/'signer.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
                info=os.fstat(lock_fd)
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077:raise SignerBlocked('signing_failed')
                deadline=time.monotonic()+45
                while True:
                    try:fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        if time.monotonic()>deadline:raise SignerBlocked('signing_failed')
                        await asyncio.sleep(.05)
                from .macos_store import MachineStore
                store=MachineStore(self.library.parent)
                expected=self.machine
                machine=await asyncio.to_thread(store.load)
                if any(machine[key]!=expected[key] for key in ('host_uuid','uid','devid','serial','routing')):raise SignerBlocked('signing_failed')
                artifact=await asyncio.to_thread(self._read_artifact)
                response=await channel.exchange('mac_prepare',artifact=_encode(artifact,self.MAX_ARTIFACT),host_uuid=machine['host_uuid'],saved=machine['saved'])
                if response.get('phase')!='ready':raise SignerBlocked('signer_initialization_failed')
                response=await channel.exchange('mac_headers')
                headers=response.get('headers')
                if not isinstance(headers,dict) or set(headers)!={'X-Apple-I-MD','X-Apple-I-MD-M','X-Apple-I-MD-RINFO'}:
                    raise SignerBlocked('signer_output_invalid')
                for key in ('X-Apple-I-MD','X-Apple-I-MD-M'):
                    text=headers[key]
                    if not isinstance(text,str) or len(text)>8192 or not base64.b64decode(text,validate=True):raise SignerBlocked('signer_output_invalid')
                if headers['X-Apple-I-MD-RINFO']!=str(machine['routing']):raise SignerBlocked('signer_output_invalid')
                machine['saved']=response['saved']
                from .macos_identity import validate_machine
                validate_machine(machine)
                from .shared_runtime import _persist
                await _persist(lambda:store.save(machine))
                self._snapshot=json.dumps(machine,separators=(',',':')).encode()
                self._window=window;self._headers_cache=dict(headers)
                return dict(headers)
            except BaseException:
                self._closed=True;self._headers_cache=None
                raise
            finally:
                try:await channel.close()
                finally:
                    if lock_fd is not None:os.close(lock_fd)
    def snapshot(self):
        if not self.ready or self._operation.locked():raise SignerBlocked('signer_busy')
        return self._snapshot
    async def close(self):
        self._closed=True;self._initialized=False;self._headers_cache=None
