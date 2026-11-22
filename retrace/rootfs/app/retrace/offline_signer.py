"""Offline-only ADI signing from verified artifacts and existing provisioning.

No downloading, provisioning, account login or HTTP client is provided here.
Native/crypto work is serialized and offloaded from the asyncio loop. This is
not an OS sandbox for malicious native/Python code, nor hard thread preemption.
"""
import asyncio
import base64
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import stat
import threading

class SignerBlocked(RuntimeError):
    def __init__(self,code):
        super().__init__(code)
        self.code=code

class NoProvisioning:
    # The library can update this reference if its VM is recreated. It is not a
    # network client; implicit reprovisioning always stops here.
    adi=None
    def provision(self,*args,**kwargs):
        raise SignerBlocked("provisioning_required")

def _build_engine(state,libraries):
    from anisette import Anisette
    from anisette._ani_provider import AnisetteProvider
    def no_download():
        raise SignerBlocked("artifact_incomplete")
    provider=AnisetteProvider.load(BytesIO(state),BytesIO(libraries),fs_fallback=no_download)
    provider._provisioning_session=NoProvisioning()
    return Anisette(provider)

class OfflineSigner:
    MAX_ARTIFACT=64*1024*1024
    MAX_STATE=16*1024*1024
    def __init__(self,library,state,expected_sha256):
        if not isinstance(expected_sha256,str) or not re.fullmatch("[a-f0-9]{64}",expected_sha256):
            raise SignerBlocked("artifact_digest_required")
        if not isinstance(state,bytes) or not 0<len(state)<=self.MAX_STATE:
            raise SignerBlocked("provisioning_state_required")
        self.library=Path(library)
        self.digest=expected_sha256
        self._state=state
        self._engine=None
        self._closed=False
        self._lock=threading.Lock()
    @property
    def ready(self):return self._engine is not None and not self._closed
    def __repr__(self):return "<OfflineSigner redacted>"
    def _read_artifact(self):
        try:
            fd=os.open(self.library,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,"rb") as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=self.MAX_ARTIFACT:
                    raise SignerBlocked("artifact_invalid")
                value=stream.read(self.MAX_ARTIFACT+1)
        except OSError:
            raise SignerBlocked("artifact_unavailable") from None
        if len(value)>self.MAX_ARTIFACT or hashlib.sha256(value).hexdigest()!=self.digest:
            raise SignerBlocked("artifact_digest_mismatch")
        return value
    def _initialize(self):
        with self._lock:
            if self._closed:raise SignerBlocked("signer_closed")
            if self._engine is not None:return
            try:
                state=self._state
                artifact=self._read_artifact()
                if self._closed:raise SignerBlocked("signer_closed")
                engine=_build_engine(state,artifact)
                if not engine.is_provisioned:raise SignerBlocked("provisioning_required")
                if self._closed:raise SignerBlocked("signer_closed")
                self._engine=engine
            except BaseException:
                self._closed=True
                raise
            finally:
                self._state=None
                if self._closed:self._engine=None
    async def initialize(self):
        try:
            await asyncio.to_thread(self._initialize)
            if self._closed:raise SignerBlocked("signer_closed")
        except asyncio.CancelledError:
            self._revoke()
            raise
        except SignerBlocked:raise
        except Exception:raise SignerBlocked("signer_initialization_failed") from None
    def _require_ready(self):
        if self._closed:raise SignerBlocked("signer_closed")
        if self._engine is None:raise SignerBlocked("signer_not_ready")
        if not self._engine.is_provisioned:raise SignerBlocked("provisioning_required")
    def _headers(self):
        with self._lock:
            self._require_ready()
            engine=self._engine
            value=engine.get_data()
            if self._closed:raise SignerBlocked("signer_closed")
            result={}
            for key in ("X-Apple-I-MD","X-Apple-I-MD-M"):
                text=value.get(key) if isinstance(value,dict) else None
                if not isinstance(text,str) or not text or len(text)>8192 or any(c in text for c in "\r\n\x00"):
                    raise SignerBlocked("signer_output_invalid")
                result[key]=text
            return result
    async def headers(self):
        try:
            result=await asyncio.to_thread(self._headers)
            if self._closed:raise SignerBlocked("signer_closed")
            return result
        except asyncio.CancelledError:
            self._revoke()
            raise
        except SignerBlocked:raise
        except Exception:raise SignerBlocked("signing_failed") from None
    def snapshot(self):
        with self._lock:
            self._require_ready()
            output=BytesIO()
            engine=self._engine
            engine.save_provisioning(output)
            if self._closed:raise SignerBlocked("signer_closed")
            value=output.getvalue()
            if not 0<len(value)<=self.MAX_STATE:raise SignerBlocked("provisioning_state_invalid")
            return value
    def _revoke(self):
        # Immediate logical revocation, independent of a blocked native lock.
        # A native call already in flight can finish using its local references,
        # but its result is rejected and initialization cannot publish an engine.
        self._closed=True
        self._state=None
        self._engine=None
    async def close(self):
        self._revoke()

def provider_for(signer,*,serial,identity=None,_mac=False):
    """Build the SDK interface around owned offline signing, not SDK networking."""
    from findmy.reports.anisette import BaseAnisetteProvider
    if not isinstance(signer,OfflineSigner) or not signer.ready:
        raise SignerBlocked("signer_not_ready")
    if not isinstance(serial,str) or not serial or len(serial)>128 or any(not c.isprintable() for c in serial):
        raise SignerBlocked("identity_required")
    class OfflineProvider(BaseAnisetteProvider):
        def __init__(self):
            options={"serial":serial}
            if identity is not None:options["identity"]=identity
            super().__init__(**options)
            self._owned_signer=signer
            self._prepared={}
            self._header_lock=asyncio.Lock()
        @property
        def otp(self):return self._prepared.get("X-Apple-I-MD","")
        @property
        def machine(self):return self._prepared.get("X-Apple-I-MD-M","")
        @property
        def router(self):
            return self._prepared.get('X-Apple-I-MD-RINFO','') if _mac else super().router
        async def get_headers(self,*args,**kwargs):
            async with self._header_lock:
                self._prepared=await signer.headers()
                try:return await super().get_headers(*args,**kwargs)
                finally:self._prepared={}
        def to_json(self,dst=None):
            if dst is not None:raise SignerBlocked("use_private_account_store")
            value={"type":"aniOwnedMac" if _mac else "aniOwnedOffline","serial":self.serial,"library_sha256":signer.digest,
                "prov_data":base64.b64encode(signer.snapshot()).decode("ascii")}
            if hasattr(self,"identity"):value["identity"]=self.identity.to_json()
            return value
        @classmethod
        def from_json(cls,*args,**kwargs):
            raise SignerBlocked("use_owned_account_restore")
        async def close(self):
            self._prepared={}
            await signer.close()
    return OfflineProvider()
