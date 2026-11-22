"""Explicit shared-image startup; no SDK/downloader/provisioning fallback."""
import asyncio
import base64
import json
import os
from pathlib import Path
import re
import secrets
import time
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .owned_session import SessionBlocked
from .private_session_store import _private_bytes,_write_new,PrivateSessionStore,MANIFEST
from .storage import atomic_json

BACKEND_REVISION="8ecfae6cb34b29caf0bd8176ee73155ca81415a8"
BACKEND_ARCHIVE_SHA256="676e871098ec60a9c5e6718ea8cc18215631b036b99117a814ac1eb87d4e99e7"
SIGNING_MANIFEST="owned-signing.json"
AAD=b"retrace-owned-signing-v1"

class RuntimeBlocked(RuntimeError):
    def __init__(self,code):self.code=code;super().__init__(code)

def read_options(path=Path('/data/options.json')):
    path=Path(path)
    try:
        if not path.exists():return {"runtime_mode":"legacy","shared_artifact_id":"applemusic-arm64-v8a","create_new_identity":False,"install_reviewed_component":False,"private_evaluation":False,"experimental_macos_signer":False,"apple_music_provider":True,"macos_provider":False}
        if path.is_symlink() or path.stat().st_size>4096:raise ValueError()
        value=json.loads(path.read_text(),object_pairs_hook=_pairs)
        if not isinstance(value,dict) or set(value)-{"runtime_mode","shared_artifact_id","create_new_identity","install_reviewed_component","private_evaluation","experimental_macos_signer","apple_music_provider","macos_provider"}:raise ValueError()
        apple=value.get('apple_music_provider',True)
        mac=value.get('macos_provider',False)
        if type(apple) is not bool or type(mac) is not bool:raise ValueError()
        macos=value.get("experimental_macos_signer",False)
        if type(macos) is not bool:raise ValueError()
        mode=value.get("runtime_mode","legacy")
        artifact=value.get("shared_artifact_id","applemusic-arm64-v8a")
        create=value.get("create_new_identity",False)
        install=value.get("install_reviewed_component",False)
        private_evaluation=value.get("private_evaluation",False)
        if mode not in ("legacy","shared") or type(create) is not bool or type(install) is not bool or type(private_evaluation) is not bool:raise ValueError()
        if not isinstance(artifact,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}",artifact):raise ValueError()
        return {"runtime_mode":mode,"shared_artifact_id":artifact,"create_new_identity":create,"install_reviewed_component":install,"private_evaluation":private_evaluation,"experimental_macos_signer":macos,"apple_music_provider":apple,"macos_provider":mac}
    except Exception:raise RuntimeBlocked("runtime_options_invalid") from None

def publish_runtime_options(root,options,*,uid=None,gid=None):
    """Hand off validated non-secret options before the launcher drops root."""
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise RuntimeBlocked("runtime_options_invalid")
    path=root/'runtime-options.json'
    atomic_json(path,options)
    if uid is not None:os.chown(path,uid,gid,follow_symlinks=False)
    return path

def require_shared_backend():
    try:
        marker=json.loads(Path(__file__).with_name('shared_backend.json').read_text())
        if marker!={"revision":BACKEND_REVISION,"archive_sha256":BACKEND_ARCHIVE_SHA256}:raise ValueError()
        import findmy
        from findmy.icloud import AsyncFindMyClient
        from findmy.reports.anisette import DeviceIdentity
        if Path(findmy.__file__).resolve().parent!=Path('/opt/retrace-protocol/findmy'):raise ValueError()
    except Exception:raise RuntimeBlocked("shared_image_required") from None

def configure_runtime(options):
    mode=options['runtime_mode']
    if mode=='shared':require_shared_backend()
    elif Path(__file__).with_name('shared_backend.json').exists():raise RuntimeBlocked('legacy_image_required')
    os.environ['RETRACE_RUNTIME_MODE']=mode
    os.environ['RETRACE_PRIVATE_EVALUATION']='1' if mode=='shared' and options.get('private_evaluation',False) is True else '0'
    return mode

def owned_session_available(root):
    marker=Path(root)/MANIFEST
    return marker.exists() or marker.is_symlink()

def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise SessionBlocked('signing_identity_invalid')
        result[key]=value
    return result

