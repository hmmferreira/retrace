# Owned credential transport — 2026-11-19

Status: tested on `feat/shared-session-discovery`; not enabled on Edge and not
connected to the household's Apple account. No live credentials or exports were
used for this work.

## What the app now controls

`apple_transport.py` owns HTTPS requests, response parsing, destination validation,
TLS configuration and DNS resolution for the clients assembled by
`owned_protocol.py`. The prototype no longer uses the candidate's default
CloudKit/escrow client construction. Construction replaces unused SDK HTTP
objects before network access and closes all new clients on failure/cancellation.
Main account construction has the same transport installed before sign-in.
Discovery refuses accounts with an unprotected account HTTP transport.

| Purpose | Allowed destinations and operations |
| --- | --- |
| Machine provisioning | Exact gsa.apple.com lookup GET and MidService start/finish POST routes |
| Account authentication | Explicit GSA/GSAS authentication paths and setup.icloud.com loginDelegates |
| Location reports | Explicit gateway.icloud.com Find My report paths |
| CloudKit reads | Explicit gateway.icloud.com init/database read/code-invoke paths; init allows only the Find My or Keychain container query |
| Keychain recovery | Numbered Apple escrowproxy hosts; only get_records, get_club_cert, srp_init and recover |
| Cuttlefish functions | Only fetchViableBottles, fetchChanges and fetchRecoverableTLKShares through the owned client |

No suffix-wide apple.com/icloud.com permission is granted. Server-provided gateway
URLs are checked before their tokens are used. Unknown destinations, userinfo,
nonstandard ports, encoded/ambiguous URLs, fragments, arbitrary query parameters,
record saves and escrow enroll/delete paths fail closed. Regional/changed Apple
endpoints require an explicit compatibility review rather than a wildcard.

Redirects are disabled and rejected, including same-origin redirects. Environment
proxies and cookies are disabled, and callers cannot override Host, proxy or TLS
settings. No automatic HTTP retry is made, especially for device-passcode calls.
Timeouts and decoded response sizes are bounded. Error codes/repr do not contain
URLs, credentials, headers or response bodies.

TLS verifies hostnames and certificates with a pinned-package certifi trust store,
plus Apple's public root. SSL_CERT_FILE/SSL_CERT_DIR cannot replace that store.
The public root is bundled, never fetched during authentication, and its DER
SHA-256 is checked before use:
`b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024`.
Source: https://www.apple.com/appleca/AppleIncRootCertificate.cer . This is a public
certificate, not a private key or account credential. Leaf certificates are not
pinned, so normal Apple certificate rotation does not require a code change.
DNS answers are checked for global addresses, including mixed public/private
responses, and the connector uses those answers without a separate app lookup.

## What this does not prove

A Python object wrapper is **not an isolation boundary against malicious Python
running in the same process**. Such code could read process memory or open a
separate socket instead of calling this transport. Pinned source/hashes and review
reduce supply-chain drift; they are not a proof that the initial dependency is
benign. The native worker has the explicit OS restrictions described below, but
account/CloudKit Python orchestration remains in its parent process. Do not
describe these URL checks as a general-purpose parent process sandbox or claim
all dependencies are audited.

Anisette remains a separate boundary. Source inspection of anisette 1.2.4 found:

- its default library URL is a third-party download host; the SDK can reach it
  when a local library file is absent;
- provisioning uses a separate urllib3 client and server-provided Apple URL bag;
- the bundled alternative helper downloads its native libraries from Apple's
  app CDN, using its own networking implementation.

The shared runtime bypasses those default paths: local bytes must pass the
reviewed artifact policy; native signing/provisioning runs in a no-network worker;
and provisioning HTTP is owned by the parent. This does not establish that the
previous defaults leaked passwords: artifact fetches and machine provisioning
use different data. The working Rust/helper baseline is separate and remains
unchanged. Native artifact review/approval and distribution rights still gate
activation. No household provisioning or Apple account operation was run here.

Likewise, POST is used for both reads and writes in Apple's protocol. The owned
client restricts named operations and write paths, but this is not a complete
wire-level verification of every protobuf payload from a malicious dependency.

## Verification

The original owned-transport baseline passed 120 app cases, including 17
transport/DNS/TLS cases. Subsequent shared-runtime and worker tests extend it. Negative URL cases additionally cover deceptive domains, Unicode/userinfo,
encoded hosts/paths, local IPs, query injection and destination/profile mismatch.
Two real local HTTPS tests show that a 307 does not forward the synthetic body or
authentication, and that a server with an untrusted certificate receives no
credential-bearing HTTP. Local DNS/TLS overrides exist only inside fixtures;
production DNS rejection is independently tested.

