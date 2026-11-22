> Release0.2.0: the maintainer authorized source-only publication with unresolved
> Apple permission disclosed and local native acquisition consent required. See
> RELEASE.md and release/0.2.0.json. Earlier statements that publication itself is
> blocked describe the pre-decision review; they do not mean native rights are cleared.

# Dependency and ownership boundary

Source audit: 2026-11-20, development branch `feat/shared-session-discovery`.
This describes inspected code/build paths, not a new live security certification.

## What is independent today

Shared Edge replaces the legacy Rust extractor and separate Anisette server.
Its Dockerfile contains neither executable. App-owned code composes one main
account, its controlled transport, encrypted session restoration, discovery and
recovery UI, item selection and asynchronous reporting. Trusted-device unlock
is still a separate sensitive recovery operation, not a second account provider.

This is **ownership of integration and security controls, not ownership of the
entire Apple protocol implementation**. Rewriting a wrapper does not remove the
trust in code it imports.

| Layer | Current source / trust |
| --- | --- |
| Management UI, lifecycle, storage, transport and isolation | Project-maintained code under `retrace/rootfs/app/retrace/` |
| Shared account, CloudKit, Keychain and report protocol | Third-party `parawanderer/FindMy.py`, commit `8ecfae6cb34b29caf0bd8176ee73155ca81415a8`; archive SHA-256 `676e871098ec60a9c5e6718ea8cc18215631b036b99117a814ac1eb87d4e99e7`; MIT notice retained |
| Native offline signing/provisioning | Fixed Apple vendor components in private app data; policy/digest checked, isolated worker; explicit private evaluation, unresolved native-use rights |
| Python libraries | Shared image installs both `requirements.lock` and `requirements-shared.lock`; these still include FindMy 0.10.2 as well as cryptography, HTTP, emulation and other dependencies. Shared imports use the checked candidate source first; the installed legacy package has not been removed |
| Container and system libraries | Python/Debian base, TLS, AppArmor and seccomp packages; image tags/apt remain separate supply-chain inputs, not fully immutable builds |
| Legacy image / original Edge | Still uses findmy-export, rustpush and anisette-v3-server; do not apply Shared Edge independence claims to it |

The authoritative recipe is `retrace/Dockerfile.shared`. The default
`retrace/Dockerfile` remains legacy. `tools/render-evaluation.py` emits the
separate Shared Edge app; `tools/render-channel.py` rejects shared stable builds.
Historical documents about test-only candidates or pre-deployment evidence must
be read with newer dated deployment notes, not as current universal status.

## Credential visibility and limits

Project-owned transport constrains reviewed Apple destinations, methods, TLS,
DNS, redirects and response sizes. Account operations do not require a public
third-party authentication/signing relay in this path. Private component
acquisition, when explicitly enabled, is separate from account authentication.
See CREDENTIAL_BOUNDARY.md and ARTIFACT_PROVENANCE.md for exact controls.

Protocol Python executes in the parent process and can access account objects
and transient credentials. It is not isolated from secrets by our transport
wrapper. Pinning prevents unnoticed upstream revision drift; it does not prove
that pinned code is safe. Native worker isolation is a different OS boundary and
does not isolate the whole Python parent. Root, a compromised app image, or a
complete decrypted backup can expose stored secrets. No claim of complete audit,
clean-room provenance or prevention of all credential exposure is justified.

## Remaining work before stable

- Complete credential-path and transitive dependency review and notices inventory;
  remove redundant installed dependencies only with compatibility tests.
- Decide whether to maintain a reviewed minimal protocol fork or replace modules
  incrementally. Any copied code retains its original license and attribution;
  a fork improves change control but does not establish independent authorship.
- Resolve native-component use/distribution questions. Private evaluation does
  not clear an official release, even when binaries are downloaded locally.
- Complete the release/security checklist, live factor/recovery checks and
  supply-chain provenance work. Keep stable promotion blocked until resolved.

See also SHARED_RUNTIME.md, THIRD_PARTY_REVIEW.md, SECURITY_RECOVERY_REVIEW.md,
DEPENDENCIES.md and RELEASE.md. No upstream messages were sent for this audit.