class SigningIdentityStore:
    """Machine state survives account-token expiry, encrypted and never regenerated.

    Key/ciphertext share the host's trust boundary. Encryption does not protect a
    compromised HA host or complete backup containing both files.
    """
    def __init__(self,root,expected_sha256):self.root,self.digest=Path(root),expected_sha256
    def exists(self):
        path=self.root/SIGNING_MANIFEST
        return path.exists() or path.is_symlink()
    def load(self):
        try:
            marker=json.loads(_private_bytes(self.root/SIGNING_MANIFEST,4096),object_pairs_hook=_pairs)
            if set(marker)!={'version','generation','sha256'} or type(marker['version']) is not int or marker['version']!=2 or marker['sha256']!=self.digest:raise ValueError()
            generation=marker['generation']
            if not isinstance(generation,str) or not re.fullmatch(r'[a-f0-9]{32}',generation):raise ValueError()
            key=_private_bytes(self.root/('signing-'+generation+'.key'),32)
            payload=_private_bytes(self.root/('signing-'+generation+'.enc'),24*1024*1024)
            plain=AESGCM(key).decrypt(payload[:12],payload[12:],AAD+self.digest.encode())
            data=json.loads(plain,object_pairs_hook=_pairs)
            if not isinstance(data,dict) or set(data)!={'serial','identity','state','ids'}:raise ValueError()
            if not isinstance(data['serial'],str) or not re.fullmatch('[a-f0-9]{32}',data['serial']):raise ValueError()
            identity=data['identity']
            fields={'model','os_name','os_version','os_build','cfnetwork','darwin'}
            if not isinstance(identity,dict) or set(identity)!=fields or any(not isinstance(v,str) or not 0<len(v)<=128 or not v.isprintable() for v in identity.values()):raise ValueError()
            if not isinstance(data['state'],str) or len(data['state'])>23*1024*1024:raise ValueError()
            ids=data['ids']
            if not isinstance(ids,dict) or set(ids)!={'uid','devid'}:raise ValueError()
            for value in ids.values():
                if not isinstance(value,str) or str(uuid.UUID(value))!=value:raise ValueError()
            state=base64.b64decode(data['state'],validate=True)
            if not 0<len(state)<=16*1024*1024:raise ValueError()
            return state,data['serial'],identity,ids
        except Exception:raise SessionBlocked('signing_identity_invalid') from None
    def save(self,state,serial,identity,ids):
        if not isinstance(state,bytes) or not 0<len(state)<=16*1024*1024:raise SessionBlocked('signing_identity_invalid')
        value={'serial':serial,'identity':identity,'ids':ids,'state':base64.b64encode(state).decode('ascii')}
        raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
        key=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
        payload=nonce+AESGCM(key).encrypt(nonce,raw,AAD+self.digest.encode())
        generation=secrets.token_hex(16)
        keyfile=self.root/('signing-'+generation+'.key');datafile=self.root/('signing-'+generation+'.enc')
        try:
            _write_new(keyfile,key);_write_new(datafile,payload)
            atomic_json(self.root/SIGNING_MANIFEST,{'version':2,'generation':generation,'sha256':self.digest})
        except BaseException:
            # Keep possibly published generations if fsync failed after replace.
            try:published=json.loads(_private_bytes(self.root/SIGNING_MANIFEST,4096)).get('generation')==generation
            except Exception:published=True
            if not published:keyfile.unlink(missing_ok=True);datafile.unlink(missing_ok=True)
            raise

async def _persist(operation):
    task=asyncio.create_task(asyncio.to_thread(operation))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task,return_exceptions=True)
        raise

async def check_saved_identity(signing,library,digest):
    """Offline comparison only: no provisioning, account login, or disk writes."""
    from .native_worker import ProcessOfflineSigner
    signer=None
    try:
        if not signing.exists():return {"status":"not_saved"}
        async with asyncio.timeout(50):
            state,serial,identity,ids=await asyncio.to_thread(signing.load)
            from findmy.reports.anisette import DeviceIdentity
            client=DeviceIdentity(**identity).client_info("com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)")
            signer=ProcessOfflineSigner(library,state,digest)
            await signer.initialize()
            checks=await signer.identity_checks({"uid":ids["uid"],"devid":ids["devid"],"client_info":client})
            return {"status":"consistent" if all(checks.values()) else "mismatch",**checks}
    except asyncio.CancelledError:raise
    except Exception as error:
        code=getattr(error,"code",None)
        allowed={"signing_identity_invalid","worker_boundary_unavailable","artifact_unavailable","artifact_digest_mismatch",
                 "native_worker_failed","signer_initialization_failed","identity_check_failed"}
        return {"status":"unavailable","error":code if isinstance(code,str) and code in allowed else "check_failed"}
    finally:
        if signer is not None:await signer.close()


