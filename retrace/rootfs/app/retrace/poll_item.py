"""One bounded child query. Credentials stay in private files, never argv."""
import asyncio
from datetime import timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from .apple import ReportingAccount, ReportSourceUnavailable, PacedHttp, RateLimited
from .storage import read_json, atomic_json
from .private_session_store import restore_reporting_account
from .owned_session import SessionBlocked
from .progress import QueryProgress,safe_query_diagnostic
from .search import fetch_bounded

async def query():
    from findmy import FindMyAccessory
    from findmy.errors import InvalidCredentialsError, UnauthorizedError
    root=Path(os.environ.get("RETRACE_DATA","/data/retrace"))
    request=json.loads(sys.stdin.buffer.read(4096))
    item_id=request["id"]
    if not isinstance(item_id,str) or not re.fullmatch("[a-f0-9]{32}",item_id):
        raise ValueError("Invalid item identifier")
    progress=QueryProgress(root/"progress"/(item_id+".json"))
    items=read_json(root/"items.json",{})
    item=items[item_id]
    if not item["enabled"]:
        return {"ok":True,"report":None}
    key_file=root/"keys"/item["key_file"]
    if key_file.resolve().parent != (root/"keys").resolve():
        raise ValueError("Invalid key file")
    try:
        account=await restore_reporting_account(root)
    except SessionBlocked as error:
        setup_codes={"worker_boundary_unavailable","artifact_review_required","artifact_license_review_required",
            "artifact_not_approved","artifact_architecture_unsupported","artifact_digest_mismatch",
            "session_artifact_mismatch","artifact_unavailable","artifact_policy_invalid","artifact_source_unverified",
            "reporting_backend_unavailable","signer_initialization_failed","signing_failed"}
        return {"ok":False,"error":"setup_required" if error.code in setup_codes else "authentication_required",
            "diagnostic":safe_query_diagnostic({"stage":"session_restore","code":error.code})}
    account._http=PacedHttp(account._http,root/"request-gate")
    try:
        accessory=FindMyAccessory.from_json(key_file)
        progress.instrument(account,accessory)
        report,search_pending=await fetch_bounded(account,accessory,root/"search"/(item_id+".json"))
        progress.complete()
        # Poll children never write the shared session: UI authentication owns it.
        atomic_json(key_file,accessory.to_json())
        return {"ok":True,"search_pending":search_pending,"report":None if report is None else {
            "latitude":report.latitude,"longitude":report.longitude,
            "accuracy":report.horizontal_accuracy,
            "timestamp":report.timestamp.astimezone(timezone.utc).isoformat()}}
    except RateLimited:
        return {"ok":False,"error":"rate_limited"}
    except ReportSourceUnavailable:
        return {"ok":False,"error":"apple_empty_response"}
    except (InvalidCredentialsError,UnauthorizedError):
        return {"ok":False,"error":"authentication_required","diagnostic":{"stage":"report_fetch","code":"authentication_required"}}
    except ValueError as error:
        return {"ok":False,"error":"authentication_required" if str(error)=="No username or password specified" else "poll_failed"}
    except Exception:
        return {"ok":False,"error":"poll_failed"}
    finally:
        await account.close()

def main():
    os.umask(0o077)
    logging.disable(logging.CRITICAL)
    try:
        result=asyncio.run(query())
        print(json.dumps(result,allow_nan=False),flush=True)
    except Exception:
        print('{"ok":false,"error":"poll_failed"}',flush=True)

if __name__=="__main__":
    main()
