"""Mac account adapter. Account secrets stay in the owned parent transport."""
import asyncio
import base64
import uuid
from .offline_signer import provider_for
from .apple import ReportingAccount

IDENTITY={'model':'MacBookPro13,2','os_name':'Mac OS X','os_version':'13.1','os_build':'22C65','cfnetwork':'1404.0.5','darwin':'22.2.0'}

class MacReportingAccount(ReportingAccount):
    @property
    def device_uuid(self):
        # CloudKit requires a UUID; GrandSlam headers still use _devid (Mac UDID).
        return str(uuid.UUID(self._anisette._owned_signer.machine['host_uuid'])).upper()

def mac_provider(signer):
    from findmy.reports.anisette import DeviceIdentity
    provider=provider_for(signer,serial=signer.machine['serial'],identity=DeviceIdentity(**IDENTITY),_mac=True)
    return provider

async def account_for(signer,*,state=None):
    from .owned_protocol import _replace_http
    machine=signer.machine
    account=MacReportingAccount(mac_provider(signer),state_info=state,uid=machine['uid'],devid=machine['devid'])
    try:return await _replace_http(account,'account',30)
    except BaseException:
        await account.close();raise
