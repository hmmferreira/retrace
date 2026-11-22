# Experimental owned session restoration

`owned_session.py` is an explicit opt-in API for the shared-auth feature branch.
It does not change existing Edge account files or migrate them automatically.

- `await snapshot_account(account, encryption_key=key, expires_at=epoch)` returns
  encrypted bytes. The supplied key must be 32 random bytes. The caller chooses
  the local expiry, no later than 30 days, and persists the envelope atomically in
  app-private storage. Main password, PET and heartbeat fields are excluded; only
  the logged-in polling/delegate state and offline provisioning are retained.
  Service data is limited to searchPartyToken (required), cloudKitToken and
  mmeAuthToken; unrelated service metadata and token scopes are excluded.
- `await restore_account(data, encryption_key=key, library=path,
  expected_sha256=reviewed_digest)` restores the same client IDs, serial and full
  device identity through the explicit candidate SDK constructor. It initializes
  the verified offline signer and installs owned account HTTP before returning a
  ReportingAccount, preserving app classification of empty-response failures.
  It never invokes the SDK provider deserializer, downloads, logs in or silently
  falls back to a different identity.
- Native serialization, JSON validation and envelope encryption/decryption run
  off the event loop. Account construction/resource cleanup remains async.

The format uses AES-256-GCM with a fresh random 96-bit nonce and a version-bound
associated-data prefix. Decryption/authentication precedes JSON interpretation.
The parser bounds input, refuses duplicate/nonfinite fields, validates required
identity and logged-in state, and rejects expired, tampered, truncated, unknown or
password-bearing snapshots. Local expiry is policy, not a claim that Apple has
accepted a token. A service rejection still needs an explicit main-flow
reauthentication prompt; restore itself deliberately performs no network call.

The caller must manage the private encryption key separately from the envelope,
retain it across restarts, and include it in an appropriate private backup. Key
loss requires a new login. A key beside the ciphertext does not protect against a
host compromise, and AEAD alone does not prevent replay of an older still-valid
snapshot. No key creation, backup integration, secure hardware storage, rollback
counter, process sandbox or memory zeroization is implemented by this module.
Never expose this data/key to public state, diagnostics, logs, Git or chat.

Tests use only synthetic identities/state and a fake native engine. App tests
exercise encryption, field minimization, restore composition, malformed/tampered
inputs, expiry, missing identity, cancellation cleanup and worker-thread behavior.
Candidate integration tests exercise its real constructor/serialization and
report requests: a valid zero-sighting response remains an empty result, a 401
requires reauthentication without a login retry, and empty responses retain the
app-specific unavailable classification. No household session is used as a fixture.

## Private storage and reporting composition

`PrivateSessionStore(root, library=reviewed_local_path,
expected_sha256=reviewed_digest).save(account)` generates an independent random
32-byte key for each encrypted generation. Key and ciphertext are separate 0600
files inside the private 0700 root. One atomic `owned-session.json` replacement
publishes the matching generation, library and digest. If staging fails, the
previous manifest remains usable. The trusted digest must originate from a
reviewed artifact policy; merely hashing an unknown executable is insufficient.

`restore_reporting_account(root)` selects owned restoration whenever the owned
manifest exists, including a broken symlink. It validates private bounded files
and never falls back to `account.json` on malformed, missing, expired or rejected
owned state. Legacy restore is used only when no owned manifest exists, preserving
existing installations. Poll children return `authentication_required` for blocked
owned restoration and never write shared session state. The restored class is
`ReportingAccount`, preserving empty-response classification and request pacing.
The real candidate SDK tests exercise identity/serial/ID roundtrip, actual report
request construction, zero sightings, 401 with no login/PET retry, and bounded
empty-response retry behavior.

Compose explicitly with `compose_shared_ui(store, account_factory=reviewed_factory,
session_writer=private_sessions.save,
session_available=lambda: session_available(store.root))`. Production main remains
unchanged pending provisioning/isolation/provenance gates. The availability check
only establishes local presence; reporting validates content and server rejection
requests reauthentication.

Backups must include the manifest, its referenced key/ciphertext, the verified
artifact and the existing app identity/inventory. Restoring only ciphertext cannot
recover the session. Old unreferenced generations and pre-existing legacy files
are retained rather than deleted automatically; retention/cleanup and backup
restore rehearsal remain release work. A cancelled off-thread filesystem commit
may finish atomically; cancellation is not a rollback or secure-erasure guarantee.
