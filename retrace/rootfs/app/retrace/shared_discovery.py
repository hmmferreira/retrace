"""Experimental app-owned discovery controller over one authenticated account.

No exporter process, password prompt, trust-circle join or account mutation API.
The protocol backend is injected and is not installed in the production image.
"""
import asyncio
from copy import deepcopy
import secrets
import time

class SharedDiscoveryError(RuntimeError):
    def __init__(self,code):
        super().__init__(code)
        self.code=code

class TokenLease:
    """One existing account/identity, with an expiring token, never a password."""
    def __init__(self,account,token,*,clock=time.monotonic,lifetime=240):
        if not isinstance(token,str) or not token:
            raise SharedDiscoveryError("authentication_required")
        self._account,self._token=account,token
        self._clock,self._until=clock,clock()+lifetime
    def __getattr__(self,name):
        return getattr(self._account,name)
    async def request_pet(self):
        if self._token is None or self._clock()>=self._until:
            raise SharedDiscoveryError("authentication_required")
        return self._token
    def release(self):
        self._token=None

class ReadOnlyClient:
    """Expose only the recovery/read operations; no join/rename/delete API."""
    def __init__(self,client,lease):
        self._client,self._lease=client,lease
    async def recovery_options(self):
        return await self._client.recovery_options()
    async def unlock(self,record,passcode):
        return await self._client.unlock(record,passcode)
    async def accessories(self):
        return await self._client.accessories()
    async def close(self):
        self._lease.release()
        await self._client.close()

async def python_client(account):
    # A capability check: released FindMy 0.10.2 does not offer this protocol.
    # Never fall back to Rust or ask for another independent account login.
    try:
        from findmy.icloud import AsyncFindMyClient
        from .owned_protocol import open_shared_client
    except ImportError:
        raise SharedDiscoveryError("backend_unavailable") from None
    from .apple_transport import OwnedHttpSession
    transport=getattr(account,"_http",None)
    if not isinstance(transport,OwnedHttpSession) or transport.profile!="account":
        raise SharedDiscoveryError("owned_transport_required")
    if not callable(getattr(account,"request_pet",None)):
        raise SharedDiscoveryError("backend_incompatible")
    try:
        # One service-token exchange using the already authenticated identity,
        # while the main sign-in still owns the transient password in memory.
        token=await account.request_pet()
    finally:
        if hasattr(account,"_password"):
            account._password=None
    lease=TokenLease(account,token)
    try:
        client=await open_shared_client(lease)
    except BaseException:
        lease.release()
        raise
    return ReadOnlyClient(client,lease)

def label(record):
    values=[]
    for field in ("device_name","device_model"):
        value=getattr(record,field,None)
        if isinstance(value,str):
            value="".join(c for c in value if c.isprintable()).strip()[:80]
            if value: values.append(value)
    return " · ".join(values) or "Trusted device"

class SharedDiscovery:
    def __init__(self,commit,*,factory=python_client,timeout=90,lifetime=600):
        self.commit,self.factory=commit,factory
        self.timeout,self.lifetime=timeout,lifetime
        self.owner=None
        self.state={"phase":"idle"}
        self.client=None
        self.task=None
        self.expiry=None
        self.records={}
        self.generation=0
        self.deadline=0
        self._pending_account=None

    def visible(self,owner):
        if self.owner is not None and owner!=self.owner:
            return {"phase":"busy"}
        return deepcopy(self.state)

    def _owned(self,owner):
        if self.owner!=owner or self.owner is None:
            raise SharedDiscoveryError("not_owner")
        if time.monotonic()>self.deadline:
            raise SharedDiscoveryError("expired")

    async def start(self,owner,account):
        if not isinstance(owner,str) or not owner:
            raise SharedDiscoveryError("invalid_owner")
        if self.owner is not None:
            raise SharedDiscoveryError("busy")
        if getattr(getattr(account,"login_state",None),"name",None)!="LOGGED_IN":
            raise SharedDiscoveryError("authentication_required")
        self.owner=owner
        self.generation+=1
        self.deadline=time.monotonic()+self.lifetime
        self.state={"phase":"working","step":"discover_recovery_devices"}
        self._pending_account=account
        self.task=asyncio.create_task(self._run(lambda:self._prepare(account)))
        self.expiry=asyncio.create_task(self._expire(owner,self.generation))
        return self.visible(owner)

    async def _prepare(self,account):
        try:
            self.client=await self.factory(account)
        finally:
            # The caller hands off a *freshly authenticated* account. A backend
            # may need another service-token exchange while the password is in
            # RAM. It must not retain it for later silent reauthentication.
            if hasattr(account,"_password"):
                account._password=None
            self._pending_account=None
        options=await self.client.recovery_options()
        recoverable=list(options.recoverable)
        if not recoverable:
            raise SharedDiscoveryError("no_recovery_devices")
        self.records={secrets.token_urlsafe(18):record for record in recoverable}
        self.state={"phase":"input","kind":"device_unlock",
            "choices":[{"value":key,"label":label(record)} for key,record in self.records.items()]}

    async def unlock(self,owner,choice,passcode):
        self._owned(owner)
        if self.state.get("phase")!="input" or not isinstance(choice,str) or choice not in self.records:
            raise SharedDiscoveryError("invalid_choice")
        if not isinstance(passcode,str) or not passcode or len(passcode)>512 or any(c in passcode for c in "\x00\r\n"):
            raise SharedDiscoveryError("invalid_passcode")
        record=self.records[choice]
        self.records={}
        self.state={"phase":"working","step":"unlock_and_discover"}
        self.task=asyncio.create_task(self._run(lambda:self._unlock(record,passcode)))
        return self.visible(owner)

    async def _unlock(self,record,passcode):
        try:
            await self.client.unlock(record,passcode)
        finally:
            passcode=None
        accessories=await self.client.accessories()
        if not isinstance(accessories,list) or len(accessories)>10000:
            raise SharedDiscoveryError("invalid_inventory")
        # Keys never enter visible state. The private sink must validate and
        # atomically merge inventory, preserving item selection and identities.
        await self.commit(accessories)
        self.state={"phase":"complete","item_count":len(accessories)}
        await self._close_client()
        self._finish()

    async def _run(self,operation):
        try:
            async with asyncio.timeout(self.timeout):
                await operation()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            code=error.code if isinstance(error,SharedDiscoveryError) else (
                "timed_out" if isinstance(error,TimeoutError) else
                "authentication_required" if type(error).__name__ in ("UnauthorizedError","InvalidCredentialsError") else "discovery_failed")
            self.state={"phase":"failed","error":code}
            await self._close_client()
            self._finish()

    def _finish(self):
        self.records={}
        if self.expiry and self.expiry is not asyncio.current_task():
            self.expiry.cancel()
        self.expiry=None
        # Retain owner until dismissal so another user cannot read its result.

    async def _expire(self,owner,generation):
        await asyncio.sleep(self.lifetime)
        if self.owner==owner and self.generation==generation:
            await self.cancel(owner,phase="expired")

    async def _close_client(self):
        client,self.client=self.client,None
        if client is not None:
            try:
                async with asyncio.timeout(10): await client.close()
            except Exception:
                pass

    async def cancel(self,owner,*,phase="cancelled"):
        if self.owner is not None and self.owner!=owner:
            raise SharedDiscoveryError("not_owner")
        task,self.task=self.task,None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        if self._pending_account is not None:
            if hasattr(self._pending_account,"_password"):
                self._pending_account._password=None
            self._pending_account=None
        await self._close_client()
        self._finish()
        self.owner=None
        self.state={"phase":phase}
