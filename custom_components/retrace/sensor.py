from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from .entity import ItemEntity, discover

async def async_setup_entry(hass, entry, async_add_entities):
    await discover(entry.runtime_data, async_add_entities, LastSeen, entry)

class LastSeen(ItemEntity, SensorEntity):
    _attr_name = "Last sighting"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "_last_seen")
    @property
    def native_value(self):
        value = self.report.get("timestamp")
        return datetime.fromisoformat(value) if value else None
