"""Find My-only inventory commit with atomic manifest visibility.

Only accessory mappings reach disk; recovered Keychain peers/views never do.
Immutable-generation key filenames leave old poll children and old manifests
usable if staging or the final manifest write fails. Orphan cleanup is deferred.
"""
import asyncio
import hashlib
import json
from .storage import atomic_json,read_json
from .descriptions import metadata,safe_text
from .shared_discovery import SharedDiscoveryError

FIELDS={"type","master_key","skn","sks","paired_at","name","model","identifier",
        "group_identifier","serial_number","alignment_date","alignment_index"}

class PrivateInventorySink:
    def __init__(self,store,worker):self.store,self.worker=store,worker
    def _stage(self,accessories):
        from findmy import FindMyAccessory
        pending={}
        for accessory in accessories:
            if not isinstance(accessory,FindMyAccessory):raise SharedDiscoveryError("invalid_inventory")
            raw=accessory.to_json()
            if not isinstance(raw,dict) or raw.get("type")!="accessory":raise SharedDiscoveryError("invalid_inventory")
            data={k:v for k,v in raw.items() if k in FIELDS}
            stable=data.get("identifier")
            if not isinstance(stable,str) or not 0<len(stable)<=512 or any(not c.isprintable() for c in stable):
                raise SharedDiscoveryError("invalid_inventory")
            item_id=hashlib.sha256(stable.encode()).hexdigest()[:32]
            if item_id in pending:raise SharedDiscoveryError("invalid_inventory")
            old=self.store.items.get(item_id,{})
            filename=old.get("key_file")
            if isinstance(filename,str) and filename and filename==filename.split("/")[-1] and "\\" not in filename:
                saved=read_json(self.store.root/"keys"/filename,{})
                if all(saved.get(k)==data.get(k) for k in ("master_key","skn","sks","paired_at")):
                    for field in ("alignment_date","alignment_index"):
                        if field in saved:data[field]=saved[field]
            # Validate the allowlisted record before writing, including alignment.
            FindMyAccessory.from_json(data)
            encoded=json.dumps(data,sort_keys=True,allow_nan=False).encode()
            if len(encoded)>65536:raise SharedDiscoveryError("invalid_inventory")
            key_file=item_id+"-"+hashlib.sha256(encoded).hexdigest()[:24]+".json"
            pending[item_id]=({"name":safe_text(data.get("name")) or "Find My item",
                              "key_file":key_file,**metadata(data)},data)
        # Nothing becomes referenced by the inventory until every item validates.
        for details,data in pending.values():atomic_json(self.store.root/"keys"/details["key_file"],data)
        return pending

    async def __call__(self,accessories):
        if not isinstance(accessories,list) or len(accessories)>10000:raise SharedDiscoveryError("invalid_inventory")
        async with self.worker.poll_lock:
            self.worker.inventory_busy=True
            acquired=0
            try:
                # Drain existing per-item children and reserve all slots while
                # staging; new manual refresh requests get a clear busy result.
                for _ in range(self.worker.CONCURRENCY):
                    await self.worker.query_slots.acquire();acquired+=1
                pending=await asyncio.to_thread(self._stage,accessories)
                updated=dict(self.store.items)
                for item_id,(details,_) in pending.items():
                    old=updated.get(item_id,{})
                    updated[item_id]={**details,"name":old.get("name",details["name"]),"enabled":old.get("enabled",False)}
                # Commit and publish together on the event loop, so selection
                # saves cannot race a stale copy during an awaited disk write.
                atomic_json(self.store.root/"items.json",updated)
                self.store.items=updated
                self.worker.request_poll()
            finally:
                for _ in range(acquired):self.worker.query_slots.release()
                self.worker.inventory_busy=False
