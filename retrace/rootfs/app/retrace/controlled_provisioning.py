"""Explicit async machine provisioning orchestration; experimental, not UI enabled.

No account password, implicit download, file persistence or default native worker.
The worker interface is not itself process isolation: deployment must supply an
isolated implementation whose logs and network access are restricted.
"""
import asyncio
import base64
import hashlib
import math
import os
from pathlib import Path
import plistlib
import re
import stat
from datetime import datetime, timezone
from typing import Protocol

from .apple_transport import OwnedHttpSession, TransportBlocked, validate_destination

LOOKUP="https://gsa.apple.com/grandslam/GsService2/lookup"
START="https://gsa.apple.com/grandslam/MidService/startMachineProvisioning"
FINISH="https://gsa.apple.com/grandslam/MidService/finishMachineProvisioning"
MAX_ARTIFACT=64*1024*1024
MAX_FIELD=1024*1024
MAX_STATE=16*1024*1024

class ProvisioningBlocked(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)

class ProvisioningWorker(Protocol):
    """One-use private worker, with no account credentials or HTTP capability.

    prepare returns only the three device identity header values; begin returns
    CPIM; finish consumes PTM/TK and returns provisioning state for OfflineSigner.
    Worker retains native session handles and must reap them on close/cancellation.
    A real implementation must isolate native logs and disable worker networking.
    """
    async def prepare(self,verified_artifact:bytes)->dict[str,str]: ...
    async def begin(self,spim:bytes)->bytes: ...
    async def finish(self,ptm:bytes,tk:bytes)->bytes: ...
    async def close(self)->None: ...

def _artifact(path,digest):
    if not isinstance(digest,str) or not re.fullmatch("[a-f0-9]{64}",digest):
        raise ProvisioningBlocked("reviewed_artifact_required")
    try:
        fd=os.open(Path(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=MAX_ARTIFACT:
                raise ProvisioningBlocked("artifact_invalid")
            value=stream.read(MAX_ARTIFACT+1)
    except (OSError,TypeError,ValueError):
        raise ProvisioningBlocked("artifact_unavailable") from None
    if len(value)>MAX_ARTIFACT or hashlib.sha256(value).hexdigest()!=digest:
        raise ProvisioningBlocked("artifact_digest_mismatch")
    return value

def _binary(value):
    if not isinstance(value,str) or not 0<len(value)<=((MAX_FIELD+2)//3)*4:
        raise ProvisioningBlocked("provisioning_response_invalid")
    try: decoded=base64.b64decode(value,validate=True)
    except ValueError: raise ProvisioningBlocked("provisioning_response_invalid") from None
    if not 0<len(decoded)<=MAX_FIELD:raise ProvisioningBlocked("provisioning_response_invalid")
    return decoded

async def provision_new_identity(library,expected_sha256,*,worker=None,transport=None,
                                 create_new_identity=False,timeout=90,
                                 user_agent="akd/1.0 CFNetwork/1404.0.5 Darwin/22.3.0"):
    """Return private state bytes, never write them or replace an existing identity.

    There is deliberately no production worker fallback. Callers must provide a
    reviewed isolated worker; merely implementing this Protocol is not isolation.
    Transport is owned and closed here. No stage or passcode is automatically retried.
    """
    if create_new_identity is not True:
        raise ProvisioningBlocked("explicit_new_identity_required")
    if worker is None:
        raise ProvisioningBlocked("isolated_provisioning_worker_required")
    if not isinstance(timeout,(float,int)) or isinstance(timeout,bool) or not math.isfinite(timeout) or not 0<timeout<=90:
        raise ProvisioningBlocked("provisioning_options_invalid")
    if not isinstance(user_agent,str) or not user_agent or len(user_agent)>1024 or any(ord(c)<32 or ord(c)>126 for c in user_agent):
        raise ProvisioningBlocked("provisioning_options_invalid")
    if transport is not None and (not isinstance(transport,OwnedHttpSession) or transport.profile!="provisioning"):
        raise ProvisioningBlocked("owned_transport_required")
    http=transport
    try:
        async with asyncio.timeout(timeout):
            artifact=await asyncio.to_thread(_artifact,library,expected_sha256)
            identity=await worker.prepare(artifact)
            del artifact
            keys=("X-Mme-Device-Id","X-MMe-Client-Info","X-Apple-I-MD-LU")
            if not isinstance(identity,dict) or set(identity)!=set(keys) or any(
                not isinstance(value,str) or not value or len(value)>1024
                or any(ord(c)<32 or ord(c)>126 for c in value) for value in identity.values()):
                raise ProvisioningBlocked("worker_identity_invalid")
            if http is None:http=OwnedHttpSession(profile="provisioning",timeout=min(timeout,30))
            async def request(method,url,payload=None):
                validate_destination("provisioning",method,url)
                headers={**identity,"User-Agent":user_agent,
                    "Content-Type":"application/x-www-form-urlencoded","X-Apple-Client-App-Name":"Setup",
                    "X-Apple-I-Client-Time":datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
                options={"headers":headers}
                if payload is not None:options["data"]=plistlib.dumps({"Header":{},"Request":payload})
                response=await http.request(method,url,**options)
                if not response.ok:raise ProvisioningBlocked("provisioning_request_failed")
                return response.plist()
            bag=(await request("GET",LOOKUP)).get("urls")
            # Verify both routes before sending either protocol payload. No fallback,
            # suffix permission, alternative operation, or server-directed redirect.
            if not isinstance(bag,dict) or bag.get("midStartProvisioning")!=START or bag.get("midFinishProvisioning")!=FINISH:
                raise ProvisioningBlocked("provisioning_endpoints_changed")
            start=await request("POST",START,{})
            spim=_binary(start.get("Response",{}).get("spim"))
            cpim=await worker.begin(spim)
            if not isinstance(cpim,bytes) or not 0<len(cpim)<=MAX_FIELD:
                raise ProvisioningBlocked("worker_output_invalid")
            finish=await request("POST",FINISH,{"cpim":base64.b64encode(cpim).decode("ascii")})
            response=finish.get("Response",{})
            ptm,tk=_binary(response.get("ptm")),_binary(response.get("tk"))
            state=await worker.finish(ptm,tk)
            if not isinstance(state,bytes) or not 0<len(state)<=MAX_STATE:
                raise ProvisioningBlocked("worker_output_invalid")
            return state
    except asyncio.CancelledError:raise
    except TimeoutError:raise ProvisioningBlocked("provisioning_timeout") from None
    except ProvisioningBlocked:raise
    except TransportBlocked as exc:raise ProvisioningBlocked(exc.code) from None
    except Exception:raise ProvisioningBlocked("provisioning_failed") from None
    finally:
        # A worker close must reap its process. Bounded cleanup is a second line
        # of defense, not a claim that arbitrary threads can be interrupted.
        async def cleanup():
            tasks=[worker.close()]
            if http is not None:tasks.append(http.close())
            results=await asyncio.gather(*tasks,return_exceptions=True)
            if any(isinstance(result,BaseException) for result in results):
                raise ProvisioningBlocked("provisioning_cleanup_failed")
        cleanup_task=asyncio.create_task(cleanup())
        try:await asyncio.wait_for(asyncio.shield(cleanup_task),5)
        except asyncio.CancelledError:
            cleanup_task.cancel()
            raise
        except TimeoutError:
            cleanup_task.cancel()
            raise ProvisioningBlocked("provisioning_cleanup_timeout") from None
