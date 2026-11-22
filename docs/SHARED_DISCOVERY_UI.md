# Shared-account UI adapter (experimental)

The feature branch contains an injectable UI path; production composition in
`server.main` still selects the working exporter. There is no environment switch
that activates an unreviewed provider or bypasses the remaining release gates.

`AppleWorker` accepts an async `account_factory`, async `session_writer`, and an
`authenticated(owner, account)` handoff. `SharedDiscoveryUI.bind(worker)` requires
the first two hooks before installing the handoff. The worker saves the reviewed
private session, hands the same authenticated account to discovery, and transfers
ownership instead of closing it prematurely. The UI adapter closes that account
on discovery completion, failure, expiry or cancellation. Discovery obtains its
service token while the main login password remains transient, then clears it.

`make_app(..., shared_ui=bridge)` exposes shared auth status only on the protected
management snapshot, never the integration's read-only API. Authentication POSTs
return 202 promptly; snapshots provide the verification/progress state. Shared
recovery accepts only opaque device choice and passcode, or cancellation. It
never accepts another account credential pair. Main login requires explicit
item-key recovery consent. The UI hides the second email/password form, explains
account authentication versus device unlock, preserves partially typed passcodes
across background refresh, and clears passcodes before submitting them.

The optional `PrivateInventorySink(store, worker)` allowlists FindMyAccessory
records only. It validates the full batch, preserves stable hashed item IDs,
selection/custom labels and existing key alignment when material matches, stages
private key generations, then atomically replaces the item manifest. Failed
staging/manifest writes leave the previous manifest valid. It drains per-item
poll slots and holds the scheduled poll lock while saving; new manual refreshes
receive a discovery-busy response. New items remain unselected. Orphan-generation
cleanup is deferred; recovered Keychain peer/view records are never serialized.

## Tests and activation gates

Synthetic tests cover async HTTP 202/progress and consent, same-account ownership,
opaque unlock, secret omission, mandatory lifecycle injection, inventory validation,
private permissions, atomic manifest failure, alignment/selection preservation and
poll draining. Browser tests cover the shared-account explanation and unlock form.
No live Apple, Home Assistant or household credential operation is used.

Remaining composition must explicitly provide the reviewed provisioning/restore
factory, encrypted session writer/key lifecycle, and the matching report-worker
restore path. Poll children now select the encrypted owned manifest when present and
refuse legacy fallback on owned-state failure; see OWNED_SESSION.md for the
private storage composition and backup requirements. Do not enable this adapter on Edge until that composition, dependency
provenance, process egress controls and a deliberate protected-UI live comparison
are reviewed. Restoring location tokens does not make a fresh Keychain PET
available; adding items later must explicitly reconnect through the main login.

## Integration review

`compose_shared_ui(store, account_factory=..., session_writer=...,
session_available=..., discovery_factory=...)` constructs the worker, private sink
and bridge explicitly. Its factory refuses an account whose HTTP transport is not
the app-owned account profile, closes rejected objects and clears transient
passwords. Pass the private session store's async `save` and a local presence
predicate; manual/scheduled readiness and management snapshots now use that
predicate instead of assuming a legacy session file. The predicate is not a
validation or network operation: actual reporting restore must enforce integrity,
expiry and provider restrictions.

Sign-in admission schedules terminal-flow cleanup inside the background task so
restarting a finished flow never waits on account closure in the HTTP request.
Concurrent cancel/admission is rejected clearly. Account construction, login and
closure are bounded; cancellation clears pending passwords and reaps auth tasks.
Expired verification is detected when the worker expires its pending account and
maps to a main-sign-in prompt. Session-save errors do not start discovery or leave
an authenticated account pending. Shared discovery failures/expiry reopen the
main form and explain that saved tracked items survive. Busy/invalid owner and
invalid unlock choices produce redacted 409 messages, not a generic 503.

The original activation warning above records the initial adapter checkpoint.
The integration review is adding owned reporting restoration separately; production
`server.main` still does not activate this composition. Fresh identity provisioning
still requires a reviewed isolated worker before a complete new-account UI can be
enabled. No real account, passcode, HA request or deployment is part of these tests.
