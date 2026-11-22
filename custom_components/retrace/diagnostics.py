"""Counts only; never return tokens, account info, item names, keys or locations."""
async def async_get_config_entry_diagnostics(hass, entry):
    data = entry.runtime_data.data
    return {"app_status": data["health"].get("status"), "item_count": len(data["items"]),
            "selected_count": sum(bool(i["enabled"]) for i in data["items"]),
            "channel": data.get("channel","edge")}
