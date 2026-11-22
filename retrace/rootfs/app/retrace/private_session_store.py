"""Private generation-based session storage and explicit reporting restore.

An owned manifest is authoritative: corruption never falls back to legacy state.
The separate key protects accidental ciphertext disclosure, not host compromise.
"""
import asyncio
import os
import json
from pathlib import Path
import re
import secrets
import stat
import time
from .owned_session import SessionBlocked, snapshot_account, restore_account
from .storage import atomic_json, read_json

MANIFEST="owned-session.json"

def _unique_pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise SessionBlocked("session_storage_invalid")
        value[key]=item
    return value

def session_available(root):
    root=Path(root)
    # Include broken symlinks: they must select owned validation, never fallback.
    marker=root/MANIFEST
    if marker.exists() or marker.is_symlink():return True
    return (root/"account.json").exists()

def _private_bytes(path,limit):
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)&0o077 or not 0<info.st_size<=limit:
                raise SessionBlocked("session_storage_invalid")
            value=stream.read(limit+1)
            if len(value)>limit:raise SessionBlocked("session_storage_invalid")
            return value
    except OSError:raise SessionBlocked("session_storage_unavailable") from None

def _write_new(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(value);stream.flush();os.fsync(stream.fileno())

class PrivateSessionStore:
    def __init__(self,root,*,library,expected_sha256):
        self.root=Path(root)
        library=Path(library)
        if library.parent!=self.root or library.name in ("",MANIFEST) or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]+",library.name):
            raise SessionBlocked("artifact_path_invalid")
        if not isinstance(expected_sha256,str) or not re.fullmatch(r"[a-f0-9]{64}",expected_sha256):
            raise SessionBlocked("artifact_digest_required")
        self.library=library.name;self.digest=expected_sha256
        self.lock=asyncio.Lock()

    async def save(self,account):
        async with self.lock:
            key=secrets.token_bytes(32)
            envelope=await snapshot_account(account,encryption_key=key,expires_at=time.time()+30*86400)
            generation=secrets.token_hex(16)
            def persist():
                if self.root.is_symlink():raise SessionBlocked("session_storage_invalid")
                self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
                self.root.chmod(0o700)
                keyfile=self.root/("session-"+generation+".key")
                datafile=self.root/("session-"+generation+".enc")
                try:
                    _write_new(keyfile,key);_write_new(datafile,envelope)
                    # A single atomic switch publishes a matching key/ciphertext pair.
                    atomic_json(self.root/MANIFEST,{"version":1,"generation":generation,
                        "library":self.library,"sha256":self.digest})
                except BaseException:
                    # Atomic replace can succeed before directory fsync fails. Keep
                    # files if the new manifest became visible, even on that error.
                    try:published=read_json(self.root/MANIFEST,{}).get("generation")==generation
                    except Exception:published=True
                    if not published:
                        keyfile.unlink(missing_ok=True);datafile.unlink(missing_ok=True)
                    raise
            await asyncio.to_thread(persist)

def active_provider(root):
    path=Path(root)/'active-provider.json'
    if not path.exists() and not path.is_symlink():return 'apple_music'
    try:
        value=json.loads(_private_bytes(path,4096),object_pairs_hook=_unique_pairs)
        if (not isinstance(value,dict) or set(value)!={'version','provider'} or
                type(value['version']) is not int or value['version']!=1 or
                value['provider'] not in ('apple_music','macos')):raise ValueError()
        return value['provider']
    except Exception:raise SessionBlocked('session_storage_invalid') from None

async def restore_reporting_account(root,*,_mac=False):
    root=Path(root)
    if root.is_symlink():raise SessionBlocked("session_storage_invalid")
    if not _mac and await asyncio.to_thread(active_provider,root)=='macos':
        if (root/'providers').is_symlink():raise SessionBlocked('session_storage_invalid')
        return await restore_reporting_account(root/'providers'/'macos',_mac=True)
    marker=root/MANIFEST
    if not marker.exists() and not marker.is_symlink():
        if os.environ.get("RETRACE_RUNTIME_MODE")=="shared":raise SessionBlocked("reauthentication_required")
        from .apple import ReportingAccount
        session=await asyncio.to_thread(read_json,root/"account.json")
        return ReportingAccount.from_json(session,anisette_libs_path=str(root/"ani_libs.bin"))
    def load():
        try:
            manifest=json.loads(_private_bytes(marker,4096),object_pairs_hook=_unique_pairs)
            if not isinstance(manifest,dict) or set(manifest)!={"version","generation","library","sha256"} or type(manifest["version"]) is not int or manifest["version"]!=1:
                raise SessionBlocked("session_storage_invalid")
            generation=manifest["generation"]
            if not isinstance(generation,str) or not re.fullmatch(r"[a-f0-9]{32}",generation):raise SessionBlocked("session_storage_invalid")
            policy=PrivateSessionStore(root,library=root/manifest["library"],expected_sha256=manifest["sha256"])
            key=_private_bytes(root/("session-"+generation+".key"),32)
            if len(key)!=32:raise SessionBlocked("session_storage_invalid")
            data=_private_bytes(root/("session-"+generation+".enc"),24*1024*1024+128)
            return data,key,policy
        except SessionBlocked:raise
        except Exception:raise SessionBlocked("session_storage_invalid") from None
    data,key,policy=await asyncio.to_thread(load)
    options={}
    if _mac:
        from .macos_artifact import LIBRARY_SHA
        from .macos_worker import MacSigner
        from .native_consent import accepted
        if (os.environ.get('RETRACE_PRIVATE_EVALUATION')!='1' and not await asyncio.to_thread(accepted,root)) or policy.library!='coreadi.bin' or policy.digest!=LIBRARY_SHA:
            raise SessionBlocked('session_artifact_mismatch')
        options['signer_factory']=MacSigner
    elif os.environ.get("RETRACE_RUNTIME_MODE")=="shared":
        from .native_worker import ProcessOfflineSigner
        from .artifact_policy import ArtifactBlocked,reviewed_artifact,verify_artifact
        try:
            approved=reviewed_artifact("applemusic-arm64-v8a",private_evaluation=os.environ.get("RETRACE_PRIVATE_EVALUATION")=="1")
            if approved.expected_sha256!=policy.digest:raise SessionBlocked("session_artifact_mismatch")
            await verify_artifact(root/policy.library,approved)
        except ArtifactBlocked as exc:raise SessionBlocked(exc.code) from None
        options["signer_factory"]=ProcessOfflineSigner
    return await restore_account(data,encryption_key=key,library=root/policy.library,expected_sha256=policy.digest,**options)