async def compose_runtime(store,options):
    """Used by server.main only in the explicitly selected shared runtime image."""
    require_shared_backend()
    from .artifact_policy import reviewed_artifact,verify_artifact
    from .native_worker import IsolatedNativeWorker,ProcessOfflineSigner,verify_native_boundary
    from .controlled_provisioning import provision_new_identity
    from .offline_signer import provider_for
    from .owned_protocol import create_account
    from .shared_ui import compose_shared_ui
    await verify_native_boundary()
    apple_enabled=options.get('apple_music_provider',True)
    policy=signing=sessions=None
    library=store.root/'owned-libs.bin'
    if apple_enabled:
        policy=reviewed_artifact(options['shared_artifact_id'],private_evaluation=options.get('private_evaluation',False))
        # Validate the actual target's native boundary before vendor download,
        # entering credentials, or opening UI/integration listeners.
        library=store.root/'owned-libs.bin'
        if options.get('install_reviewed_component',False):
            from .component_installer import ensure_component
            await ensure_component(store.root,policy,install=True)
        await verify_artifact(library,policy)
        signing=SigningIdentityStore(store.root,policy.expected_sha256)
        check=await check_saved_identity(signing,library,policy.expected_sha256)
        print("Retrace identity check: "+json.dumps(check,separators=(",",":")),flush=True)
        sessions=PrivateSessionStore(store.root,library=library,expected_sha256=policy.expected_sha256)
    mac=None
    if options.get('experimental_macos_signer',False) or options.get('macos_provider',False):
        from .macos_runtime import MacRuntime
        mac=MacRuntime(store.root,options)
        await mac.prepare()
    lifecycle=asyncio.Lock()
    async def account_factory(provider=None,*,native_consent=False):
        provider=provider or ('apple_music' if apple_enabled else 'macos')
        if provider=='macos':
            if mac is None:raise RuntimeBlocked('macos_signer_not_available')
            return await mac.account(native_consent=native_consent)
        if provider!='apple_music' or not apple_enabled:raise RuntimeBlocked('provider_unavailable')
        async with lifecycle:
            if signing.exists():state,serial,identity,ids=await asyncio.to_thread(signing.load)
            else:
                # Existing/corrupt identity or owned account manifests cannot be
                # overwritten by keeping create_new_identity enabled in options.
                if owned_session_available(store.root):raise SessionBlocked('signing_identity_missing')
                if not options['create_new_identity']:raise RuntimeBlocked('explicit_new_identity_required')
                from findmy.reports.anisette import CLIENT_IDENTITY
                ids={"uid":str(uuid.uuid4()),"devid":str(uuid.uuid4())}
                client_info=CLIENT_IDENTITY.client_info("com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)")
                state=await provision_new_identity(library,policy.expected_sha256,
                    worker=IsolatedNativeWorker(uid=ids["uid"],devid=ids["devid"],client_info=client_info),
                    create_new_identity=True,user_agent=CLIENT_IDENTITY.user_agent("akd/1.0"))
                serial=secrets.token_hex(16);identity=CLIENT_IDENTITY.to_json()
                await _persist(lambda:signing.save(state,serial,identity,ids))
            from findmy.reports.anisette import DeviceIdentity
            signer=ProcessOfflineSigner(library,state,policy.expected_sha256)
            try:
                await signer.initialize()
                return await create_account(provider_for(signer,serial=serial,identity=DeviceIdentity(**identity)),uid=ids["uid"],devid=ids["devid"])
            except BaseException:
                await signer.close();raise
    async def save_account(account):
        from .macos_provider import MacReportingAccount
        if isinstance(account,MacReportingAccount):
            if mac is None:raise RuntimeBlocked('macos_signer_not_available')
            return await mac.save(account)
        await sessions.save(account)
        # Refresh private machine state without retaining any account password,
        # PET, location tokens or broader recovered Keychain material here.
        provider=getattr(account,'_anisette',None)
        if provider is None:raise SessionBlocked('owned_account_required')
        value=provider.to_json()
        state=base64.b64decode(value['prov_data'],validate=True)
        ids={'uid':account.local_user_uuid,'devid':account.device_uuid}
        await _persist(lambda:signing.save(state,value['serial'],value['identity'],ids))
        await _persist(lambda:atomic_json(store.root/'active-provider.json',{'version':1,'provider':'apple_music'}))
    def available():
        from .private_session_store import active_provider
        root=store.root/'providers'/'macos' if active_provider(store.root)=='macos' else store.root
        return owned_session_available(root)
    result=compose_shared_ui(store,account_factory=account_factory,session_writer=save_account,
                             session_available=available)
    result[1].macos_available=mac is not None
    result[1].apple_music_available=apple_enabled
    result[1].default_provider='apple_music' if apple_enabled else 'macos'
    result[1].native_consent_required=mac.consent_required if mac is not None else lambda:False
    print("Retrace providers: "+json.dumps({"apple_music":apple_enabled,"macos":mac is not None},separators=(",",":")),flush=True)
    return result
