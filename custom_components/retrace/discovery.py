"""Allowlist Supervisor connection metadata; never retain unrelated fields."""
import re
from .const import normalize_channel

def connection_data(config,slug):
    instance=config.get("instance_id")
    token=config.get("token")
    host=config.get("host")
    if not isinstance(instance,str) or not re.fullmatch(r"[a-f0-9]{32}",instance):
        raise ValueError("Invalid instance identity")
    if not isinstance(token,str) or not 32 <= len(token) <= 256:
        raise ValueError("Invalid pairing credential")
    if not isinstance(host,str) or not re.fullmatch(r"[a-z0-9-]+-retrace(?:\.local\.hass\.io)?",host):
        raise ValueError("Invalid discovered host")
    if not isinstance(slug,str) or not re.fullmatch(r"[a-zA-Z0-9_]+",slug):
        raise ValueError("Invalid app slug")
    return {"host":host,"token":token,"instance_id":instance,"app_slug":slug,
            "channel":normalize_channel(config.get("channel"))}