The pinned candidate's 877 offline tests pass. Seven app/candidate integration tests
cover actual decryption, owned HTTP installation before authentication, constrained
client construction, disallowed operations, server-provided third-party gateway
rejection using real SDK request construction, and cancellation cleanup. Fifteen
controller cases pass, including refusal to request a token for an unprotected
account. No real Apple endpoint or production data is used by these tests.

References for the transport design:
- https://docs.aiohttp.org/en/stable/client_reference.html
- https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

## Offline signing increment — 2026-11-19

The experimental account factory now requires an initialized app-owned offline
signer. Its adapter loads a local regular-file artifact only after an explicitly
supplied SHA-256 matches, requires existing provisioning state, and replaces the
library's implicit download and provisioning fallbacks with failures. OTP work
is serialized; only the two required signing fields are returned. The original
thread-backed adapter remains a test implementation; shared startup/restore
selects ProcessOfflineSigner with a restricted child. Private state serialization is explicit, with no automatic file
write, and the legacy provider restore entry point is refused.

Nine synthetic signer tests cover artifact tampering/missing files/symlinks,
unprovisioned identities, lost provisioning, redacted failures, closure, worker
thread execution and disabled high-level download fallback. Candidate integration
also exercises the owned provider and rejects a default SDK provider before
account creation. All tests run without network or household credentials.

Shared restoration, UI handoff, private inventory storage and the restricted
native execution paths are implemented elsewhere in this branch. Runtime
activation still requires approved artifact policy, target compatibility and live
verification. An explicitly supplied digest must come from a reviewed release
manifest, not an arbitrary untrusted download. No zeroization is claimed.

### Offline signer lifecycle review

Cancellation of initialization/signing and explicit close now immediately revoke
the signer without waiting for its native thread lock. Late initialization cannot
produce a usable signer and late OTP results are rejected before delivery.
Synthetic event-controlled tests cover each case. Close drops app references;
it does not kill a native call or promise destruction/zeroization. The process-backed implementation below is selected for shared runtime. An
approved artifact manifest and target verification remain activation requirements;
see CONTROLLED_PROVISIONING.md for the concrete boundary and remaining gates.


### Restricted native worker implementation

The native execution boundary is now implemented by native_sandbox.py,
native_worker_child.py and native_worker.py. Production shared-runtime callers
can use IsolatedNativeWorker and ProcessOfflineSigner rather than native threads.
Linux LandlockABI>=3, or an explicitly loaded and verified enforced AppArmor
child profile on HAOS, limits reads to public code/runtime files and denies private
filesystem contents/writes; libseccomp denies sockets, child execution, tracing,
parent memory/signalling and boundary changes. No privileges are added. Startup
fails closed when required controls are unavailable, before third-party/native
execution. Native logs are discarded and bounded private IPC is separate.
Cancellation/error cleanup terminates and reaps workers; process signing refreshes
a validated cached private snapshot for nonblocking serialization.

Artifact provenance/release approval,
real native compatibility and HA target/live verification remain open gates;
synthetic boundary success does not approve an artifact. Full implemented policy,
test scope and operational limits are in CONTROLLED_PROVISIONING.md.


For the HAOS AppArmor backend, an app-owned nested profile is loaded by Supervisor,
not by the worker. The worker verifies a permanent enforced transition before
no-new-privileges, syscall restrictions or native loading. It has no permission to
transition back. Startup preflight validates and reaps a fresh restricted child
before artifact installation/UI listening. Parent file permissions do not inherit
into the child profile. Diagnostic stderr classification applies only to the
credential-free synthetic probe; production native stdout/stderr remain discarded.

Actual HAOS target verification on 2026-11-20 passed: diagnostic app0.1.4 ran
protected as UID1000, with all ten synthetic checks denied by the enforced
AppArmor/seccomp child. Landlock was unavailable (ENOSYS38), so the validated
boundary was `apparmor-seccomp-v1`. Only the trusted diagnostic parent required
ordinary container file permissions; native child permissions stayed restricted
and match the shared-runtime template. No Apple account or native artifact was
used by the target probe. See CONTROLLED_PROVISIONING.md for the exact scope.
