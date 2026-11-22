DOMAIN = "retrace"
PLATFORMS = ["device_tracker", "sensor"]

def normalize_channel(channel):
    """Legacy unmarked/Beta installations are development installations."""
    return "stable" if channel=="stable" else "edge"

def entry_title(channel):
    return "Retrace" if normalize_channel(channel)=="stable" else "Retrace Edge"


def migrated_entry_title(title, channel):
    """Rename only known product defaults, preserving user-selected titles."""
    defaults = {"Retrace (Beta)", "Retrace (Edge)", "Retrace (Stable)"}
    return entry_title(channel) if title in defaults else title
