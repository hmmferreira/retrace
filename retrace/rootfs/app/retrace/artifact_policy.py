"""Release-owned native artifact approval; runtime state cannot approve binaries.

The bundled manifest records review decisions, not a cryptographic attestation of
third-party honesty. No download, extraction, execution or mutable override exists.
"""
import asyncio
from dataclasses import dataclass,field
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat

_MANIFEST=Path(__file__).with_name("trusted_artifacts.json")
_MAX_MANIFEST=64*1024
_MAX_ARTIFACT=64*1024*1024
_ISSUER=object()
_SOURCE="https://apps.mzstatic.com/content/android-apple-music-apk/applemusic.apk"
_WRAPPER={"name":"anisette","version":"1.2.4","wheel_sha256":"f61e620aa736f0cac0ca102dd44a02cc2caea1a072eab0f1ef7f2d8b534e03dc"}
_ARCHES={"amd64":"amd64","x86_64":"amd64","aarch64":"aarch64","arm64":"aarch64"}

class ArtifactBlocked(RuntimeError):
    def __init__(self,code):self.code=code;super().__init__(code)

def _hash(value):return isinstance(value,str) and re.fullmatch(r"[a-f0-9]{64}",value) is not None

def _text(value):
    return isinstance(value,str) and 0<len(value)<=2048 and all(c.isprintable() for c in value)

def _keys(value,expected):return isinstance(value,dict) and set(value)==set(expected)

def _pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ArtifactBlocked("artifact_policy_invalid")
        value[key]=item
    return value

def _load_manifest():
    try:
        value=_MANIFEST.read_bytes()
        if not 0<len(value)<=_MAX_MANIFEST:raise ValueError()
        return json.loads(value,object_pairs_hook=_pairs,parse_constant=lambda _:None)
    except Exception:raise ArtifactBlocked("artifact_policy_invalid") from None

@dataclass(frozen=True)
class ReviewedArtifact:
    id:str
    expected_sha256:str
    guest_architecture:str
    host_architecture:str
    source_url:str
    source_version:str
    source_sha256:str
    member_sha256:tuple[tuple[str,str],...]
    review_id:str
    redistribution:str
    _issuer:object=field(repr=False,compare=False)


def reviewed_artifact(artifact_id,*,host_architecture=None,private_evaluation=False):
    """Select only an approved source-bound entry from the fixed release manifest."""
    if not isinstance(artifact_id,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}",artifact_id):
        raise ArtifactBlocked("artifact_policy_invalid")
    if type(private_evaluation) is not bool:raise ArtifactBlocked("artifact_policy_invalid")
    manifest=_load_manifest()
    if not _keys(manifest,("schema_version","artifacts")) or type(manifest["schema_version"]) is not int or manifest["schema_version"]!=1 or not isinstance(manifest["artifacts"],list):
        raise ArtifactBlocked("artifact_policy_invalid")
    entries={}
    for entry in manifest["artifacts"]:
        if not _keys(entry,("id","review_status","host_architectures","guest_architecture","wrapper","source","bundle","review","license")) or not isinstance(entry["id"],str) or entry["id"] in entries:
            raise ArtifactBlocked("artifact_policy_invalid")
        entries[entry["id"]]=entry
    entry=entries.get(artifact_id)
    if entry is None:raise ArtifactBlocked("artifact_not_approved")
    evaluation=entry["review_status"]=="private-evaluation"
    if entry["review_status"]!="approved" and not (evaluation and private_evaluation):raise ArtifactBlocked("artifact_review_required")
    arch=_ARCHES.get(host_architecture or platform.machine())
    if arch is None or not isinstance(entry["host_architectures"],list) or not entry["host_architectures"] or any(a not in ("amd64","aarch64") for a in entry["host_architectures"]) or arch not in entry["host_architectures"]:
        raise ArtifactBlocked("artifact_architecture_unsupported")
    if entry["guest_architecture"]!="arm64-v8a" or entry["wrapper"]!=_WRAPPER:
        raise ArtifactBlocked("artifact_policy_invalid")
    source,bundle,review,license=entry["source"],entry["bundle"],entry["review"],entry["license"]
    if not _keys(source,("url","version","sha256")) or source["url"]!=_SOURCE or not _text(source["version"]) or not _hash(source["sha256"]):
        raise ArtifactBlocked("artifact_source_unverified")
    members={"lib/arm64-v8a/libCoreADI.so","lib/arm64-v8a/libstoreservicescore.so"}
    if not _keys(bundle,("format","sha256","member_sha256")) or bundle["format"]!="anisette-library-bundle" or not _hash(bundle["sha256"]) or not _keys(bundle["member_sha256"],members) or not all(_hash(v) for v in bundle["member_sha256"].values()):
        raise ArtifactBlocked("artifact_policy_invalid")
    if not _keys(review,("id","date","evidence")) or not all(_text(v) for v in review.values()):
        raise ArtifactBlocked("artifact_review_required")
    try:date.fromisoformat(review["date"])
    except (ValueError,TypeError):raise ArtifactBlocked("artifact_policy_invalid") from None
    if not _keys(license,("wrapper","native_review","redistribution")) or license["wrapper"]!="MIT":
        raise ArtifactBlocked("artifact_license_review_required")
    if evaluation:
        if license["native_review"]!="terms-reviewed-no-clearance" or license["redistribution"]!="local-use-only":raise ArtifactBlocked("artifact_license_review_required")
    elif license["native_review"]!="approved" or license["redistribution"] not in ("permitted","local-use-only"):
        raise ArtifactBlocked("artifact_license_review_required")
    return ReviewedArtifact(entry["id"],bundle["sha256"],entry["guest_architecture"],arch,source["url"],source["version"],source["sha256"],tuple(sorted(bundle["member_sha256"].items())),review["id"],license["redistribution"],_ISSUER)


def _verify(path,policy):
    if not isinstance(policy,ReviewedArtifact) or policy._issuer is not _ISSUER:
        raise ArtifactBlocked("reviewed_artifact_required")
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=_MAX_ARTIFACT:
                raise ArtifactBlocked("artifact_invalid")
            value=stream.read(_MAX_ARTIFACT+1)
    except (OSError,ValueError,TypeError):raise ArtifactBlocked("artifact_unavailable") from None
    if len(value)>_MAX_ARTIFACT or hashlib.sha256(value).hexdigest()!=policy.expected_sha256:
        raise ArtifactBlocked("artifact_digest_mismatch")
    return value

async def verify_artifact(path,policy):
    """Read/hash off-loop; return bytes only for the selected immutable release pin."""
    return await asyncio.to_thread(_verify,path,policy)
