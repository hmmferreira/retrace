# Security and recovery checkpoint — 2026-11-19

This review uses synthetic data only. It does not restore a Home Assistant backup,
change household sessions, or activate the shared-auth prototype in Edge.

## Verified

- 172 app cases pass in the isolated offline runtime, including private file
  permissions, expiry/tampering, cancellation, atomic-write failures, and UI flows.
- 877 pinned backend cases and 12 candidate integration cases pass. The recovery
  rehearsal encrypts a real SDK account with a synthetic native engine, copies
  the private app directory, deletes the original, restores the copy, preserves
  app/account identity and constructs a reporting request through owned HTTP.
- Missing backup keys and mixed key/ciphertext generations fail closed even if a
  legacy account file exists. Corrupt owned state does not trigger legacy login.
- A directory fsync failure after manifest replacement retains the newly published
  key/ciphertext pair, rather than breaking the visible generation.
- Every session component must be owner-only. Duplicate manifest keys and a
  symlink data root are rejected before account restoration.
- Public dependency advisory check: 30 locked Python versions checked against OSV;
  zero unreviewed findings, three existing documented applicability notes. This
  does not audit native binaries or establish candidate source provenance.

## Backup and recovery contract

Keep the entire app-private directory together: app identity, owned manifest,
referenced key/ciphertext generation, verified artifact, inventory/key records,
reports and search alignment. Treat the backup as credentials and location data.
The key is separate from ciphertext but on the same host; this does not defend
against host compromise. Missing keys require main-flow reauthentication. No
automatic deletion of legacy or unreferenced generations is performed.

The rehearsal uses private directory copies, not a Supervisor archive/target-host
restore. Target-host backup inclusion and kernel isolation need deployment-target
verification. No live native provisioning or real Apple server success is claimed.

## Edge decision

Do not promote the replacement authentication flow yet. Green tests close the
backup/restoration gap but do not supply missing implementation:

1. Provisioning has no isolated native worker. It deliberately stops with
   `isolated_provisioning_worker_required`. Signing is also currently thread-backed.
   Implement and verify the boundaries in CONTROLLED_PROVISIONING.md.
2. Native artifacts need a reviewed source/version/architecture/digest manifest
   and distribution/provenance evidence. A checksum alone does not establish trust.
3. Production main still selects the existing flow and the runtime lock still
   selects the existing SDK. Compose and package the reviewed candidate explicitly
   only after its dependency/license review and worker boundary are complete.
4. Before migration, create a private recovery point for the current Edge app and
   record its version. A code rollback alone cannot undo private data migration;
   retain a matching pre-migration data copy. Perform a protected-UI live comparison
   with deliberate sign-in, report refresh and restart verification.

No additional user-provided API key or manual file upload is needed for the
completed review. A future live sign-in/verification or device-unlock prompt must
stay in the protected UI, not chat or logs.


## Follow-up implementation

The development tasks listed in the Edge decision above have since been
implemented on the feature branch: restricted native worker, fixed source-bound
artifact policy, explicit shared runtime composition/image and Edge renderer.
See SHARED_AUTH_REWRITE.md's final implementation checkpoint for current counts.
The policy's approval remains pending, and actual target/live verification is
still required; the earlier section records the decision at that review point.
