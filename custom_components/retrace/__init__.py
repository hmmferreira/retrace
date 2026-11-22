"""Native tracking entities; the existing MQTT deployment is independent."""
from datetime import timedelta
import logging
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import issue_registry as ir
from .api import Api, Unauthorized
from .const import DOMAIN, PLATFORMS, normalize_channel, migrated_entry_title

_LOGGER = logging.getLogger(__name__)

class Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60), config_entry=entry)
        self.entry = entry
        self.api = Api(async_get_clientsession(hass), entry.data["host"], entry.data["token"])

    async def _async_update_data(self):
        try:
            data = await self.api.snapshot()
        except Unauthorized as error:
            raise ConfigEntryAuthFailed("Reconnect the app's read-only pairing credential") from error
        except Exception as error:
            raise UpdateFailed("Retrace app is unavailable") from error
        status = data["health"].get("status")
        for key, active in {"apple_reauth":status=="reauth_required", "poll_failed":status in ("error","partial_results")}.items():
            issue_id = self.entry.entry_id + "_" + key
            if active:
                ir.async_create_issue(self.hass, DOMAIN, issue_id, is_fixable=False,
                    severity=ir.IssueSeverity.WARNING, translation_key=key)
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return data

async def async_setup_entry(hass, entry):
    coordinator = Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    channel=normalize_channel(coordinator.data.get("channel"))
    updates={}
    if entry.data.get("channel")!=channel:
        updates["data"]={**entry.data,"channel":channel}
    title=migrated_entry_title(entry.title,channel)
    if title!=entry.title:
        updates["title"]=title
    if updates:
        hass.config_entries.async_update_entry(entry,**updates)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for key in ("apple_reauth","poll_failed"):
            ir.async_delete_issue(hass, DOMAIN, entry.entry_id + "_" + key)
    return unloaded
