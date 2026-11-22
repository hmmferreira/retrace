"""Bounded, resumable SDK key search; checkpoints stay in private app data."""
from datetime import datetime, timedelta, timezone
from .storage import atomic_json, read_json

# The SDK otherwise searches every index since pairing when not yet aligned.
# Always revisit recent indices; advance a separate older window only after a
# successful empty response. Apple pacing/rate-limit handling is unchanged.
RECENT_INDICES = 580
OLDER_INDICES = 2320

async def fetch_bounded(account, accessory, checkpoint):
    now = datetime.now(timezone.utc)
    get_min, get_max = accessory.get_min_index, accessory.get_max_index
    floor, top = max(0,get_min(now-timedelta(days=7))), get_max(now)
    if not (isinstance(floor,int) and isinstance(top,int) and 0 <= floor <= top):
        raise ValueError("Invalid search bounds")
    recent_floor = max(floor,top-RECENT_INDICES+1)

    async def window(low,high):
        # Keep the real SDK report decryption and alignment logic. Bounds limit
        # only this call; restore methods even if Apple rejects the request.
        accessory.get_min_index = lambda date: max(low,get_min(date))
        accessory.get_max_index = lambda date: min(high,get_max(date))
        try:
            return await account.fetch_location(accessory)
        finally:
            accessory.get_min_index, accessory.get_max_index = get_min,get_max

    report = await window(recent_floor,top)
    if report is not None or recent_floor == floor:
        checkpoint.unlink(missing_ok=True)
        return report,False
    saved = read_json(checkpoint,{})
    cursor = saved.get("next_index") if isinstance(saved,dict) and saved.get("version")==1 else None
    if type(cursor) is not int or not floor <= cursor < recent_floor:
        cursor = recent_floor-1
    lower = max(floor,cursor-OLDER_INDICES+1)
    report = await window(lower,cursor)
    pending = report is None and lower > floor
    if pending:
        atomic_json(checkpoint,{"version":1,"next_index":lower-1})
    else:
        checkpoint.unlink(missing_ok=True)
    return report,pending
