# Shared authentication and Python discovery prototype

Status: Shared Edge private evaluation active; sign-in/discovery user-confirmed and saved-session polling verified; fresh SMS retry pending
rewrite. Edge remains on its working Rust-backed implementation. No production
Python dependency, Apple session, Keychain membership or item inventory changed.

## What is feasible

One app authentication flow can provide the account and identity used by both
location polling and key discovery. That means one email/password/2FA journey,
not one universal Apple token or one network request. Keychain escrow requires a
fresh password-equivalent token (PET), which the discovery candidate obtains by
an additional authentication exchange. It can use the transient credentials
already held during main sign-in. It cannot silently do this later from a
password-free saved session, and Apple can still demand another factor.

A trusted device's unlock passcode is a separate cryptographic approval. It is
not an unnecessary second Apple login and cannot be promised away. A native
recovery session also does not itself require enrolling another Keychain member;
this prototype calls recovery/read operations only and exposes no join, rename
or delete operation.

## Implemented in this branch

`shared_discovery.py` is app-owned orchestration over an injected Python protocol
client. It accepts an existing authenticated account, prepares a short-lived
in-memory token lease, clears the transient account password, lists recoverable
devices, accepts a device/passcode selection, and passes recovered Find My
accessories to a private sink. It does not spawn the Rust exporter or parse PTY
prompts. Starts/unlocks are background asyncio tasks with timeouts, expiry,
owner isolation, cancellation and generic errors. Public state contains opaque
choices and labels, never tokens, passcodes, hardware serials or item keys.

This is **not yet connected to AppleWorker's sign-in completion or the HTTP UI**.
The handoff must occur before the existing worker closes its authenticated
account. The caller retains account ownership until discovery finishes; the
controller closes its discovery client, not the caller's account. The private
sink must atomically validate/merge accessory keys, preserve selections and
coordinate with poll children. It must not persist the broader recovered
Keychain peer/view keys. These are integration requirements, not completed work.

## Protocol backend and licensing boundary

Released FindMy 0.10.2 has no `findmy.icloud` discovery API. It fails the prototype
capability check rather than starting a different sign-in or falling back to
Rust. A separate Python fork declares MIT and implements the protocol:

- repository: https://github.com/parawanderer/FindMy.py
- reviewed test revision: `8ecfae6cb34b29caf0bd8176ee73155ca81415a8`
- protocol discussion: https://github.com/malmeloo/FindMy.py/issues/278
- protocol documentation: https://github.com/parawanderer/OpenTagViewer/tree/main/docs/findmy-export

The experimental runner uses that clean, pinned checkout in a disposable image;
its source is not vendored or made a production dependency. The declared license
and claimed independent implementation still need provenance/compatibility
review before adoption. Translating the existing Rust source is not the approach
used here. We have already inspected that source historically and do not label
our work a clean-room cryptographic reimplementation. No license blocker is
claimed resolved merely by creating an adapter or changing languages.

## Test evidence

- Existing app regressions, 15 controller cases and 17 transport cases: 111 tests.
- Candidate backend suite: 877 tests passed in a read-only container, with no
  network, no Apple account and no production mounts.
- Six integration tests include running our controller over the candidate's real
  key-share/zone/record decryption code and synthetic account fixtures, producing
  an accessory that derives rolling advertising keys.
- Ownership, no duplicate account input, secret redaction, invalid choices,
  passcode validation, no automatic retries, token expiry/revocation, timeout,
  cancellation, inventory sink failures and resource closing are covered.

These tests prove local composition and failure handling, not Apple's live
protocol or a successful import from the household account. The app-owned client construction now closes its resources when initial open
is cancelled, with explicit coverage. Anisette provisioning and OS-level egress
isolation still require review before UI integration. See CREDENTIAL_BOUNDARY.md. Its own documentation distinguishes synthetic success from
live account verification.

Developer-only reproduction (the backend checkout must match backend.json and
have no local changes):

```sh
python3 tools/review-shared-discovery.py /path/to/reviewed/FindMy.py
```

The runner uses the existing private Portainer configuration. Builds download
public test dependencies; the test container itself has network disabled and no
host/runtime mounts. It packages allowlisted source/tests only. Never substitute
production session files, keys, account exports or a real passcode for fixtures.

## Before replacing the existing extractor

1. Review/pin the Python backend and its dependencies, including provenance, provisioning and
   process/network isolation. Retain notices; audit changed SDK behavior.
2. Wire main sign-in completion to the owned discovery session and expose one
   unified UI flow. Later discovery requiring a fresh PET must request main-flow
   reauthentication explicitly, without retaining a password.
3. Implement the atomic Find My-only private inventory sink and preservation of
   stable IDs, selections, alignment and existing polling.
4. Run an explicit live comparison using the app's protected UI for the device
   passcode. Do not collect a passcode through chat or test logs. Verify no trust
   join/write calls and compare actual recovered accessories/sightings.
5. Only then remove the Rust binary/build patches from a tested image. The helper
   image's separate licensing/provenance review does not disappear with Rust.


## Owned transport increment — 2026-11-19

