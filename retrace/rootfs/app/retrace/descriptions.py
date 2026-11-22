"""Allowlisted item descriptions: never publish serials, keys or account data."""
from datetime import datetime, timezone
from xml.etree.ElementTree import ParseError
from plistlib import InvalidFileException
from .storage import atomic_json, read_json

# Hardware identifier facts checked against DeviceKit's generated catalog
# (https://github.com/devicekit/DeviceKit) and Apple Support 108052.
MODEL_NAMES = {
    "iPhone15,2":"iPhone 14 Pro", "iPhone15,3":"iPhone 14 Pro Max",
    "iPhone15,4":"iPhone 15", "iPhone15,5":"iPhone 15 Plus",
    "iPhone16,1":"iPhone 15 Pro", "iPhone16,2":"iPhone 15 Pro Max",
    "iPhone17,1":"iPhone 16 Pro", "iPhone17,2":"iPhone 16 Pro Max",
    "iPhone17,3":"iPhone 16", "iPhone17,4":"iPhone 16 Plus",
    "iPhone17,5":"iPhone 16e", "iPhone18,1":"iPhone 17 Pro",
    "iPhone18,2":"iPhone 17 Pro Max", "iPhone18,3":"iPhone 17",
    "iPhone18,4":"iPhone Air",
    "iPad13,1":"iPad Air (4th generation)", "iPad13,2":"iPad Air (4th generation)",
    "iPad13,8":"iPad Pro 12.9-inch (5th generation)",
    "iPad13,9":"iPad Pro 12.9-inch (5th generation)",
    "iPad13,10":"iPad Pro 12.9-inch (5th generation)",
    "iPad13,11":"iPad Pro 12.9-inch (5th generation)",
    "Mac14,6":"MacBook Pro 16-inch (2023)", "Mac14,10":"MacBook Pro 16-inch (2023)",
    "Watch7,12":"Apple Watch Ultra 3",
}

def safe_text(value, limit=254):
    if not isinstance(value,str):
        return None
    value="".join(c for c in value if c.isprintable()).strip()
    return value[:limit] or None

def metadata(data):
    model=safe_text(data.get("model"),128)
    paired=data.get("pairingDate",data.get("paired_at"))
    if isinstance(paired,str):
        try: paired=datetime.fromisoformat(paired.replace("Z","+00:00"))
        except ValueError: paired=None
    paired_at=None
    if isinstance(paired,datetime) and 1970<=paired.year<=2100:
        paired_at=paired.replace(tzinfo=paired.tzinfo or timezone.utc).astimezone(timezone.utc).date().isoformat()
    return {"apple_name":safe_text(data.get("name")), "model":model or "",
            "model_name":MODEL_NAMES.get(model,model), "paired_at":paired_at}

def enrich_metadata(store):
    """Backfill from saved private files, without Apple calls or key rewrites."""
    from .importer import normalized_plist
    import hashlib
    changed=False
    updated={key:dict(item) for key,item in store.items.items()}
    # SDK key records already contain model and paired_at, even on older installs.
    for item in updated.values():
        if not isinstance(item.get("key_file"),str): continue
        key_file=store.root/"keys"/item["key_file"]
        if key_file.resolve().parent!=(store.root/"keys").resolve():
            continue
        try: data=read_json(key_file,{})
        except (OSError,ValueError): continue
        details=metadata(data)
        for field,value in details.items():
            if value and not item.get(field):
                item[field]=value;changed=True
    # Export metadata carries the original Apple display name, rather than the
    # filename's punctuation-normalized name. Do not reimport any key material.
    for source in sorted((store.root/"export/accessories").glob("*.plist"),key=lambda p:(p.stat().st_mtime_ns,p.name)):
        try:
            data=normalized_plist(source.read_bytes())
            identifier=data.get("identifier")
            if not isinstance(identifier,str) or not identifier: continue
            item_id=hashlib.sha256(identifier.encode()).hexdigest()[:32]
            if item_id not in updated: continue
            item=updated[item_id]
            for field,value in metadata(data).items():
                if value and item.get(field)!=value:
                    item[field]=value;changed=True
        except (OSError,ValueError,TypeError,KeyError,AttributeError,ParseError,InvalidFileException):
            continue
    if changed:
        atomic_json(store.root/"items.json",updated)
        store.items=updated
    return changed
