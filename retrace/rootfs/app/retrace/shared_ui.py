"""Explicitly injected shared-account UI adapter; never enabled by default.

Composition must supply a reviewed account factory and private session writer.
This module never creates an account, restores SDK state or accepts another login.
"""
import asyncio
from .shared_discovery import SharedDiscovery, SharedDiscoveryError

class SharedDiscoveryUI:
    def __init__(self, commit, *, factory=None):
        options={} if factory is None else {"factory":factory}
        self.flow=SharedDiscovery(commit,**options)
        self.account=None
        self.watcher=None
        self.auth_task=None
        self.auth_owner=None
        self.auth_state={"phase":"idle"}
        self.worker=None
        self._commands=asyncio.Lock()

    def bind(self,worker):
        # Never accidentally route household credentials to the production SDK
        # constructor or default (password-containing SDK) serialization path.
        if worker.account_factory is None or worker.session_writer is None:
            raise ValueError("reviewed_account_lifecycle_required")
        self.worker=worker
        worker.authenticated=self.authenticated

    def visible(self,owner):
        return self.flow.visible(owner)

    def auth_visible(self,owner):
        if self.auth_owner not in (None,owner):return {"phase":"busy"}
        if (self.auth_state.get("phase") in ("choose_method","verification_code") and
                self.worker is not None and self.worker.pending is None):
            self.auth_state={"phase":"failed","error":"sign_in_expired"}
        return dict(self.auth_state)

    @staticmethod
    def _auth_error(error):
        code=getattr(error,"code",None)
        if code in {"session_expired","reauthentication_required"}:return "session_expired"
        if code in {"authentication_failed","authentication_network_error","verification_rejected",
                    "verification_not_accepted","verification_rate_limited","code_request_failed",
                    "invalid_verification_code","discovery_handoff_failed","sign_in_expired","setup_required","apple_signin_refused","credentials_rejected",
                    "authentication_protocol_error","authentication_state_error"}:return code
        if code in {"session_snapshot_failed","session_key_required","session_storage_invalid","session_storage_unavailable","session_save_failed"}:return "session_save_failed"
        if code in {"artifact_unavailable","artifact_digest_mismatch","artifact_review_required","reviewed_artifact_required",
                    "isolated_provisioning_worker_required","worker_boundary_unavailable","explicit_new_identity_required",
                    "signing_identity_missing","signing_identity_invalid"}:return "setup_required"
        return "authentication_required"

    async def authenticate(self,owner,operation):
        if self._commands.locked() or self.auth_owner not in (None,owner) or (self.auth_task and not self.auth_task.done()):
            raise SharedDiscoveryError("busy")
        if self.flow.owner is not None:
            if self.flow.owner!=owner or self.flow.state.get("phase") in ("working","input"):
                raise SharedDiscoveryError("busy")
        self.auth_owner=owner
        self.auth_state={"phase":"working"}
        async def run():
            try:
                if self.flow.owner is not None:
                    await self.flow.cancel(owner)
                    if self.watcher:await self.watcher
                self.auth_state=await operation()
            except asyncio.CancelledError:raise
            except Exception as error:self.auth_state={"phase":"failed","error":self._auth_error(error)}
        self.auth_task=asyncio.create_task(run())
        return self.auth_visible(owner)

    async def authenticated(self,owner,account):
        if self.account is not None:raise SharedDiscoveryError("busy")
        await self.flow.start(owner,account)
        self.account=account
        async def watch():
            try:
                while self.flow.state.get("phase") in ("working","input"):
                    await asyncio.sleep(.1)
            finally:
                if self.account is account:
                    self.account=None
                    if hasattr(account,"_password"):account._password=None
                    try:
                        async with asyncio.timeout(10):await account.close()
                    except Exception:pass
        self.watcher=asyncio.create_task(watch())

    async def action(self,owner,data):
        async with self._commands:
            if data.get("action")=="answer":
                return await self.flow.unlock(owner,data.get("choice"),data.get("passcode"))
            if data.get("action")=="cancel":
                await self.flow.cancel(owner)
                if self.watcher:await self.watcher
                return self.flow.visible(owner)
            # Restored location tokens cannot silently obtain a fresh PET.
            raise SharedDiscoveryError("authentication_required")

    async def cancel_auth(self,owner):
        async with self._commands:
            if self.auth_owner not in (None,owner):raise SharedDiscoveryError("not_owner")
            if self.auth_task and not self.auth_task.done():
                self.auth_task.cancel()
                await asyncio.gather(self.auth_task,return_exceptions=True)
            await self.worker.cancel(owner)
            self.auth_state={"phase":"cancelled"}
            self.auth_owner=None

    async def close(self):
        if self.auth_owner is not None:await self.cancel_auth(self.auth_owner)
        await self.flow.cancel(self.flow.owner)
        if self.watcher:await self.watcher


def compose_shared_ui(store, *, account_factory, session_writer, session_available,
                      discovery_factory=None):
    """Explicit experimental composition; never constructs a default provider.

    Caller supplies reviewed provisioning/restoration and encrypted persistence.
    Availability checks only local presence; restore/reporting validates contents.
    """
    from .worker import AppleWorker
    from .shared_inventory import PrivateInventorySink
    from .apple_transport import OwnedHttpSession
    if not all(callable(value) for value in (account_factory,session_writer,session_available)):
        raise ValueError("reviewed_account_lifecycle_required")
    async def checked_factory(provider=None,*,native_consent=False):
        account=await account_factory(provider,**({"native_consent":True} if native_consent else {})) if provider is not None else await account_factory()
        transport=getattr(account,"_http",None)
        if not isinstance(transport,OwnedHttpSession) or transport.profile!="account":
            if account is not None:
                if hasattr(account,"_password"):account._password=None
                try:
                    async with asyncio.timeout(10):await account.close()
                except Exception:pass
            raise SharedDiscoveryError("owned_transport_required")
        return account
    worker=AppleWorker(store,account_factory=checked_factory,session_writer=session_writer,
                       session_available=session_available)
    bridge=SharedDiscoveryUI(PrivateInventorySink(store,worker),factory=discovery_factory)
    bridge.bind(worker)
    return worker,bridge