Account, CloudKit and escrow HTTP for the prototype now go through the app-owned
transport with explicit Apple destinations, strict TLS, private-DNS rejection and
no redirects/environment proxies. Discovery refuses an unprotected account.
Candidate clients are composed explicitly, without changing shared module globals
or the production SDK. The public Apple root is bundled and hash-checked.
See [credential boundaries and tests](CREDENTIAL_BOUNDARY.md), including the
separate Anisette network paths and why an in-process wrapper is not a malicious
code sandbox. UI activation remains gated; Edge and its dependency lock have not
changed.

## Offline signer increment — 2026-11-19

The prototype refuses the SDK's default downloading/remote signer. It accepts an
app-owned offline signer with a verified local artifact and existing provisioning
only. Signing leaves the asyncio event loop, implicit provisioning/downloads stop
with redacted errors, and transient prepared headers are cleared after use.
Validation: 120 app cases, 877 candidate cases and seven composition cases pass;
the 15 controller cases also pass in the candidate environment. Fresh provisioning,
owned restore, UI wiring and process isolation remain open; no Edge deployment.

## Integrated review checkpoint — 2026-11-19

The three parallel implementations are now reviewed together. Encrypted session
storage publishes matching private generations atomically; per-item report
processes restore the owned account and preserve error classification, pacing and
explicit reauthentication. UI composition takes explicit account/session hooks,
uses async progress and cancellation, and privately commits item inventories.
Signer cancellation immediately revokes reuse and rejects late native results.
Session snapshots retain only required reporting/CloudKit token scopes.

Validation: 168 app tests, 877 pinned backend cases, ten real candidate composition
cases, and 15 controller cases in the candidate runtime (also in the app count).
Tests use synthetic state and network-disabled containers. No live Apple login,
provisioning, household migration, Home Assistant restart or Edge deployment.

Deployment is still gated. Missing: reviewed artifact/distribution policy and
isolated native provisioning worker with denied networking, restricted filesystem
and bounded private IPC/termination; dependency provenance/licensing sign-off;
backup/restore rehearsal and deliberate protected-UI live comparison. Production
main and dependency lock remain unchanged. This checkpoint closes the old report
restoration gap but is not permission to enable unfinished provisioning.

## Security and recovery rehearsal — 2026-11-19

See SECURITY_RECOVERY_REVIEW.md: 172 app tests, 877 backend tests and 12 candidate
integration tests pass, including full private-copy recovery after original
directory deletion, missing/mixed key failures and post-replace fsync failure.
OSV check of 30 locked Python packages found zero unreviewed advisories with three
existing applicability notes. This closes synthetic backup rehearsal; target-host
isolation/native artifact policy and production composition remain open. No Edge
deployment or household state change.

## Native worker, artifact policy and startup implementation — 2026-11-19

Implemented the previously missing development paths:

- Process-backed native provisioning and signing, with Linux Landlock ABI>=3,
  libseccomp, minimal environment, private bounded IPC, muted native logs,
  resource limits, immediate cancellation/termination and process reaping.
- Immutable release-owned artifact policy and deterministic bundle recipe. Public
  vendor APK source/version/member/bundle hashes are recorded. Official Android
  apksigner verifies its v2 signature and its signer matches Apple's published
  association. No native artifact is committed or redistributed.
- Explicit shared production startup/image and Edge-only repository rendering.
  Both account UUIDs, serial, client identity and encrypted native state survive
  reauthentication. Native provisioning headers and SDK identity agree. Reporting
  always rechecks fixed artifact policy and requires the process signer in shared
  mode, with no legacy/provider fallback. Unsupported security boundaries report
  setup-required rather than asking for another account password.

Validation: 212 app cases pass under UID1000, read-only root, no capabilities and
network disabled; 877 backend and 14 candidate integration cases pass in the
non-root offline candidate runtime. All 31 locked Python packages (including the
shared dependency) have zero unreviewed OSV advisories and three prior applicability
notes. The actual shared image builds and its production boundary smoke passes.
The public hash-verified vendor bundle initializes inside that restricted image
with matching configured identity headers; no Apple login/provisioning request,
OTP authentication or household state is used by that compatibility probe.

The artifact manifest deliberately remains pending for native-use/distribution
review. Dragon validation is not a claim of Home Assistant target-kernel support.
Before activation: resolve the artifact-use policy, verify the actual HA target
boundary, create a private recovery point, and perform a deliberate protected-UI
live sign-in/poll/restart comparison. No Edge publication, update, migration or
Home Assistant restart performed. See ARTIFACT_PROVENANCE.md, SHARED_RUNTIME.md
and CONTROLLED_PROVISIONING.md for evidence, runnable paths and exact limits.


## Home Assistant host compatibility and private evaluation — 2026-11-20

The actual HAOS host reports Landlock unavailable (ENOSYS38). The worker now
supports an independently enforced AppArmor child profile plus the same seccomp
restrictions; no protection disabling, OS change or additional app capabilities.
Diagnostic app 0.1.4 passed all ten restrictions as UID1000, with Supervisor
protection enabled. A production-equivalent trusted parent profile was necessary
for Python child startup; the restricted native child permissions stayed fixed.

