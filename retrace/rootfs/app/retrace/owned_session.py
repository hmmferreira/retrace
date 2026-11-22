"""Encrypted password-free snapshots for the experimental owned account path.

No disk IO, login, fallback provider deserialization or network verification is
performed. Callers own private key storage and map expiry/server rejection to an
explicit main-flow reauthentication prompt. A local expiry is not proof that an
Apple service token remains valid.
"""
import asyncio
import base64
import copy
import json
import math
import os
import time
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .apple_transport import OwnedHttpSession
from .offline_signer import OfflineSigner, SignerBlocked, provider_for
from .owned_protocol import _replace_http

_MAGIC=b"RETRACESESSION\x01"
_MAX_BYTES=24*1024*1024
_MAX_LIFETIME=30*24*60*60
_TOKEN_FIELDS={"searchPartyToken","cloudKitToken","mmeAuthToken"}
_IDENTITY_FIELDS={"model","os_name","os_version","os_build","cfnetwork","darwin"}

class SessionBlocked(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)

def _key(value):
    if not isinstance(value,bytes) or len(value)!=32:
        raise SessionBlocked("session_key_required")
    return value

def _now(value):
    value=time.time() if value is None else value
    if type(value) not in (int,float) or not math.isfinite(value):
        raise SessionBlocked("session_time_invalid")
    return value

def _text(value,limit=1024):
    if not isinstance(value,str) or not value or len(value)>limit or any(not c.isprintable() for c in value):
        raise SessionBlocked("session_invalid")
    return value

def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise SessionBlocked("session_invalid")
        result[key]=value
    return result

def _json(value):
    return json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(",",":"),sort_keys=True).encode()

def _validate(state,*,saving=False):
    """Keep only fields required to resume polling; never persist PET/password."""
    if not isinstance(state,dict) or set(state)!={"type","ids","account","login","anisette"} or state["type"]!="account":
        raise SessionBlocked("session_invalid")
    ids=state["ids"]
    if not isinstance(ids,dict) or set(ids)!={"uid","devid"}:raise SessionBlocked("session_invalid")
    mac=state.get('anisette',{}).get('type')=='aniOwnedMac' if isinstance(state.get('anisette'),dict) else False
    uuid.UUID(_text(ids['uid'],64))
    if mac:
        import re
        if not re.fullmatch('00006000-[A-F0-9]{16}',_text(ids['devid'],64)):raise SessionBlocked('session_identity_invalid')
    else:uuid.UUID(_text(ids['devid'],64))
    info=state["account"]
    if not isinstance(info,dict) or not {"username","password","info"}<=set(info) or set(info)-{"username","password","info","device_name"}:
        raise SessionBlocked("session_invalid")
    _text(info["username"])
    if not saving and info["password"] is not None:raise SessionBlocked("session_password_forbidden")
    info["password"]=None
    if "device_name" in info:_text(info["device_name"],128)
    login=state["login"]
    if not isinstance(login,dict) or set(login)!={"state","data"} or type(login["state"]) is not int or login["state"]!=3:
        raise SessionBlocked("reauthentication_required")
    data=login["data"]
    if not isinstance(data,dict):raise SessionBlocked("session_invalid")
    if not saving and set(data)-{"dsid","adsid","mobileme_data"}:raise SessionBlocked("session_credentials_forbidden")
    login["data"]={key:data[key] for key in ("dsid","adsid","mobileme_data") if key in data}
    _text(login["data"].get("dsid"))
    if "adsid" in data and data["adsid"] is not None:_text(data["adsid"])
    mobile=data.get("mobileme_data")
    if not isinstance(mobile,dict) or not isinstance(mobile.get("tokens"),dict) or not mobile["tokens"]:
        raise SessionBlocked("reauthentication_required")
    tokens=mobile["tokens"]
    if not saving and (set(mobile)!={"tokens"} or set(tokens)-_TOKEN_FIELDS):
        raise SessionBlocked("session_credentials_forbidden")
    if not tokens.get("searchPartyToken"):raise SessionBlocked("reauthentication_required")
    tokens={key:_text(value,65536) for key,value in tokens.items() if key in _TOKEN_FIELDS}
    login["data"]["mobileme_data"]={"tokens":tokens}
    ani=state["anisette"]
    if not isinstance(ani,dict) or set(ani)!={"type","serial","library_sha256","prov_data","identity"} or ani["type"] not in {"aniOwnedOffline","aniOwnedMac"}:
        raise SessionBlocked("session_provider_invalid")
    _text(ani["serial"],128)
    identity=ani["identity"]
    if not isinstance(identity,dict) or set(identity)!=_IDENTITY_FIELDS:raise SessionBlocked("session_identity_invalid")
    for value in identity.values():_text(value,128)
    if not isinstance(ani["prov_data"],str) or len(ani["prov_data"])>OfflineSigner.MAX_STATE*4//3+4:
        raise SessionBlocked("session_invalid")
    provision=base64.b64decode(ani["prov_data"],validate=True)
    if not 0<len(provision)<=OfflineSigner.MAX_STATE:raise SessionBlocked("session_invalid")
    if mac:
        from .macos_identity import validate_machine
        machine=validate_machine(json.loads(provision,object_pairs_hook=_pairs))
        from .macos_provider import IDENTITY
        if ids!={'uid':machine['uid'],'devid':machine['devid']} or ani['serial']!=machine['serial'] or identity!=IDENTITY:
            raise SessionBlocked('session_identity_invalid')
    return state,provision

