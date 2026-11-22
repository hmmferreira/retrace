"""Validate restored app-owned data before root applies ownership or modes."""
import os
from pathlib import Path
import stat

def prepare_private_root(root: Path,uid=None,gid=None):
    if root.is_symlink():
        raise ValueError("Private data root cannot be a symlink")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    directories=[root]
    files=[]
    def fail(error):
        raise error
    for directory,names,filenames in os.walk(root,followlinks=False,onerror=fail):
        for name in names:
            path=Path(directory)/name
            mode=path.lstat().st_mode
            if not stat.S_ISDIR(mode):
                raise ValueError("Private data directories must be real directories")
            directories.append(path)
        for name in filenames:
            path=Path(directory)/name
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise ValueError("Private data files must be independent regular files")
            files.append(path)
    # Validate the whole tree before touching any restored object's ownership.
    for path in directories+files:
        if uid is not None:
            os.chown(path,uid,gid,follow_symlinks=False)
        path.chmod(0o700 if path in directories else 0o600)
