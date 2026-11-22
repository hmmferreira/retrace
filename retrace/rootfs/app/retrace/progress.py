"""Count-only query diagnostics. No item names, IDs, keys or locations in logs."""
import time
from .storage import atomic_json,read_json

PHASES={"loading","deriving_keys","requesting_reports","complete"}
def safe_progress(value):
    if not isinstance(value,dict) or value.get("phase") not in PHASES:
        return {}
    result={"phase":value["phase"]}
    for key in ("indices_checked","report_batches","reports_returned"):
        v=value.get(key)
        if isinstance(v,int) and not isinstance(v,bool) and 0<=v<=10_000_000:
            result[key]=v
    elapsed=value.get("elapsed_seconds")
    if isinstance(elapsed,(int,float)) and 0<=elapsed<=86400:
        result["elapsed_seconds"]=round(elapsed,1)
    return result

class QueryProgress:
    def __init__(self,path):
        self.path=path
        self.started=time.monotonic()
        self.last_write=-float("inf")
        self.value={"phase":"loading","indices_checked":0,"report_batches":0,"reports_returned":0}
        self.save(force=True)
    def save(self,force=False):
        now=time.monotonic()
        if force or now-self.last_write>=1:
            self.value["elapsed_seconds"]=round(now-self.started,1)
            atomic_json(self.path,self.value)
            self.last_write=now
    def instrument(self,account,accessory):
        keys_at=accessory.keys_at
        async_fetch=account.fetch_raw_reports
        def checked_keys(index):
            self.value["phase"]="deriving_keys"
            self.save()
            keys=keys_at(index)
            self.value["indices_checked"]+=1
            return keys
        async def fetch_reports(devices):
            self.value["phase"]="requesting_reports"
            self.value["report_batches"]+=1
            self.save(force=True)
            reports=await async_fetch(devices)
            self.value["reports_returned"]+=len(reports)
            self.save(force=True)
            return reports
        accessory.keys_at=checked_keys
        account.fetch_raw_reports=fetch_reports
    def complete(self):
        self.value["phase"]="complete"
        self.save(force=True)

QUERY_DIAGNOSTIC_STAGES={'session_restore','report_fetch'}
QUERY_DIAGNOSTIC_CODES={
    'session_expired','reauthentication_required','session_invalid','session_restore_failed',
    'session_storage_invalid','session_storage_unavailable','session_artifact_mismatch',
    'artifact_review_required','artifact_license_review_required','artifact_not_approved',
    'artifact_architecture_unsupported','artifact_digest_mismatch','artifact_unavailable',
    'artifact_policy_invalid','artifact_source_unverified','worker_boundary_unavailable',
    'reporting_backend_unavailable','signer_initialization_failed','signing_failed',
    'authentication_required','rate_limited','poll_failed',
}

def safe_query_diagnostic(value):
    if not isinstance(value,dict) or value.get('stage') not in QUERY_DIAGNOSTIC_STAGES or value.get('code') not in QUERY_DIAGNOSTIC_CODES:return {}
    return {'stage':value['stage'],'code':value['code']}