async def snapshot_account(account,*,encryption_key,expires_at,now=None):
    """Return encrypted private bytes. The caller must persist the key separately."""
    key=_key(encryption_key);now=_now(now);expires_at=_now(expires_at)
    if not now<expires_at<=now+_MAX_LIFETIME:raise SessionBlocked("session_expiry_invalid")
    signer=getattr(getattr(account,"_anisette",None),"_owned_signer",None)
    if not isinstance(signer,OfflineSigner) or not signer.ready or not isinstance(account._http,OwnedHttpSession) or account._http.profile!="account":
        raise SessionBlocked("owned_account_required")
    try:
        # Native provisioning serialization is blocking, and may touch the VM.
        def serialize():
            state,_=_validate(copy.deepcopy(account.to_json()),saving=True)
            plain=_json({"version":1,"issued_at":now,"expires_at":expires_at,"state":state})
            if len(plain)>_MAX_BYTES:raise SessionBlocked("session_too_large")
            nonce=os.urandom(12)
            return _MAGIC+nonce+AESGCM(key).encrypt(nonce,plain,_MAGIC)
        return await asyncio.to_thread(serialize)
    except SessionBlocked:raise
    except Exception:raise SessionBlocked("session_snapshot_failed") from None

async def restore_account(data,*,encryption_key,library,expected_sha256,now=None,timeout=30,signer_factory=None):
    """Restore locally, preserving identity, with no auth request or SDK fallback."""
    key=_key(encryption_key);now=_now(now)
    signer=None;account=None
    try:
        if not isinstance(data,bytes) or not len(_MAGIC)+28<len(data)<=_MAX_BYTES+len(_MAGIC)+28 or not data.startswith(_MAGIC):
            raise SessionBlocked("session_invalid")
        def deserialize():
            nonce=data[len(_MAGIC):len(_MAGIC)+12]
            plain=AESGCM(key).decrypt(nonce,data[len(_MAGIC)+12:],_MAGIC)
            envelope=json.loads(plain,object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(SessionBlocked("session_invalid")))
            if not isinstance(envelope,dict) or set(envelope)!={"version","issued_at","expires_at","state"} or type(envelope["version"]) is not int or envelope["version"]!=1:
                raise SessionBlocked("session_invalid")
            issued=_now(envelope["issued_at"]);expires=_now(envelope["expires_at"])
            if not issued<expires<=issued+_MAX_LIFETIME or issued>now+60:raise SessionBlocked("session_time_invalid")
            if expires<=now:raise SessionBlocked("session_expired")
            state,provision=_validate(envelope["state"])
            return state,provision
        state,provision=await asyncio.to_thread(deserialize)
        if state["anisette"]["library_sha256"]!=expected_sha256:raise SessionBlocked("session_artifact_mismatch")
        factory=OfflineSigner if signer_factory is None else signer_factory
        if not isinstance(factory,type) or not issubclass(factory,OfflineSigner):raise SessionBlocked("owned_signer_required")
        signer=factory(library,provision,expected_sha256)
        await signer.initialize()
        if state['anisette']['type']=='aniOwnedMac':
            from .macos_worker import MacSigner
            if type(signer) is not MacSigner:raise SessionBlocked('session_provider_invalid')
            from .macos_provider import account_for
            account=await account_for(signer,state=state)
            return account
        from .apple import ReportingAccount
        from findmy.reports.anisette import DeviceIdentity
        provider=provider_for(signer,serial=state["anisette"]["serial"],identity=DeviceIdentity(**state["anisette"]["identity"]))
        account=ReportingAccount(provider,state_info=state,timeout=timeout)
        return await _replace_http(account,"account",timeout)
    except BaseException as exc:
        if account is not None:await account.close()
        elif signer is not None:await signer.close()
        if isinstance(exc,(SessionBlocked,asyncio.CancelledError)):raise
        if isinstance(exc,ImportError):raise SessionBlocked("reporting_backend_unavailable") from None
        if isinstance(exc,SignerBlocked) and exc.code in {"worker_boundary_unavailable","artifact_digest_mismatch","artifact_unavailable","signer_initialization_failed","signing_failed"}:raise SessionBlocked(exc.code) from None
        raise SessionBlocked("session_restore_failed") from None
