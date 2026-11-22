# Setup and daily-use direction

## Why two sign-ins exist now

The Python location-report client and Rust item-key exporter maintain different
session formats and authentication identities. This prototype does not translate
tokens between them. Two initial authorizations are an implementation limitation,
not a claim that Apple always requires every client to sign in twice.

Location access reads reports periodically. Item discovery obtains encrypted
accessory keys through Keychain recovery. The exporter already persists a
private token-only session, but the original UI forced --fresh-login on every
discovery. This release removes that default; a valid saved discovery session
can be reused. Expiry still needs explicit sign-in, and a trusted device's unlock
passcode may still be required. Do not cache that passcode to hide the prompt.

Discovery email and password now share one form. The bridge feeds them only
when the matching exporter stdin prompts arrive, clears them before the next
challenge, and never places them in argv/environment/public state/logs. SMS and
trusted-device passcodes remain separate Apple challenges. A future common
authentication backend could remove the duplicated initial authorization, but
that needs protocol/security work rather than token-format guessing.

## Feedback

Setup names each purpose and shows connection/session status. Tracked choices
have unsaved state, disabled unchanged Save, exact saved count and specific
success/error messages. Saved choices do not imply fresh sightings. Background
refresh does not replace an unchanged recovery input or erase typed SMS codes.

## Manual item refresh

Refresh this item queues only that item's Apple request asynchronously and uses
the next free slot shared with scheduled polling (maximum two). A request already
running is reused. Attempts within 60 seconds are declined with a wait message.
An Apple HTTP 429 pause always overrides manual refresh and survives app restart.
The minute is this app's anti-spam guard, not a published Apple quota.

A refresh retrieves Apple's latest available report; it cannot make an AirTag
broadcast or make a nearby Apple device relay it immediately. Last checked is
separate from Last sighting. Existing valid sightings are retained on failures.
Per-item refresh is currently in the ingress UI. The companion read API remains
read-only; a native HA refresh button would need a separately scoped control
credential rather than turning the snapshot credential into a write token.

## Edge isolation

Each installed app has its own persistent instance ID. Native unique IDs include
that instance ID and the item ID, so separate installs do not merge. Channel
metadata now travels in the image, snapshot and discovery announcement.
New devices are named Item (Edge), and new entity object IDs explicitly contain
retrace_edge. Legacy development installs use Edge; Stable remains a separate channel. Existing
registry IDs are preserved to avoid breaking consumers; existing entries require
an audited rename if the user wants their old IDs changed. Do not silently
regenerate an ID on every update.

The new companion code must be installed through HACS and Core restarted before
confirming discovery to use the new naming. The app's upgrade alone cannot
replace already-loaded native integration code.

## Native Home Assistant UI

The current app is an independent ingress page with its own DOM, not HA's
frontend component tree. Its simplified styling is not a claim of native
ha-* components. The optional Leaflet/OSM map is now collapsed and only starts
tile requests when opened. Standard HA map/device/history screens are linked.

The recommended daily interface is HA's built-in map and native tracker/history
cards. The confirmed companion integration is required for those entities.
Longer term, put setup/options into HA config flows, or an integration-owned
custom panel with HA selectors and forms, and keep Apple secrets in the worker.
That needs a deliberately scoped authenticated management API and authorization
review. Do not access private parent-frame DOM or give the existing read-only
API credential broad account-management permissions to imitate HA components.

## Delivery

After any active recovery/import finishes, update the Edge app from Apps.
Update the companion integration from HACS and restart Core once for new naming.
Confirm the discovered integration in Devices & services. Sessions, selections
and saved reports stay in the same app /data directory. No archive or terminal
copy is needed. First-time native dashboard confirmation and actual Apple
reports still need live verification.
