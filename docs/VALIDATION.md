# Local validation — 2026-11-16

- 25 automated tests passed in an isolated, network-disabled container with no
  live runtime mounts: ingress/CSRF/read-only API, secrets, recovery ownership and
  full synthetic prompt journey, import normalization, polling/timestamps/expiry,
  and installer dry-run/integrity/no-overwrite.
- Built the complete amd64 app image on Dragon. Upstream patched Rust tests passed:
  endpoint lookup tests and session/identity/private escrow-password tests.
- Empty-state packaged startup check passed with uid 1000, read-only root,
  no added capabilities, no host ports, no-new-privileges and tmpfs data.
  Authenticated snapshot worked; direct management UI access was denied.
  Local helper returned HTTP 200; exporter help showed the cached-session flags.
- Python sources and integration JSON parsed. Supervisor YAML parsed with no
  published host port. Native integration/hassfest and browser rendering tests
  have not yet run. These focused tests do not prove end-to-end HA compatibility.
- No live Apple authentication was attempted in the new app. No original sessions,
  keys or item data were copied into it. The baseline bridge remains unchanged.

## Concurrent polling update — 2026-11-16

33 isolated tests passed before channel tests were added. Built 0.1.2 and passed
its non-root/private-state/ingress/local-helper startup smoke check. Tests cover
two-worker limits, immediate partial results, timeout of a CPU-bound process,
cancellation cleanup, global pacing, rate limits, old timestamps and cooldown.
Live Home Assistant still runs local app 0.1.1; these changes have not yet
produced a verified live Apple report. Do not claim the live issue resolved.

Repository CI passed all 36 tests on the first source push. Channel delivery
initialization needed a fix for staged orphan-branch files; delivery is being
verified separately before advertising the channel as installable.

The corrected GitHub run passed all 37 tests and delivered Edge
0.1.2-dev.2.1 (branch commit 28439ba). Home Assistant accepted the repository
and listed its app. HACS accepted the integration and downloaded edge.
Supervisor install was submitted once; its 300-second tool timeout did not
establish completion or failure. Await durable installed state and UI account
setup before claiming live polling success. Configuration check passed and
Core restart was initiated to activate the HACS-managed companion integration.

Final offline suite: 38 tests passed, including cross-worker HTTP 429 cooldown.
Final 0.1.2 image built and passed non-root/private-state/ingress/helper startup
smoke. Previous repository run also published v0.1.2-dev.3.1 successfully.
No stable release is approved. Supervisor still has no durable installed
version for Edge after its install tool timed out; user UI status is pending.
Core is back after the HACS activation restart; no retrace startup errors
were returned by the system-log query. Existing MQTT status remains ok, reports 9.

## Usability 0.1.3

47 Python test cases passed, including a Node/jsdom runner covering six DOM
scenarios: saved-count feedback, failed-save edit retention, typed SMS preservation,
combined credentials, saved discovery-session reuse, and one-item refresh.
Backend tests verify private credential consumption, explicit fresh-login,
shared automatic/manual concurrency, duplicate refresh suppression, cooldown,
Apple pause and CSRF/read-only API boundaries. DOM dependencies are locked and
excluded from app runtime. No native HA config entries existed at the initial
live check; no existing entity registry IDs were renamed. Real browser visual
testing and a live native entity creation check remain pending.

## Item descriptions and Edge terminology — 0.1.4

52 Python cases pass, including eight DOM scenarios. New tests verify bounded
friendly-model mapping, date handling, metadata allowlisting, legacy-channel
normalization and backfill without key rewrites. Production exporter build
passes two Rust tests for collision-free same-name exports and safe bounded
filenames. Live Edge polls now repeatedly return three reports for five selected
items, with two item timeouts; two native integration entries are loaded.
Native label migration and descriptive backfill have not yet been verified live.
