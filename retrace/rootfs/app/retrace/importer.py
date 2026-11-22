"""Normalize the pinned Rust export without changing its source files."""
from datetime import datetime, timezone
import hashlib
import plistlib
from pathlib import Path
import xml.etree.ElementTree as ET
from .storage import atomic_json
from .descriptions import metadata


def normalized_plist(raw: bytes):
    if len(raw) > 2_000_000 or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsupported export")
    if raw.startswith(b"bplist"):
        data = plistlib.loads(raw)
    else:
        tree = ET.fromstring(raw)
        for node in tree.iter("date"):
            date = datetime.fromisoformat(node.text.replace("Z", "+00:00"))
            node.text = date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = plistlib.loads(ET.tostring(tree))
    for field in ("privateKey", "sharedSecret", "secondarySharedSecret", "secureLocationsSharedSecret"):
        if isinstance(data.get(field), bytes):
            data[field] = {"key": {"data": data[field]}}
    return data


def import_exports(store, directory: Path):
    from findmy import FindMyAccessory
    # Validate every item before writing the inventory. Existing selection survives rediscovery.
    pending = {}
    for source in sorted(directory.glob("*.plist"),key=lambda p:(p.stat().st_mtime_ns,p.name)):
        data = normalized_plist(source.read_bytes())
        stable = str(data["identifier"])
        item_id = hashlib.sha256(stable.encode()).hexdigest()[:32]
        accessory = FindMyAccessory.from_plist(data, name=source.stem.replace("_", " "))
        old = store.items.get(item_id, {})
        pending[item_id] = {"name": old.get("name", source.stem.replace("_", " ")),
                            "model": str(data.get("model", "")),
                            "enabled": old.get("enabled", False),
                            "key_file": item_id + ".json", **metadata(data)}
        atomic_json(store.root / "keys" / (item_id + ".json"), accessory.to_json())
    updated = {**store.items, **pending}
    atomic_json(store.root / "items.json", updated)
    store.items = updated
    return len(pending)
