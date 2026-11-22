"""App-owned construction of candidate clients with constrained HTTP sessions.

Imports the pinned experimental protocol only when explicitly requested. No
monkeypatch of shared globals, default session factory or production SDK.
"""
import asyncio
import re
import uuid
from .apple_transport import OwnedHttpSession,TransportBlocked,validate_destination
from .offline_signer import OfflineSigner

async def _replace_http(client,profile,timeout):
    previous=client._http
    await previous.close()
    client._http=OwnedHttpSession(profile=profile,timeout=timeout)
    return client

async def create_account(provider,*,timeout=30,uid=None,devid=None):
    """Install HTTP before sign-in; refuse default remote/downloading providers."""
    signer=getattr(provider,"_owned_signer",None)
    if not isinstance(signer,OfflineSigner) or not signer.ready:
        raise TransportBlocked("owned_signer_required")
    options={}
    if uid is not None or devid is not None:
        try:
            if not isinstance(uid,str) or not isinstance(devid,str):raise ValueError()
            for value in (uid,devid):uuid.UUID(value)
        except (ValueError,TypeError,AttributeError):raise TransportBlocked("account_identity_invalid") from None
        options={"uid":uid,"devid":devid}
    from findmy import AsyncAppleAccount
    account=AsyncAppleAccount(provider,timeout=timeout,**options)
    try:
        return await _replace_http(account,"account",timeout)
    except BaseException:
        await account.close()
        raise

async def open_shared_client(account):
    from findmy.cloudkit.client import AsyncCloudKitClient
    from findmy.cloudkit.beacons import AsyncBeaconStore
    from findmy.cloudkit.constants import KEYCHAIN_CONTAINER,CUTTLEFISH_BUNDLE
    from findmy.keychain.items import SECURITYD_BUNDLE
    from findmy.keychain.escrow import AsyncEscrowProxy,escrow_host
    from findmy.keychain.session import AsyncKeychainSession
    from findmy.icloud import AsyncFindMyClient

    class ReadCloudKit(AsyncCloudKitClient):
        async def open_container(self):
            info=await super().open_container()
            for base,path in ((info.database_gateway_url,"/api/client/record/sync"),(info.code_gateway_url,"/api/client/code/invoke")):
                if not isinstance(base,str): raise TransportBlocked("gateway_blocked")
                validate_destination("cloudkit","POST",base.rstrip("/")+path)
            return info
        async def function_invoke(self,service,method,payload,**kwargs):
            if service!="Cuttlefish" or method not in ("fetchViableBottles","fetchChanges","fetchRecoverableTLKShares"):
                raise TransportBlocked("operation_blocked")
            return await super().function_invoke(service,method,payload,**kwargs)

    resources=[]
    async def client(**kwargs):
        value=ReadCloudKit(account,**kwargs)
        resources.append(value)
        return await _replace_http(value,"cloudkit",account.timeout)
    try:
        cloudkit=await client()
        cuttlefish=await client(container=KEYCHAIN_CONTAINER,bundle=CUTTLEFISH_BUNDLE)
        securityd=await client(container=KEYCHAIN_CONTAINER,bundle=SECURITYD_BUNDLE)
        info=await cloudkit.open_container()
        if not isinstance(info.partition,str) or not re.fullmatch(r"[1-9][0-9]{0,4}",info.partition):
            raise TransportBlocked("partition_blocked")
        pet=await account.request_pet()
        proxy=AsyncEscrowProxy(account,escrow_host(info.partition),pet)
        resources.append(proxy)
        await _replace_http(proxy,"escrow",account.timeout)
        session=AsyncKeychainSession(account,cloudkit,cuttlefish,securityd,proxy)
        store=AsyncBeaconStore(account,client=cloudkit)
        return AsyncFindMyClient(account,session,store)
    except BaseException:
        # Includes cancellation while the first network request is pending.
        await asyncio.gather(*(value.close() for value in resources),return_exceptions=True)
        raise
