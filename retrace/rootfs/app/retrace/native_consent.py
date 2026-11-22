"""Local operational consent is not a grant of Apple rights or legal clearance."""
import json
from pathlib import Path
from .private_session_store import _private_bytes,_unique_pairs
from .storage import atomic_json
from .owned_session import SessionBlocked

DOCUMENT='EA1510'
DOCUMENT_SHA256='eda6a88a807d38bbfcc62befabbfef463d40ad9041285d85dec1e0d1d556be97'
NAME='native-consent.json'
RECORD={'version':1,'document':DOCUMENT,'sha256':DOCUMENT_SHA256,'acquire_locally':True}

def accepted(root):
    path=Path(root)/NAME
    if not path.exists() and not path.is_symlink():return False
    try:
        if Path(root).is_symlink():raise ValueError()
        value=json.loads(_private_bytes(path,4096),object_pairs_hook=_unique_pairs)
        if value!=RECORD or type(value.get('version')) is not int or value.get('acquire_locally') is not True:raise ValueError()
        return True
    except Exception:raise SessionBlocked('native_consent_invalid') from None

def record(root):
    if accepted(root):return
    atomic_json(Path(root)/NAME,RECORD)
