# Repository delivery and migration

## Channels

Development source lives on main. CI runs synthetic tests without Apple secrets,
and explicit delivery renders only allowlisted app, integration and documentation
files into the edge branch. Source pushes never overwrite the side-by-side Shared
Edge package; use the reviewed evaluation renderer for that app. Versions are unique (`0.1.2-dev.RUN.ATTEMPT`), never a mutable `latest`.
App store URL: https://github.com/hmmferreira/retrace#edge

Stable URL (after the first validated promotion):
https://github.com/hmmferreira/retrace#stable
Run the channel workflow on main, choose stable, and acknowledge completion of
RELEASE.md checks. Stable versions cannot be overwritten: increase config.yaml's
version first. Stable is not automatically promoted from Edge. Matching tagged integration
releases are created only after the channel branch is successfully pushed.

These are source-build channels for now. Home Assistant builds on Install/Update;
users do not copy source files themselves. Prebuilt public images are deliberately
not published while exporter/dependency redistribution rights are unresolved.
Once cleared, publish a tested immutable GHCR version FIRST, make the package
pullable, and only then advertise that version with `image:` in the channel config.
Do not use a mutable edge image tag. Preserve the source-build recipe and notices.

## One-time move from a local install

Supervisor hashes the repository URL (including #branch) into the app ID.
The local install, Edge and stable therefore have separate private /data volumes,
sessions and native integration instance IDs. Installing Edge cannot silently
adopt the local app's credentials. Keep the old app/data for rollback; use the
Edge ingress setup once and confirm its discovered integration. Avoid running
multiple Apple pollers longer than needed for comparison. Stop the old local development app after
checking two successful Edge polls, UI responsiveness and native tracker history.
The independent existing MQTT tracker does not change.

After this one-time move, updates to that channel use Settings → Apps → Update,
retaining its /data state. Switching channels is another separate installation;
no cross-volume secret migration is implemented yet. Never upload sessions or keys
to GitHub and never paste credentials into repository URLs.

## Companion integration

Supervisor updates the app, not custom_components. Keep the app without a /config
write mount. Add this GitHub repository to HACS as category Integration to manage
its files; approve the required Core restart through HA. During development use
HACS Redownload and select edge. The delivery workflow creates a matching GitHub release/tag for each channel
(Edge is a prerelease; stable requires the live-validation gate). In HACS,
enable beta/prerelease versions once to receive tagged Edge integration updates.
Stable users leave prereleases disabled. App and integration updates remain
separate UI actions; custom integration code activation needs a Core restart.
The integration reads snapshots every 60 seconds, not Apple itself. Version/API
compatibility must be checked before each stable release.

## Polling contract

Two independent asynchronous device workers take items from a queue. Process
starts and shared Apple POST requests are spaced by at least one second. CPU key
derivation runs in child processes, so it cannot block the web event loop.
Each child has a 120-second hard limit and is killed/reaped on timeout/cancellation.
Every completed valid report is saved immediately, preserving original timestamps.
One hung item cannot hold back the other worker's results. Account state is read
only by children; only the UI authentication flow saves its token-only session.
Expired sessions require sign-in instead of persisting a password.
An Apple 429 stops queued work and sets a shared 30-minute request cooldown.
The other worker checks it before sending another POST (a request already sent
can still finish). This is combined with
15-minute minimum polling and exponential error backoff up to one hour. Apple's
private API has no documented quota here; concurrency is intentionally conservative.
The request limiter uses private local metadata, not a cookie or credential file.

For manual per-item refresh, cached discovery sessions, setup feedback and new
channel-specific entity names/IDs, see USABILITY.md. Per-item refresh stays on
the CSRF-protected ingress management API; the companion snapshot API is read-only.


## Pairing credential renewal

Update the companion integration to 0.1.10 or newer before using Setup → Home
Assistant connection security. Confirming renewal revokes the old read-only
credential immediately. The replacement is privately announced to Supervisor;
the existing integration verifies the same instance and updates its connection
without new entities or copying tokens through the browser. Discovery retries
if Supervisor is temporarily unavailable. The read-only API has no renewal
endpoint. Apple credentials and source item keys are not changed.


## Fresh Stable setup (owner decision, 2026-11-22)

Stable and Edge are independent installations. Do not transfer Edge history,
credentials, device selections or entity IDs into Stable. Edge entities remain
explicitly Edge and are disposable development data; a fresh Stable setup creates
its own entities/history. Keep companion integration code on a compatible released
version for everyday use; app channel separation alone does not provide separate
Core integration code versions. Preparing a release never deletes the working
Edge setup implicitly. Extended soak/recovery observation continues after release.
