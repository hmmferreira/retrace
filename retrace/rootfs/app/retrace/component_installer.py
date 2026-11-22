"""Explicit vendor acquisition; fixed URL/pins, no arbitrary binary installation.

The APK is public vendor material, never credentials. It is streamed to an
owner-only temporary file, hash-verified before opening the archive, and removed
on every outcome. Only two pinned ELF members enter the deterministic bundle.
"""
import asyncio
import hashlib
from io import BytesIO
import os
from pathlib import Path
import secrets
import stat
import tarfile
import zipfile
from . import artifact_policy
from .artifact_policy import ArtifactBlocked,ReviewedArtifact,verify_artifact
from .apple_transport import OwnedHttpSession,ARTIFACT_URL,TransportBlocked

MAX_APK=200*1024*1024
MAX_LIBRARY=16*1024*1024
MEMBERS={"lib/arm64-v8a/libCoreADI.so","lib/arm64-v8a/libstoreservicescore.so"}

async def _thread(operation):
    # Cancellation must not close/unlink a stream while a worker is writing it.
    task=asyncio.create_task(asyncio.to_thread(operation))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task,return_exceptions=True)
        raise

def _policy(policy):
    if not isinstance(policy,ReviewedArtifact) or policy._issuer is not artifact_policy._ISSUER:
        raise ArtifactBlocked("reviewed_artifact_required")
    if policy.source_url!=ARTIFACT_URL or set(dict(policy.member_sha256))!=MEMBERS:
        raise ArtifactBlocked("artifact_policy_invalid")

def _bundle(stream,policy):
    stream.flush();stream.seek(0)
    digest=hashlib.sha256();received=0
    while True:
        chunk=stream.read(1024*1024)
        if not chunk:break
        received+=len(chunk)
        if received>MAX_APK:raise ArtifactBlocked("artifact_source_too_large")
        digest.update(chunk)
    if digest.hexdigest()!=policy.source_sha256:raise ArtifactBlocked("artifact_source_digest_mismatch")
    stream.seek(0);output=BytesIO()
    try:
        with zipfile.ZipFile(stream) as archive,tarfile.open(fileobj=output,mode="w",format=tarfile.USTAR_FORMAT) as tar:
            names=archive.namelist()
            for name,digest in sorted(policy.member_sha256):
                if name not in MEMBERS or names.count(name)!=1:raise ArtifactBlocked("artifact_source_member_invalid")
                info=archive.getinfo(name)
                if not 0<info.file_size<=MAX_LIBRARY or not 0<info.compress_size<=MAX_LIBRARY:
                    raise ArtifactBlocked("artifact_source_member_invalid")
                with archive.open(name) as source:value=source.read(MAX_LIBRARY+1)
                if len(value)>MAX_LIBRARY or hashlib.sha256(value).hexdigest()!=digest:
                    raise ArtifactBlocked("artifact_source_member_digest_mismatch")
                if value[:6]!=b"\x7fELF\x02\x01" or value[18:20]!=b"\xb7\x00":
                    raise ArtifactBlocked("artifact_source_architecture_invalid")
                member=tarfile.TarInfo("./libs/"+Path(name).name)
                member.size=len(value);member.mode=0o644;member.mtime=0
                tar.addfile(member,BytesIO(value))
            index=b'{"libs":"./libs"}'
            member=tarfile.TarInfo("fs.json");member.size=len(index);member.mode=0o644;member.mtime=0
            tar.addfile(member,BytesIO(index))
    except ArtifactBlocked:raise
    except Exception:raise ArtifactBlocked("artifact_source_invalid") from None
    bundle=output.getvalue()
    if hashlib.sha256(bundle).hexdigest()!=policy.expected_sha256:raise ArtifactBlocked("artifact_digest_mismatch")
    return bundle

def _publish(root,destination,bundle):
    temporary=root/(".component-"+secrets.token_hex(16)+".tmp")
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(bundle);stream.flush();os.fsync(stream.fileno())
        # Publish without overwriting a file or symlink created since admission.
        try:os.link(temporary,destination,follow_symlinks=False)
        except FileExistsError:raise ArtifactBlocked("artifact_destination_changed") from None
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:temporary.unlink(missing_ok=True)

async def ensure_component(root,policy,*,install=False,transport=None):
    """Install only when explicitly requested and absent; never replace bad state."""
    _policy(policy)
    if type(install) is not bool:raise ArtifactBlocked("artifact_install_consent_required")
    root=Path(root);destination=root/"owned-libs.bin"
    if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode)&0o077:
        raise ArtifactBlocked("artifact_storage_invalid")
    if destination.exists() or destination.is_symlink():
        await verify_artifact(destination,policy)
        return {"installed":False}
    if not install:raise ArtifactBlocked("artifact_install_consent_required")
    if transport is not None and (not isinstance(transport,OwnedHttpSession) or transport.profile!="artifact"):
        raise ArtifactBlocked("owned_transport_required")
    http=transport or OwnedHttpSession(profile="artifact",timeout=90)
    temporary=root/(".component-"+secrets.token_hex(16)+".apk")
    stream=None
    try:
        fd=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        stream=os.fdopen(fd,"w+b")
        received=0;digest=hashlib.sha256()
        async for chunk in http.artifact_chunks(policy.source_url,max_bytes=MAX_APK):
            if not isinstance(chunk,bytes):raise ArtifactBlocked("artifact_download_failed")
            received+=len(chunk)
            if received>MAX_APK:raise ArtifactBlocked("artifact_source_too_large")
            digest.update(chunk)
            await _thread(lambda:stream.write(chunk))
        if digest.hexdigest()!=policy.source_sha256:raise ArtifactBlocked("artifact_source_digest_mismatch")
        bundle=await _thread(lambda:_bundle(stream,policy))
        await _thread(lambda:_publish(root,destination,bundle))
        return {"installed":True}
    except asyncio.CancelledError:raise
    except ArtifactBlocked:raise
    except TransportBlocked as error:raise ArtifactBlocked(error.code) from None
    except Exception:raise ArtifactBlocked("artifact_install_failed") from None
    finally:
        if stream is not None:stream.close()
        temporary.unlink(missing_ok=True)
        await http.close()
