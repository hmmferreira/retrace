"""The integration has a read-only credential, never Apple credentials."""
import re
from aiohttp import ClientSession, ClientTimeout
from .const import normalize_channel

class Unauthorized(Exception):
    pass

def validate_host(host):
    if not isinstance(host, str) or not re.fullmatch(r"[a-z0-9-]+-retrace(?:\.local\.hass\.io)?", host):
        raise ValueError("Use the discovered Supervisor app host")
    return host

class Api:
    def __init__(self, session: ClientSession, host, token):
        self.session, self.host, self.token = session, validate_host(host), token

    async def snapshot(self):
        async with self.session.get(f"http://{self.host}:8100/v1/snapshot",
            headers={"Authorization": "Bearer " + self.token},
            timeout=ClientTimeout(total=15), allow_redirects=False) as response:
            if response.status in (401, 403):
                raise Unauthorized()
            response.raise_for_status()
            data = await response.json()
        if not isinstance(data.get("items"), list) or not isinstance(data.get("health"), dict):
            raise ValueError("Invalid app response")
        data["channel"]=normalize_channel(data.get("channel"))
        return data
