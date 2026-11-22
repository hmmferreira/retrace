"""Explicit Mac provider lifecycle; private independent machine/session namespace."""
import asyncio
import base64
from datetime import datetime,timezone
import json
import plistlib
from .apple_transport import OwnedHttpSession
from .controlled_provisioning import LOOKUP,START,FINISH,_binary,ProvisioningBlocked
from .native_worker import _NativeChannel,_encode,_decode
from .macos_artifact import ensure,LIBRARY_SHA
from .macos_identity import new_machine,validate_machine
from .macos_store import MachineStore
from .macos_worker import MacSigner
from .macos_provider import IDENTITY,account_for,MacReportingAccount
from .private_session_store import PrivateSessionStore,_private_bytes,MANIFEST
from .storage import atomic_json,read_json

async def provision(library):
    machine=new_machine();channel=_NativeChannel();http=OwnedHttpSession(profile='provisioning',timeout=30)
    try:
        async with asyncio.timeout(90):
            artifact=await asyncio.to_thread(_private_bytes,library,16*1024*1024)
            import hashlib
            if hashlib.sha256(artifact).hexdigest()!=LIBRARY_SHA:raise ProvisioningBlocked('artifact_digest_mismatch')
            reply=await channel.exchange('mac_prepare',artifact=_encode(artifact,16*1024*1024),host_uuid=machine['host_uuid'])
            if reply.get('phase')!='new':raise ProvisioningBlocked('worker_state_invalid')
            from findmy.reports.anisette import DeviceIdentity
            identity=DeviceIdentity(**IDENTITY)
            headers={'X-Mme-Device-Id':machine['devid'],
                     'X-MMe-Client-Info':identity.client_info('com.apple.AuthKit/1 (com.apple.akd/1.0)'),
                     'X-Apple-I-MD-LU':machine['uid'],
                     'X-Apple-I-SRL-NO':machine['serial'],'User-Agent':identity.user_agent('akd/1.0'),
                     'Content-Type':'application/x-www-form-urlencoded','X-Apple-Client-App-Name':'Setup'}
            async def request(method,url,payload=None):
                options={'headers':{**headers,'X-Apple-I-Client-Time':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}}
                if payload is not None:options['data']=plistlib.dumps({'Header':{},'Request':payload})
                response=await http.request(method,url,**options)
                if not response.ok:raise ProvisioningBlocked('provisioning_request_failed')
                return response.plist()
            urls=(await request('GET',LOOKUP)).get('urls')
            if not isinstance(urls,dict) or urls.get('midStartProvisioning')!=START or urls.get('midFinishProvisioning')!=FINISH:
                raise ProvisioningBlocked('provisioning_endpoints_changed')
            spim=_binary((await request('POST',START,{})).get('Response',{}).get('spim'))
            cpim=(await channel.exchange('mac_begin',spim=_encode(spim,1024*1024),consent=True)).get('cpim')
            _binary(cpim)
            finish=(await request('POST',FINISH,{'cpim':cpim})).get('Response',{})
            ptm=_binary(finish.get('ptm'));tk=_binary(finish.get('tk'))
            routing=finish.get('X-Apple-I-MD-RINFO')
            if isinstance(routing,str) and routing.isdecimal() and len(routing)<=20:routing=int(routing)
            if type(routing) is not int or not 0<=routing<2**64:raise ProvisioningBlocked('provisioning_failed')
            reply=await channel.exchange('mac_finish',ptm=_encode(ptm,1024*1024),tk=_encode(tk,1024*1024),routing=routing)
            machine['routing']=routing;machine['saved']=reply.get('saved')
            return validate_machine(machine)
    finally:
        await channel.close();await http.close()

class MacRuntime:
    def __init__(self,root,options):
        self.parent=root;self.root=root/'providers'/'macos';self.library=self.root/'coreadi.bin'
        self.options=options;self.machine_store=MachineStore(self.root);self.lock=asyncio.Lock()
        self.sessions=PrivateSessionStore(self.root,library=self.library,expected_sha256=LIBRARY_SHA)
    def consent_required(self):
        from .native_consent import accepted
        return not self.options.get('private_evaluation',False) and not accepted(self.root)
    async def prepare(self,*,native_consent=False):
        # The operator flag permits only artifact acquisition. Account UI consent
        # remains required before the lazy first provisioning exchange.
        for root in (self.parent/'providers',self.root):
            if root.is_symlink():raise ProvisioningBlocked('session_storage_invalid')
            root.mkdir(mode=0o700,exist_ok=True);root.chmod(0o700)
        from .native_consent import accepted,record
        if native_consent is True:
            from .shared_runtime import _persist
            await _persist(lambda:record(self.root))
        consent=await asyncio.to_thread(accepted,self.root)
        evaluation=self.options.get('private_evaluation',False)
        if evaluation or consent:
            await ensure(self.library,private_evaluation=evaluation,local_consent=consent)
    async def account(self,*,native_consent=False):
        async with self.lock:
            await self.prepare(native_consent=native_consent)
            if self.consent_required():raise ProvisioningBlocked('native_consent_required')
            if self.machine_store.exists():machine=await asyncio.to_thread(self.machine_store.load)
            else:
                if (self.root/MANIFEST).exists() or (self.root/MANIFEST).is_symlink():raise ProvisioningBlocked('signing_identity_missing')
                if not self.options.get('create_new_identity',False):raise ProvisioningBlocked('explicit_new_identity_required')
                machine=await provision(self.library)
                from .shared_runtime import _persist
                await _persist(lambda:self.machine_store.save(machine))
            signer=MacSigner(self.library,json.dumps(machine,separators=(',',':')).encode(),LIBRARY_SHA)
            try:
                await signer.initialize()
                return await account_for(signer)
            except BaseException:
                await signer.close();raise
    async def save(self,account):
        from .shared_runtime import _persist
        await self.sessions.save(account)
        # Publish selection only after the new account session is durable. The
        # Android manifest and keys stay untouched and may be selected again.
        await _persist(lambda:atomic_json(self.parent/'active-provider.json',{'version':1,'provider':'macos'}))
