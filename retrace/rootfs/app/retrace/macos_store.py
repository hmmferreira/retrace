"""Independent encrypted Mac machine generations with locked bounded retention."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .private_session_store import _private_bytes,_write_new,_unique_pairs
from .storage import atomic_json
from .macos_identity import validate_machine
from .owned_session import SessionBlocked

AAD=b'retrace-macos-machine-v1'
KEEP_GENERATIONS=3

class MachineStore:
    def __init__(self,root):self.root=Path(root)
    def exists(self):return (self.root/'machine.json').exists() or (self.root/'machine.json').is_symlink()

    @contextmanager
    def _locked(self,exclusive):
        if self.root.is_symlink():raise SessionBlocked('session_storage_invalid')
        fd=os.open(self.root/'store.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or
                    stat.S_IMODE(info.st_mode)&0o077):raise SessionBlocked('session_storage_invalid')
            fcntl.flock(fd,fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:os.close(fd)

    def load(self):
        try:
            with self._locked(False):
                manifest=json.loads(_private_bytes(self.root/'machine.json',4096),object_pairs_hook=_unique_pairs)
                if set(manifest)!={'version','generation'} or type(manifest['version']) is not int or manifest['version']!=1:raise ValueError()
                generation=manifest['generation']
                if not isinstance(generation,str) or not re.fullmatch('[a-f0-9]{32}',generation):raise ValueError()
                key=_private_bytes(self.root/('machine-'+generation+'.key'),32)
                cipher=_private_bytes(self.root/('machine-'+generation+'.enc'),8*1024*1024)
                raw=AESGCM(key).decrypt(cipher[:12],cipher[12:],AAD)
                return validate_machine(json.loads(raw,object_pairs_hook=_unique_pairs))
        except Exception:raise SessionBlocked('signing_identity_invalid') from None

    def _prune(self,current):
        # Only exact machine-generation filenames in this provider namespace.
        # Readers hold store.lock until they finish consuming both files.
        groups={}
        for path in self.root.iterdir():
            match=re.fullmatch(r'machine-([a-f0-9]{32})\.(key|enc)',path.name)
            if match is not None:
                groups.setdefault(match[1],[]).append(path)
        older=sorted((gen for gen in groups if gen!=current),
                     key=lambda gen:max(p.lstat().st_mtime_ns for p in groups[gen]),reverse=True)
        keep={current,*older[:KEEP_GENERATIONS-1]}
        for generation,paths in groups.items():
            if generation not in keep:
                for path in paths:path.unlink(missing_ok=True)

    def save(self,machine):
        validate_machine(machine)
        if self.root.is_symlink():raise SessionBlocked('session_storage_invalid')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True);self.root.chmod(0o700)
        with self._locked(True):
            generation=secrets.token_hex(16);key=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
            payload=nonce+AESGCM(key).encrypt(nonce,json.dumps(machine,separators=(',',':')).encode(),AAD)
            keyfile=self.root/('machine-'+generation+'.key');datafile=self.root/('machine-'+generation+'.enc')
            try:
                _write_new(keyfile,key);_write_new(datafile,payload)
                atomic_json(self.root/'machine.json',{'version':1,'generation':generation})
            except BaseException:
                # Directory fsync can fail after the manifest was published.
                try:published=json.loads(_private_bytes(self.root/'machine.json',4096)).get('generation')==generation
                except Exception:published=True
                if not published:keyfile.unlink(missing_ok=True);datafile.unlink(missing_ok=True)
                raise
            self._prune(generation)
