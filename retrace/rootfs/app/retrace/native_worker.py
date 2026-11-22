"""Bounded async IPC to a one-use, fail-closed Linux native worker."""
import asyncio
import base64
import json
import os
from pathlib import Path
import signal
import struct
import sys

from .controlled_provisioning import ProvisioningBlocked,MAX_ARTIFACT,MAX_STATE,MAX_FIELD
from .offline_signer import OfflineSigner,SignerBlocked

_WORKER_SCRIPT=Path(__file__).with_name("native_worker_child.py")
_MAX_REQUEST=128*1024*1024
_MAX_REPLY=24*1024*1024


def _encode(value,limit):
    if not isinstance(value,bytes) or not 0<len(value)<=limit:
        raise ProvisioningBlocked("worker_input_invalid")
    return base64.b64encode(value).decode("ascii")

def _decode(value,limit):
    if not isinstance(value,str) or not 0<len(value)<=4*((limit+2)//3):
        raise ProvisioningBlocked("worker_output_invalid")
    try:result=base64.b64decode(value,validate=True)
    except ValueError:raise ProvisioningBlocked("worker_output_invalid") from None
    if not 0<len(result)<=limit:raise ProvisioningBlocked("worker_output_invalid")
    return result

class _NativeChannel:
    def __init__(self):
        self._process=None;self._reader=None;self._pipe_transport=None
        self._lock=asyncio.Lock();self._closed=False;self._boundary=None
    def __repr__(self):return "<NativeChannel redacted>"
    async def _read(self):
        header=await self._reader.readexactly(4)
        size=struct.unpack("!I",header)[0]
        if not 0<size<=_MAX_REPLY:raise ProvisioningBlocked("worker_output_invalid")
        value=json.loads(await self._reader.readexactly(size))
        if not isinstance(value,dict) or value.get("ok") is not True:
            code=value.get("error") if isinstance(value,dict) else None
            error=ProvisioningBlocked(code if code in ("worker_boundary_unavailable","native_worker_failed") else "native_worker_failed")
            if isinstance(value,dict) and value.get('component') in {'macos_child.py','macos_memory.py','adi_run.py','harness.py','stubs.py','macho.py'} and type(value.get('line')) is int:
                error.component=value['component'];error.line=value['line']
            raise error
        return value
    async def _start(self):
        read_fd,write_fd=os.pipe()
        try:
            spawn=asyncio.create_task(asyncio.create_subprocess_exec(sys.executable,"-I","-S","-B",str(_WORKER_SCRIPT),str(write_fd),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,
                pass_fds=(write_fd,),close_fds=True,start_new_session=True,cwd="/",
                env={"PATH":"/usr/bin:/bin","LANG":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1"}))
            try:self._process=await asyncio.shield(spawn)
            except asyncio.CancelledError:
                # Acquire the handle even if cancellation races process creation;
                # exchange() then kills/reaps it before propagating cancellation.
                self._process=await spawn
                raise
        except BaseException:
            os.close(read_fd)
            raise
        finally:os.close(write_fd)
        reader=asyncio.StreamReader(limit=65536)
        protocol=asyncio.StreamReaderProtocol(reader)
        try:
            self._pipe_transport,_=await asyncio.get_running_loop().connect_read_pipe(lambda:protocol,os.fdopen(read_fd,"rb",buffering=0))
        except BaseException:
            os.close(read_fd)
            raise
        self._reader=reader
        ready=await self._read()
        if set(ready)!={"ok","ready","boundary"} or ready.get("ready") is not True or ready.get("boundary") not in {"landlock3-seccomp-v1","apparmor-seccomp-v1"}:
            raise ProvisioningBlocked("worker_boundary_unavailable")
        self._boundary=ready["boundary"]
    async def exchange(self,command,**fields):
        try:
            async with self._lock:
                if self._closed:raise ProvisioningBlocked("worker_closed")
                async with asyncio.timeout(40):
                    if self._process is None:await self._start()
                    value=json.dumps({"command":command,**fields},separators=(",",":")).encode()
                    if not 0<len(value)<=_MAX_REQUEST:raise ProvisioningBlocked("worker_input_invalid")
                    self._process.stdin.write(struct.pack("!I",len(value))+value)
                    await self._process.stdin.drain()
                    return await self._read()
        except BaseException as exc:
            await self.close()
            if isinstance(exc,asyncio.CancelledError):raise
            if isinstance(exc,ProvisioningBlocked):raise
            raise ProvisioningBlocked("native_worker_failed") from None
    async def close(self):
        self._closed=True
        process=self._process
        if process is not None:
            if process.returncode is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:await asyncio.wait_for(process.wait(),2)
            except TimeoutError:raise ProvisioningBlocked("worker_reap_failed") from None
            finally:
                if process.stdin is not None:process.stdin.close()
                if self._pipe_transport is not None:self._pipe_transport.close()
        self._reader=None

async def verify_native_boundary():
    """Prove startup boundary without reading/loading any artifact or account."""
    channel=_NativeChannel()
    try:
        async with asyncio.timeout(10):
            await channel._start()
            return channel._boundary
    except asyncio.CancelledError:raise
    except ProvisioningBlocked:raise
    except Exception:raise ProvisioningBlocked("worker_boundary_unavailable") from None
    finally:await channel.close()

class IsolatedNativeWorker:
    """Native provisioning in Landlock/seccomp worker; no network/data access."""
    def __init__(self,*,uid=None,devid=None,client_info=None):
        values=(uid,devid,client_info)
        if any(value is not None for value in values):
            if any(not isinstance(value,str) or not value or len(value)>1024
                   or any(ord(c)<32 or ord(c)>126 for c in value) for value in values):
                raise ProvisioningBlocked("worker_identity_invalid")
            self._device={"uid":uid,"devid":devid.upper(),"client_info":client_info}
        else:self._device=None
        self._channel=_NativeChannel();self._phase="new"
    def __repr__(self):return "<IsolatedNativeWorker redacted>"
    async def prepare(self,verified_artifact):
        if self._phase!="new":raise ProvisioningBlocked("worker_state_invalid")
        self._phase="starting"
        fields={"mode":"provisioning","artifact":_encode(verified_artifact,MAX_ARTIFACT)}
        if self._device is not None:fields["device"]=self._device
        value=await self._channel.exchange("prepare",**fields)
        self._phase="prepared"
        return value.get("identity")
    async def begin(self,spim):
        if self._phase!="prepared":raise ProvisioningBlocked("worker_state_invalid")
        self._phase="starting"
        value=await self._channel.exchange("begin",spim=_encode(spim,MAX_FIELD))
        self._phase="begun"
        return _decode(value.get("cpim"),MAX_FIELD)
    async def finish(self,ptm,tk):
        if self._phase!="begun":raise ProvisioningBlocked("worker_state_invalid")
        self._phase="finishing"
        value=await self._channel.exchange("finish",ptm=_encode(ptm,MAX_FIELD),tk=_encode(tk,MAX_FIELD))
        self._phase="finished"
        return _decode(value.get("state"),MAX_STATE)
    async def close(self):
        self._phase="closed"
        await self._channel.close()

class ProcessOfflineSigner(OfflineSigner):
    """OfflineSigner contract backed by restricted process, never native threads.

    Private snapshots are refreshed alongside each signing result. snapshot() is
    nonblocking and refuses export while a native operation is pending.
    """
    def __init__(self,library,state,expected_sha256):
        super().__init__(library,state,expected_sha256)
        self._channel=_NativeChannel();self._operation=asyncio.Lock()
        self._snapshot=None;self._busy=False;self._initialized=False
    @property
    def ready(self):return self._initialized and not self._closed
    def __repr__(self):return "<ProcessOfflineSigner redacted>"
    async def initialize(self):
        async with self._operation:
            if self._closed:raise SignerBlocked("signer_closed")
            if self._initialized:return
            self._busy=True
            try:
                artifact=await asyncio.to_thread(self._read_artifact)
                value=await self._channel.exchange("prepare",mode="signing",artifact=_encode(artifact,self.MAX_ARTIFACT),state=_encode(self._state,self.MAX_STATE))
                if self._closed:raise SignerBlocked("signer_closed")
                self._snapshot=_decode(value.get("state"),self.MAX_STATE)
                self._initialized=True
            except BaseException as exc:
                await self.close()
                if isinstance(exc,asyncio.CancelledError):raise
                if isinstance(exc,SignerBlocked):raise
                if isinstance(exc,ProvisioningBlocked):raise SignerBlocked(exc.code) from None
                raise SignerBlocked("signer_initialization_failed") from None
            finally:self._busy=False;self._state=None
    async def headers(self):
        async with self._operation:
            if not self.ready:raise SignerBlocked("signer_closed" if self._closed else "signer_not_ready")
            self._busy=True
            try:
                value=await self._channel.exchange("headers")
                headers=value.get("headers")
                keys={"X-Apple-I-MD","X-Apple-I-MD-M"}
                if not isinstance(headers,dict) or set(headers)!=keys or any(
                    not isinstance(text,str) or not text or len(text)>8192 or any(c in text for c in "\r\n\x00") for text in headers.values()):
                    raise SignerBlocked("signer_output_invalid")
                state=_decode(value.get("state"),self.MAX_STATE)
                if self._closed:raise SignerBlocked("signer_closed")
                self._snapshot=state
                return headers
            except BaseException as exc:
                await self.close()
                if isinstance(exc,asyncio.CancelledError):raise
                if isinstance(exc,SignerBlocked):raise
                if isinstance(exc,ProvisioningBlocked):raise SignerBlocked(exc.code) from None
                raise SignerBlocked("signing_failed") from None
            finally:self._busy=False
    async def identity_checks(self,expected):
        """Compare saved native metadata in the sandbox; return booleans only."""
        async with self._operation:
            if not self.ready:raise SignerBlocked("signer_not_ready")
            if not isinstance(expected,dict) or set(expected)!={"uid","devid","client_info"} or any(
                not isinstance(v,str) or not v or len(v)>1024 or any(ord(c)<32 or ord(c)>126 for c in v)
                for v in expected.values()):raise SignerBlocked("identity_check_failed")
            self._busy=True
            try:
                reply=await self._channel.exchange("identity_check",expected=expected)
                checks=reply.get("checks")
                if not isinstance(checks,dict) or set(checks)!={"device_id_matches","local_user_matches","client_info_matches"} or any(type(v) is not bool for v in checks.values()):
                    raise SignerBlocked("identity_check_failed")
                return dict(checks)
            except BaseException as error:
                await self.close()
                if isinstance(error,asyncio.CancelledError):raise
                raise SignerBlocked("identity_check_failed") from None
            finally:self._busy=False

    def snapshot(self):
        if not self.ready or self._snapshot is None:raise SignerBlocked("signer_not_ready")
        if self._busy:raise SignerBlocked("signer_busy")
        return self._snapshot
    async def close(self):
        self._revoke();self._snapshot=None;self._initialized=False
        await self._channel.close()
