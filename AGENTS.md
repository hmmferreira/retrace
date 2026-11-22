# Retrace contributor instructions

Read README.md, docs/DEPENDENCY_BOUNDARY.md, docs/SECURITY.md and the topic notes
before changes. Check origin and GitHub updates first; preserve dirty work and
never reconcile divergence or reset household state implicitly. This repository
contains legacy and Shared Edge implementations: identify the actual build and
runtime before making claims about dependencies or authentication.

## Ownership and credentials

- Shared Edge removes the Rust exporter and separate Anisette server, not all
  third-party code. Never call it dependency-free, clean-room or fully audited.
- Keep protocol source pinned by revision and archive hash, Python wheels pinned
  by version/hash, and upstream notices intact. Review source, transitive changes,
  advisories and licenses before updating. A matching hash is integrity evidence,
  not evidence of safety or redistribution permission. Preserve the complete
  FindMy.py notice in docs/THIRD_PARTY_NOTICES.md and rootfs/app/licenses; ensure
  rendered packages retain it and the shared image keeps upstream LICENSE.md.
- Route account operations through the owned transport. No remote signer,
  arbitrary endpoint, environment proxy, redirect, legacy-session fallback or
  unreviewed executable download. Preserve explicit native policy and isolation.
- Same-process Python dependencies can access credentials: transport wrappers are
  not a sandbox. Any new dependency on that path requires an explicit trust review.
- Never commit or expose credentials, tokens, session cookies, private keys,
  passcodes, account exports, item locations, vendor binaries or raw configuration.
  Use synthetic fixtures and allowlisted diagnostic fields. Keep authentication
  in protected ingress UI; no credential query strings or browser persistence.
- Keep runtime state private and atomic; encryption keys beside ciphertext do not
  protect against host/root or complete-backup compromise. Fail closed on corrupt
  identity/session state; require explicit reauthentication or provisioning.

## Implementation and validation

Use async network operations, bounded per-item concurrency, independent item
progress and cancellation. Respect rate limits and per-item cooldowns. Do not
replay authentication/passcode operations automatically or block the event loop.
Keep action feedback by its control and setup feedback in Setup; show durable
account/recovery/tracking/check status separately. Use accessible text, not color
alone, and verify mobile layout. Keep stable and Edge identities distinct. The owner explicitly chose a clean-break
rename: current app/domain/data/entity identifiers use retrace, with no legacy
aliases or automatic secret/history migration. See docs/BRANDING.md.

Run focused synthetic tests and the appropriate container regression suite
(`python3 tools/docker-check.py test --non-root`). Protocol, storage, native policy
or isolation changes also need their matching candidate/isolation tests. Never
use household secrets as fixtures. Report what was tested and what remains live
or manual validation; a passing synthetic suite is not a complete security audit.

## Release scope chosen by the owner (2026-11-22)

Stable starts with fresh state and its own entities/history. Edge entities stay
Edge, are disposable development data, and must never be migrated or renamed into
Stable entities. Do not delete the running Edge installation without an explicit
request. Extended real-world reliability/soak testing continues after the first
release; do not invent an open-ended soak requirement as a release gate. Existing
automated security checks and unresolved native licensing still apply. Prioritize
native/dependency security/license review, then source-build stable packaging.

## Delivery

Keep original Edge, Shared Edge and stable storage/identities distinct. Use the
repository renderers and normal fast-forward delivery; never edit generated
packages alone or force-push. The owner explicitly authorized the first official release after reviewing the
unresolved native licensing finding (2026-11-22). Version-specific release records
allow source-build Stable publication with that uncertainty disclosed. Never mark
Apple permission approved, ship Apple binaries, enable private evaluation by
default, or acquire the native component before explicit local operational consent.
Credential-boundary/security checks and immutable versioned publication remain
mandatory. The authorization is not legal clearance or permission from Apple.
Verify installed version, protection and readiness through HA after deployment;
an uncertain lifecycle result must be read back before retry. Preserve sessions and selected items within the current Retrace installation;
never import pre-rename sessions or identities implicitly. HTTP readiness does not
mean the lazily created signing identity exists. Keep explicit first-identity
creation enabled until the first successful sign-in/discovery has saved it; never
clear that setup flag merely because app startup or /health succeeded. Record verified results without private data.
Do not contact upstream maintainers without explicit user instructions.
