# Candidate macOS signer: source-only review

Reviewed 2026-11-21. Not installed, executed, or approved for runtime use.

## Evidence and pins

- OpenTagViewer wrapper: commit `05b5d7cb26c9a48925f5fa580f063da4c1bed3b0`,
  `python/exporter/macadi.py` and `python/pyproject.toml`.
- Engine: `parawanderer/os-findmy-e` commit
  `595d39810639d750715babc30b063d4ac8f2c437`,
  `tools/machoadi/mac_anisette.py`, its pyproject and repository license.
- Engine metadata declares GPL-2.0-only and depends on Unicorn and FindMy.
  Process separation alone does not settle distribution obligations. Review
  applicable source, notices and licensing before packaging; no upstream code
  has been incorporated into Retrace by this review.
- Wrapper pins the Apple CoreADI payload/library hashes. This is integrity
  evidence, not redistribution permission or evidence of successful sign-in.
  No Apple binary was downloaded during this review.
- Upstream's wrapper commit explicitly leaves real sign-in unverified.

Primary sources:
[wrapper commit](https://github.com/parawanderer/OpenTagViewer/commit/05b5d7cb26c9a48925f5fa580f063da4c1bed3b0),
[engine source](https://github.com/parawanderer/os-findmy-e/blob/595d39810639d750715babc30b063d4ac8f2c437/tools/machoadi/mac_anisette.py),
[engine metadata](https://github.com/parawanderer/os-findmy-e/blob/595d39810639d750715babc30b063d4ac8f2c437/tools/machoadi/pyproject.toml).

## Integration gaps observed directly in source

1. The wrapper's `EmulatedMac.open` downloads/verifies the library and implicitly
   provisions if no provisioned machine exists. Retrace requires explicit
   provisioning consent and fail-closed restoration, so it cannot call this
   unchanged at startup or during session restoration.
2. The engine's provisioning method calls its GSA transport directly. Retrace
   must broker the typed provisioning exchanges through its owned asynchronous
   transport; the native worker must remain unable to access the network.
3. The engine reads/writes machine state and identity files; OTP generation also
   saves state. Retrace must keep these behind its private atomic storage and
   narrow IPC boundary, without granting access to account secrets or host files.
4. The Mac provisioning device identifier is not a UUID; a separate host UUID is
   also present. Current Retrace account and signing stores validate UUID device
   identifiers. Introduce an explicit versioned backend/identity model; never
   reinterpret the saved Android identity as a Mac or overwrite it implicitly.
5. The wrapper uses blocking `subprocess.run`, inherits the parent environment,
   captures stdout/stderr and exposes a stderr line in errors. Retrace needs
   bounded asynchronous process ownership, minimal environment, cancellation and
   reaping, framed bounded output, and allowlisted error codes instead.
6. The candidate has runtime/emulator lifecycle constraints and mutable OTP
   state. Verify serialized signing, timeout recovery and cache expiration;
   neither concurrent state access nor replaying provisioning is acceptable.

## Work required before a live candidate

- Define backend-neutral typed identity/signing/provisioning IPC and synthetic
  fixtures. Test both existing UUID identity compatibility and the Mac identifier
  format, corrupt/partial state, and no implicit conversion or provisioning.
- Review the engine's transitive source, emulator dependencies, native artifact
  acquisition and license obligations. Pin reviewed source and dependency hashes.
- Adapt native calls behind the existing networkless worker policy; keep network
  exchange in the parent owned transport. Verify isolation and cancellation on
  Home Assistant OS as well as the development host.
- Test atomic state updates, interrupted writes, worker crashes, malformed output,
  output limits, secret-free diagnostics, and concurrent header requests using
  synthetic data before any household authentication.
- Offer a deliberate candidate identity transition with clear consequences and
  preservation of the existing identity/session. A successful real sign-in,
  restoration, recovery and polling cycle is required before claiming a fix.

Do not deploy the upstream CLI unchanged, add a remote signing service, weaken
worker isolation, or retry household authentication automatically. Existing Edge
and stable release gates remain in force.


## Feature-flag staging

`experimental_macos_signer` is a strictly boolean internal runtime option,
defaulting to false for both absent settings and existing installations. Current
implementation is a fail-closed gate only: true returns
`macos_signer_not_available` before artifact access or private-store operations.
It is deliberately not exposed in the Supervisor schema yet. It does not claim
that the Mac adapter exists or is deployable. Existing Android paths and identity
formats remain unchanged. When the adapter is ready, it must use distinct state
and explicit provisioning; never convert or replace the existing Android store.

## Provider selection and memory adapter staging

Setup now names the current Apple Music provider and the unavailable experimental
macOS provider. The protected management snapshot publishes only fixed provider
labels/availability; the selector is locked during authentication. Existing clients
omitting a provider retain the Apple Music path. Unknown providers are rejected;
macOS selection is rejected before the account factory is called. No fallback,
identity conversion or session replacement occurs. This is not a working Mac login
and has not been deployed as one.

The project-owned experimental `experiments/macos-signer/adapter.py` accepts an
injected CoreADI interface and keeps the virtual store in memory. It separates
explicit begin/finish provisioning from restoration and signing; it neither
imports the upstream CLI nor accesses disk or HTTP. Failed native operations close
the adapter phase so the operation cannot be replayed. Synthetic tests exercise
provision/restore/sign, invalid snapshot paths and failure/no-replay. The emulator
and Apple binary have not been executed by these tests.

Remaining before household testing: construct the pinned CoreADI engine from
verified bytes inside the restricted child, connect asynchronous framed IPC and
owned provisioning transport, review upstream licensing/transitive source, add
provider-specific encrypted state/session restoration (including Mac device ID
and separate CloudKit UUID), acquire the reviewed private artifact with explicit
consent, and run native/isolation tests on HA OS. Only then enable the macOS option.
Do not wire the UI option to the existing Android factory as a substitute.


## Integrated Edge candidate — 2026-11-21

The default-off Supervisor option `experimental_macos_signer` now makes a second
provider available in the protected Setup UI. The original Apple Music path and
storage remain intact. Unknown/unavailable provider choices are rejected before
account creation; there is no automatic fallback. Both use the same Apple account
and factor UI. Main-account authentication/discovery stays user initiated.

The Mac engine is GPL-2.0-only source, pinned and shipped with its complete license
and source; see THIRD_PARTY_NOTICES.md. Only its offline emulator/dispatcher files
are imported, inside the existing restricted process after isolation succeeds.
The CLI, network client and state manager are excluded. Library bytes are fetched
from one fixed Apple HTTPS range, bounded/extracted/hash-verified privately; they
never enter Git/images. The new transport profile cannot carry auth credentials.

State is separate in `providers/macos`: encrypted machine generations, encrypted
password/PET-free account generations and private library. A cross-process lock
serializes signing/state publication. Cold native workers are reaped after each
uncached signing window. Header state is saved before headers return. A separate
host UUID is used for CloudKit while GrandSlam retains the provisioned Mac device
ID. Mac sessions are restored through the owned transport and explicit signer;
there is no SDK deserializer or Android-state migration.

`active-provider.json` changes only after the new account session is durable.
Failed authentication/session save leaves the previous provider selected. Polling
uses this pointer and never falls back when selected session data is corrupt.
Existing item keys/history and entities are shared; this is a provider choice,
not another set of tracker entities. Returning to Apple Music uses its preserved
identity and a new explicit login; it does not erase the Mac provider's state.

Actual pinned CoreADI initialization passed in the network-disabled restricted
worker. A synthetic adapter bug incorrectly rejected a positive initialization
return; the pinned engine defines nonnegative status as success. Fixed and covered
by regression. Actual anonymous Apple provisioning/signing was blocked by automatic
approval review pending the owner's explicit authorization for Apple-side machine
registration. No account authentication or existing identity reset was performed.

Encrypted machine generations are currently retained (as are account generations).
This avoids deleting files a concurrent restoring process may still read; bounded
garbage collection remains a follow-up before stable release. Host/root or complete
backup compromise is not prevented by keys stored beside ciphertext.


### Live anonymous validation completed

Owner explicitly authorized anonymous provisioning as needed after the initial
approval restriction. The first anonymous exchange reached final native
provisioning but snapshot validation rejected a virtual metadata filename. The
store schema now admits bounded, safe virtual basenames and empty lock/metadata
files, with traversal rejected and aggregate/entry size limits retained. These
names never become host paths. Added synthetic metadata/empty-lock roundtrip.
The next live smoke passed anonymous provisioning plus three cold native signing
and encrypted-machine restoration cycles. Disposable test state was removed;
no account login, 2FA, household session access or item queries were performed.


### Edge0.1.14-dev.1.6 deployed and ready for owner account test

Source8dcf198, delivery45c5668. Validation:300 app tests (including provider UI,
strict artifact transport, independent encrypted state and cross-process signing),
877 pinned SDK cases,17 controller cases and16 discovery/Mac protocol cases passed.
Shared image build and native-boundary/report-child smoke passed. After owner
approval, anonymous provisioning and three cold signing/restoration cycles passed.

Home Assistant MCP verified version0.1.14-dev.1.6 started/protected with custom
AppArmor, experimental_macos_signer true, and readinessHTTP200. Startup emitted
both provider availability booleans true. Original saved identity comparison was
consistent (all three checks true). Enabling the provider acquires/verifies only
the private library; household account sign-in and first machine provisioning
remain owner initiated through protected Setup. No account credentials supplied
through tools, original identity reset, item/history deletion or Core restart.

Owner test: reload Retrace Edge, open Setup, choose Reconnect Apple account if
shown, select macOS provider (experimental), then connect and complete Apple's
verification/recovery steps. A new-provider session becomes active for polling
only after successful durable save. Real-account acceptance and item reporting
with this provider remain unverified until that test; this is not a stable release.


### Owner account validation: macOS succeeds, Apple Music refused

Owner reported experimental macOS authentication succeeded while Apple Music did
not. Read-only HA logs independently confirm Apple Music init refusal -22410,
then a macOS login start followed by completed login, trusted-device factor
request/submission, durable session save and discovery handoff. The Mac session
save path selects macOS for polling; no later provider login appears in the
retained auth sequence. This supports a provider-specific acceptance difference
for this installation, not a wrong password or a universal diagnosis of Apple's
policy. No additional login, provisioning, restart or configuration change was
performed during this check.

Latest retained poll summaries:12 selected/completed,0 failed,7 reports received,
8 items with saved locations, status searching and no error code. Saved location
count includes earlier sightings; it does not mean all eight were newly located
in this poll or that every item reports continuously. Account authentication,
session persistence and discovery handoff are verified; unattended longevity and
later restart restoration still need observation. Keep macOS selected for now;
retain the Apple Music path without repeated login attempts.
