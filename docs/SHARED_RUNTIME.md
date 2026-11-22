# Shared runtime startup (experimental)

This branch now contains executable startup composition, separate from the
existing Rust-backed image. It is not a production promotion and does not certify
Apple protocol compatibility, dependency provenance or native artifact licensing.
No existing household data or services are changed by building it.

## Explicit image and mode

Build the shared image intentionally from the app directory:

```sh
docker build -f retrace/Dockerfile.shared -t retrace:shared retrace
```

`Dockerfile.shared` fetches exactly protocol revision
`8ecfae6cb34b29caf0bd8176ee73155ca81415a8`, checks the SHA-256 of the deterministic
FindMy-source/license archive, and copies only that allowlisted archive. It adds
hash-locked protobuf and `libseccomp2`. Source is used through an explicit
image-local PYTHONPATH; the existing production Dockerfile and its SDK remain
unchanged. The shared image contains neither the Rust exporter nor the separate
Anisette server helper. The candidate's MIT notice is retained beside the source.

Set the app options explicitly (or `/data/options.json` for a standalone test):

```json
{"runtime_mode":"shared","shared_artifact_id":"applemusic-arm64-v8a","create_new_identity":false}
```

The default remains `legacy`. Shared mode refuses the legacy image, and the shared
image refuses legacy mode. Bootstrap drops root before any account operation,
starts only the web/worker process in shared mode, and fails visibly if startup
exits. `RETRACE_RUNTIME_MODE` comes from validated options rather than an inherited
environment override. Changing modes is not an automatic data migration; keep a
complete app backup. Legacy startup refuses an owned-session marker so it cannot
silently use an old plaintext account session after shared mode was selected.

## Reviewed artifact and first identity

Shared startup requires a release-approved bundled artifact policy and a matching
private `/data/retrace/owned-libs.bin`. It verifies the artifact before opening
listeners. Users cannot approve a binary by supplying its hash in the options or
a private session manifest. **Default selection refuses the private-evaluation entry with
`artifact_review_required`. Explicit private Edge evaluation selects the fixed
technically reviewed bytes without claiming native-use or redistribution rights.**
Documenting this executable path does not waive the review or invent an approved
Apple artifact/version/redistribution claim. It performs no runtime download.

After that release review, a fresh installation must explicitly set
`create_new_identity: true` for its first provisioning. Provisioning runs through
the owned Apple transport and `IsolatedNativeWorker`; the native worker requires
Landlock ABI 3 or a verified enforced AppArmor child profile, together with
libseccomp, and cannot use the network. The actual HA host passed all ten
synthetic restrictions using AppArmor; its kernel does not provide Landlock. It receives no
Apple account password. An unsupported host fails closed. A saved identity is
always reused even if that option remains true. Missing/corrupt saved identity
material or an existing owned-account marker prevents implicit regeneration.
Return the option to false after setup.

Provisioned machine state, the client serial, the full SDK device identity and
both account UUIDs are
saved in an AES-GCM-encrypted generation under `owned-signing.json`. Its separate
owner-only key and ciphertext are published through one atomic manifest change;
artifact-policy digest is authenticated with the ciphertext. A broken manifest,
key, permission or ciphertext fails closed. This identity is separate from account
token expiry, so main-account reauthentication can preserve the same signing
identity rather than provisioning another one. Native provisioning and main
authentication use the same UUID pair, client description and matching User-Agent. Encryption protects accidental
ciphertext disclosure; it does not protect against host or complete-backup access.

## Account, UI and reports

`server.main` now selects `compose_runtime` for shared mode. Its factory loads the
private signing identity or explicitly provisions the first one, creates a
`ProcessOfflineSigner`, and constructs an owned-transport account. The session
writer commits the encrypted account snapshot and refreshed machine state.
The shared UI bridge receives that same account before transient credentials are
cleared, obtains the discovery service token, then accepts a separate trusted-
device unlock. It atomically merges only recovered accessory records. Location
readiness checks only the owned manifest in shared mode. Poll children restore
the encrypted owned account through the same process signer and policy checks;
an owned restore error never falls back to a legacy serializer/provider.

No default SDK constructor or remote signing fallback is used by this startup
path. Native child isolation does not sandbox every Python protocol dependency
inside the main web process; that broader credential/codec boundary and explicit
live UI comparison remain release review items. Shared-mode startup, identity
storage and synthetic tests do not constitute successful live Apple verification.

## Repository installation packaging

Supervisor builds the file named `Dockerfile`. For an explicitly selected shared
Edge channel, render the repository with the shared runtime option:

```sh
python3 tools/render-channel.py edge 0.1.12-dev.1.1 /tmp/findmy-shared-edge --runtime shared
```

Use the intended new development version when releasing; the example does not
publish or deploy anything. The renderer selects `Dockerfile.shared` as the
installable `Dockerfile`, sets its default mode to shared, and records the runtime
in CHANNEL.json. Subsequent updates can follow the normal GitHub app repository
workflow. Existing installed options are retained by Supervisor, so an existing
installation still needs its mode changed deliberately after the matching image
is installed. Shared Stable rendering is refused; omitting the flag retains the
legacy image/defaults. Rendering does not enable private evaluation or component installation automatically.

## Optional private component placement

`install_reviewed_component` is false by default. When explicitly true, shared
startup can acquire the fixed Apple vendor APK directly inside the app rather
than requiring a manual file upload. `private_evaluation` is separately false by
default; it selects only the fixed technically reviewed personal-evaluation policy
when that policy is present. It does not assert redistribution clearance or make
a pending component a generally approved release. The checked option sets the
report-child evaluation flag; an inherited environment variable cannot enable it.

Startup first selects the immutable policy and probes the actual native process
boundary. An unsupported target fails before any component download or account
sign-in. The acquisition transport permits one exact HTTPS GET, uses the same
strict TLS/public-DNS checks, has no account credentials/cookies/environment proxy,
and refuses redirects and compression. Streaming is bounded at 200 MiB separately
from the unchanged 8 MiB account-response limit; no automatic retry occurs.

A temporary owner-only APK is hash-verified in full before ZIP parsing. Only the
two exact pinned arm64 ELF members are read; duplicates, oversized members, wrong
architecture or member digests fail. The deterministic bundle must match its own
release pin before it is published owner-only without overwriting an existing
file or symlink. The APK and temporary files are removed on success, error or
normal cancellation. Cancellation waits for an outstanding disk operation to
finish safely; if atomic publication has begun, the verified component can remain
installed. A power loss can leave an unreferenced temporary vendor file; neither
credentials nor account state enter these files.

Existing valid components are reused. An invalid existing component is never
silently replaced, and a changed vendor APK fails its old source pin rather than
executing or approving new bytes. The vendor component is excluded from Git,
images and public app archives; this option downloads locally at the user's
explicit request. Return installation/new-identity options to false after setup.


## Side-by-side private evaluation

`tools/render-evaluation.py VERSION OUTPUT` emits only `retrace_shared` with
slug `retrace_shared` and title **Retrace Shared Edge**. It leaves an
existing `retrace` app/version untouched and installs the shared AppArmor
profile as `apparmor.txt`. This is the evaluation/rollback path: separate app data,
identity and integration instance, with the original working Edge app retained.
All setup switches default off; deliberate deployment sets runtime mode shared,
private evaluation true, reviewed component installation true, and first-identity
creation true. The installation option only reuses an existing matching component
on later starts. First-identity creation never silently replaces stored identity.
Return setup-only switches to false after initial setup. Apple account credentials
and trusted-device passcodes belong only in the protected management UI.
