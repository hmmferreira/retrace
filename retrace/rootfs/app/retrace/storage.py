"""Private atomic state; no encryption claim when key and data share a host."""
import json
import os
import re
import secrets
import stat
from pathlib import Path


def atomic_json(path: Path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.parent / ("." + secrets.token_hex(12) + ".tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path: Path, default=None):
    if path.is_symlink():
        raise PermissionError("Private state cannot be a symlink")
    if not path.exists():
        return default
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("Private state must be owner-only")
    return json.loads(path.read_text())


def token_only(account):
    # FindMy.py's default serializer includes the password. Never persist it.
    value = account.to_json()
    value["account"]["password"] = None
    return value


class Store:
    def __init__(self, root: Path):
        if root.is_symlink():
            raise PermissionError("Private state root cannot be a symlink")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self.root = root
        self.item_health = {}
        metadata_path = Path(__file__).with_name("channel.json")
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        self.channel = metadata.get("channel") if metadata.get("channel") in ("edge","stable") else "edge"
        identity = read_json(root / "identity.json")
        if identity is None:
            if any((root/name).exists() for name in ("items.json","reports.json","account.json","owned-session.json","keys","export")):
                raise ValueError("Private state identity is missing; restore the complete app backup")
            identity = {"instance_id": secrets.token_hex(16),
                        "read_token": secrets.token_urlsafe(48),
                        "csrf_key": secrets.token_hex(32)}
            atomic_json(root / "identity.json", identity)
        if not isinstance(identity,dict) or any(
            not isinstance(identity.get(key),str) or not re.fullmatch(pattern,identity[key])
            for key,pattern in (("instance_id",r"[a-f0-9]{32}"),("csrf_key",r"[a-f0-9]{64}"),("read_token",r"[A-Za-z0-9_-]{43,256}"))):
            raise ValueError("Private state identity is invalid; restore the complete app backup")
        self.identity = identity
        self.items = read_json(root / "items.json", {})
        self.reports = read_json(root / "reports.json", {})
        # Reports survive restart, health does not: a restart is not a successful poll.
        self.health = {"status": "starting", "last_poll": None, "next_poll": None}

    def rotate_read_token(self):
        """Revoke old snapshot access without changing instance or entity IDs."""
        updated={**self.identity,"read_token":secrets.token_urlsafe(48)}
        atomic_json(self.root/"identity.json",updated)
        self.identity=updated

    def public(self):
        return {"instance_id": self.identity["instance_id"], "channel": self.channel, "health": self.health,
                "items": [{"id": key, "name": item["name"],
                           "model": item.get("model"), "model_name":item.get("model_name"),
                           "apple_name":item.get("apple_name"), "paired_at":item.get("paired_at"),
                           "enabled": item["enabled"],
                           "report": self.reports.get(key), "refresh": self.item_health.get(key,{})}
                          for key, item in self.items.items()]}

    def select(self, ids):
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            raise ValueError("Invalid item selection")
        if set(ids) - self.items.keys():
            raise ValueError("Unknown item")
        selected = set(ids)
        updated = {key:{**item,"enabled":key in selected} for key,item in self.items.items()}
        atomic_json(self.root / "items.json", updated)
        self.items = updated
