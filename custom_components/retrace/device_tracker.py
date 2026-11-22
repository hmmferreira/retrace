from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from .entity import ItemEntity, discover

async def async_setup_entry(hass, entry, async_add_entities):
    await discover(entry.runtime_data, async_add_entities, Tracker, entry)

class Tracker(ItemEntity, TrackerEntity):
    _attr_name = None
    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "_location")
    @property
    def source_type(self):
        return SourceType.GPS
    @property
    def latitude(self):
        return self.report.get("latitude")
    @property
    def longitude(self):
        return self.report.get("longitude")
    @property
    def location_accuracy(self):
        return self.report.get("accuracy", 0)
    @property
    def extra_state_attributes(self):
        return {"report_timestamp": self.report.get("timestamp")}