The source-bound artifact policy has an explicit private-evaluation scope, not
native-use/legal clearance or redistribution permission. No vendor binary enters
Git or an app image. Explicit setup can privately acquire the exact vendor APK,
verify source/member/bundle hashes, and publish the component atomically. Missing
or unsupported boundaries stop startup before download or sign-in.

A separate Shared Edge app render keeps the existing Edge app/data untouched.
Account authentication and trusted-device unlock still require the protected UI;
no main password/session extraction from the existing setup is performed.


## Side-by-side deployment verified — 2026-11-20

Deployed `9c579022_retrace_shared` as **Retrace Shared Edge**
`0.1.13-dev.1.3`, source `3a88835429bf86656b3ca9857853ffc1f28962c2`,
Edge delivery commit `b83140c`. Supervisor reports started, protection enabled and
custom AppArmor profile loaded. Its credential-free `/health` returns HTTP200
with exactly `{"status":"ready"}`. Listener startup follows native-boundary and
component verification. Setup uses explicit private evaluation and fixed-component
installation, with first-identity creation authorized; Apple account sign-in and
trusted-device unlock remain protected-UI actions.

The original `9c579022_retrace` remains started at `0.1.12-dev.16.1`, unchanged.
Separate app data/identity provide the comparison/rollback path; no existing app
was stopped, migrated, backed up destructively or restored. Diagnostic0.1.4 is
installed, stopped and manual-boot after all ten target restrictions passed.
No Core restart or household Apple credential/session extraction occurred.

The first Shared Edge build stopped with `runtime_options_invalid` before setup.
The launcher now validates Supervisor options before dropping root and publishes
an owner-only app snapshot for the unprivileged web process. The final app passes
247 isolated non-root tests. CI44646322640 passed all three jobs for deployed
source3a88835, including real pinned SDK composition and shared-image boundary
smoke. Live discovery and location refresh still require the user's UI sign-in;
readiness is not a claim of successful Apple authentication or sightings.

## SMS and mobile setup repair — 2026-11-20

The live app's old logs could not explain an earlier SMS attempt: they recorded
poll counts, with no authentication stages. Inspection found a concrete local
SMS defect: the pinned SDK requests a challenge with PUT on the exact Apple
`/auth/verify/phone` route, while owned transport allowed only GET/POST. That
specific method/route is now permitted; other PUT destinations remain denied.
A real candidate integration case covers challenge PUT and submission POST,
including preservation of a code's leading zero. Known factor HTTP refusal now
carries only a fixed stage/status/code, without body or verification inputs.
The UI does not claim every refusal means an incorrect code. Explicit human retry
can reuse an SDK challenge still requiring 2FA; there is no automatic resend or
code replay. Ambiguous submission outcomes clear pending credentials.

Shared mobile setup combines account and discovery into one article, places
consent before Connect, explains encrypted-item recovery, and reports progress,
errors and success beside each CTA. Factor controls survive background snapshots;
reload reconstructs the method from server state rather than submitting null.
Legacy layout remains intact. Browser coverage checks CTA-local feedback,
consent validation without clearing a password, method/code retention and mobile
save feedback.

A second live issue appeared before report requests: report children lost both
the shared SDK path and checked runtime flags during environment sanitization.
They now use an isolated Python entrypoint with fixed SDK/app paths and reconstruct
mode/evaluation from the validated private options snapshot. No account token,
Supervisor token or arbitrary PYTHONPATH is passed through environment/argv.
The production-image smoke exercises the exact child startup without accounts.
Redacted query diagnostics distinguish local session restoration from report
fetch; redacted authentication events distinguish login, factor request/submit,
session saving and discovery handoff. No emails, phone numbers, codes, passcodes,
item IDs, coordinates, bodies or SDK exception prose are included.

Validation before delivery: 268 app cases, 877 backend cases, 15 real candidate
integration cases and 21 browser DOM cases (inside the app UI test) pass; shared
image and its exact isolated report-child smoke pass. No household credentials
were replayed or inspected during debugging. Old logs do not prove which failure
a particular past SMS attempt reached; a fresh user-driven retry remains live
verification of the repaired SMS path.


Deployment verified for SMS/mobile repair: Shared Edge0.1.13-dev.1.4, source
374bcb1c8914fc8dbd1b7a5b36acb0f3986a6fc5, Edge delivery01576bb. Supervisor
reports started/protected/custom AppArmor and readinessHTTP200. CI44716845173
passed all three jobs. Setup-only component installation/identity-creation flags
were disabled after successful initial setup; existing signing state/component
remain reused. The original Edge0.1.12-dev.16.1 stays started unchanged.

Live post-update poll completed all three selected items with zero errors:
two have saved sightings; the third returned no reports and continues bounded
resumable searching. Saved-session restoration worked after app update/restart
without another sign-in, and the prior local loading/auth failure is resolved.
No names, positions, account identifiers or private configuration were inspected
or recorded. A fresh user-driven SMS attempt remains needed to confirm the live
factor flow; the tested fix is not a claim that an old submitted code was wrong.
