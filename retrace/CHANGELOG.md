# 0.1.14-dev.1.5 — Check saved device identity without another login

- Compare saved native device metadata against account identity in the restricted
  worker at startup. Report only match booleans or fixed error codes.
- Never provision, sign in, generate OTP headers, or replace saved state during
  this check. Apple account refusals remain explicit rather than password errors.

# 0.1.14-dev.1.4 — Distinguish Apple refusals from local sign-in errors

- Recognize typed Apple account/password and protocol refusals instead of an
  unclassified generic sign-in failure.
- Record fixed login substeps and safe numeric refusal codes, never response
  prose, credentials, phone numbers or raw tracebacks.
- Show recent sign-in errors even when an earlier location session is saved.

# 0.1.14-dev.1.3 — Explain and preserve local authentication setup failures

- Preserve setup-required failures through the background authentication flow.
- Show Configuration guidance beside Connect and in the status badges.
- Log only allowlisted setup reason codes, without account details.
- Clarify that first identity creation happens on Connect, not app startup.

# 0.1.14-dev.1.2 — Retrace artwork

- Add the project owner's icon to the app store, integration branding and web UI.
- Serve the icon and home-screen bookmark image locally.

# 0.1.12 — Patch HTTP dependency and check published advisories

- Upgrade aiohttp from 3.13.2 to 3.14.5 with reviewed wheel hashes.
- Check locked runtime dependencies against OSV before channel delivery.
- Keep exact, expiring applicability notes for setuptools platform/build-only
  advisories; new findings and expired notes block release validation.

# 0.1.11 — Fail safely on incomplete or unsafe restored data

- Validate the whole private tree before privileged ownership/mode repair.
- Reject symlink roots/directories/files, hardlinks and special files.
- Refuse to create a replacement identity over an incomplete restore, preserving
  entity identity and pairing expectations instead of silently starting over.

# 0.1.10 — Revoke and renew read-only pairing access

- Add an administrator-only, CSRF-protected pairing renewal action with explicit
  confirmation. Old read access is revoked immediately; tokens never enter UI.
- Verify the same app identity before accepting updated Supervisor discovery
  credentials; reconnect the existing integration without replacing entity IDs.
- Preserve Apple sessions and retry discovery if Supervisor is unavailable.
- Companion integration 0.1.10+ is required for automatic reconnection.

# 0.1.9 — Hash-checked runtime dependency lock

- Pin all 30 Python runtime dependencies to versions from the tested image.
- Require committed SHA-256 hashes and wheels in production and CI installs.
- Check dependency consistency in both environments; preserve direct dependency
  intent separately. This is not a vulnerability audit or image signature.

# 0.1.8 — Durable state and restore regression coverage

- Publish selection, metadata, imports and sightings to memory only after their
  atomic file write succeeds, avoiding misleading state after disk-write errors.
- Add synthetic restore checks for identities, choices, keys, sessions, sightings
  and search checkpoints, including permissions and corrupt-state rejection.
- Document safe same-channel restore and the remaining live Supervisor test.

# 0.1.7 — Bounded item searches with private checkpoints

- Check recent keys first, then at most one older key window per item refresh.
- Resume successful empty searches on later polls instead of repeatedly scanning
  from the beginning until timeout. Preserve checkpoints across restarts.
- Show incomplete searches explicitly; keep saved sightings and existing Apple
  pacing, global rate-limit pauses, worker limits and hard timeouts.

# 0.1.6 — Administrator access enforced in the app

- Require the exact administrator group from trusted Supervisor ingress, as
  well as the trusted peer and user identity; reject missing group headers.
- Preserve CSRF protection and the separate read-only integration API.
- Requires Supervisor 2026.11.0 or newer for forwarded group information.

# 0.1.5 — Diagnose slow item lookups

- Persist allowlisted query phase, elapsed time and aggregate counts.
- Surface timeout diagnostics without names, identifiers, keys or locations.
- Keep asynchronous queries, limits and credentials unchanged.

# 0.1.4 — Descriptive item labels and consistent Edge naming

- Add secondary labels with Apple-provided name, known model name, pairing date
  and a short app ID; omit unavailable information.
- Backfill existing items from saved files without a login or key rewrite.
- Give same-name exports unique hashed filenames instead of overwriting them.
- Use Edge consistently for development labels, including legacy integration
  titles; retain existing entity IDs, unique IDs and user title overrides.
- Remove the obsolete hardcoded diagnostics version.

# 0.1.3 — Setup, feedback, Edge names and manual refresh

- Explain separate location-access and item-key discovery sessions.
- Reuse the saved discovery session; fresh login is an explicit choice.
- Submit discovery email and password together through private stdin handling.
- Preserve typed recovery responses while refreshing background status.
- Confirm the exact number of saved tracked items; retain edits after errors.
- Add per-item asynchronous refresh with one-minute spacing, shared worker
  limits, duplicate suppression and the shared Apple rate-limit pause.
- Show per-item refresh progress and check time separately from sighting time.
- Publish channel metadata; new Edge entities have explicit Edge names/IDs.
  Existing stable unique IDs and existing registry IDs are retained.
- Make the app map an optional preview; link native HA devices and map views.
- Add locked DOM regression tests; these are not bundled in the runtime app.

# 0.1.2 — Concurrent incremental item queries

- Save and display each item result immediately.
- Hard-limit each item query to 120 seconds, including synchronous key derivation.
- Continue after a timed-out item and expose per-item progress counts.
- Keep old sightings intact and never pass Apple credentials on child argv.
- Two asynchronous workers, shared request pacing, and no shared-session writes.
- Stop queued work on authentication-required or rate-limit responses.
- Share a 30-minute HTTP 429 cooldown across both workers.
- Prepare Edge/stable repository delivery instead of repeated archive installs.

# 0.1.1 — Polling visibility

- Distinguish no location reports from successful tracking.
- Surface report counts and last/next poll times without secrets.
- Treat repeated empty Apple responses as a protocol failure, not no sightings.
- Wake polling after account connection/selection; preserve query cooldown.
- Emit only allowlisted count/status diagnostics in the app log.

# 0.1.0 — Local experimental prototype

- Guided ingress account verification and separate key-recovery flow.
- Selected-item polling, local helper and owner-only token/key storage.
- Native companion integration, Beta trackers, last sightings and Repairs.
- Map overview and item selection; no battery/address fabrication.

## 0.1.14-dev.1.6 — Mac provider candidate

- Preserve the current Apple Music provider and offer an explicit, default-off
  experimental macOS provider in Setup; no automatic fallback or identity migration.
- Isolate pinned macOS CoreADI emulation in the restricted worker. Keep provisioning
  HTTP in the owned parent transport and machine/account state independently encrypted.
- Use the Mac device ID for Apple account requests and a separate stable UUID for
  CloudKit. Serialize signing/state updates across item poll processes.
- Change active polling provider only after the new session is durably saved.
- Retain upstream GPL source/license notices. Native binaries stay outside Git/images.
