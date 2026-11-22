# Security design and review boundary

## Runtime scope
This document includes legacy design notes. For the current Shared Edge dependency,
credential and release boundary, read [DEPENDENCY_BOUNDARY.md](DEPENDENCY_BOUNDARY.md)
and [SHARED_RUNTIME.md](SHARED_RUNTIME.md). Shared Edge has no Rust exporter or
separate Anisette server; its Python protocol dependencies remain trusted
same-process code. Shared stable promotion remains blocked.

## Isolation
The app runs web/polling processes as uid/gid 1000 after preparing its own private
/data/retrace directory. No Docker socket, host network, device access,
privileged mode, /config mount or Core administrator API token is requested.
The local helper is bundled in the app container, binds only loopback, and has no published port. Helper/exporter child environments do not inherit the Supervisor token.

Management accepts only the Supervisor ingress peer and a trusted nonempty user
header and the exact `system-admin` group. Missing groups fail closed.
Supervisor 2026.11.0 or newer is required. Mutations require a short-lived per-user CSRF token and JSON. The sidebar
panel is administrator-only. A separate listener offers authenticated read-only
snapshots to Core. Its bearer credential cannot access account management.

## Credentials and backups
The polling serializer is scrubbed of the Apple password before disk writes.
Passwords, verification codes and device passcodes are transient inputs. Pending
flows expire. Rust exporter sessions store tokens and stable device identity.
Its own escrow password is random, not hardcoded. User passcodes are not cached.
Directories are 700 and atomic state files 600.

Permissions are not encryption. Supervisor/root, compromised app code and anyone
able to decrypt a backup of app data can read these secrets. Protect backups.
We do not claim that a key beside encrypted files protects against root.
The integration pairing token is sensitive location-read access stored in HA's
normal config-entry mechanism, not an Apple password. The internal app/Core link
uses the trusted Supervisor network without additional TLS. No host port is
enabled. Exposing the API externally is unsupported.

## UI and logging
Relative ingress URLs, no credential query strings, no browser local/session
storage, no request/access logs, and generic error responses. PTY parsing exposes
only known prompts and recovery-device labels. Raw output, serials and upstream
exception bodies are withheld. textContent prevents item-name HTML injection.
Recovery inputs reject newlines/NUL; ownership prevents cross-user responses.
CSP/no-store headers are set. Map executable assets are local; OpenStreetMap sees
browser tile requests. No reverse geocoding is done.

Authentication logs use fixed substeps (account setup, Apple sign-in and method
listing). Typed Apple refusals can include only the fixed init/complete label and
a bounded integer error code. Unexpected/protocol/state failures can include a
fixed exception category and an allowlisted public source-component label/line
number. Raw tracebacks, local variables, exception messages, response bodies and
account identifiers are never rendered into these diagnostic events. This helps
identify a failure without replaying credentials or automatically retrying login.

## Release review still required
- Live non-admin browser validation remains outstanding. Supervisor 2026.11.0's
  [ingress handler](https://github.com/home-assistant/supervisor/blob/2026.11.0/supervisor/api/ingress.py)
  enforces panel_admin in its backend, filters client-supplied identity/group
  headers, then forwards authenticated groups. Its
  [user model](https://github.com/home-assistant/supervisor/blob/2026.11.0/supervisor/const.py)
  includes system-admin for owners. App tests independently reject missing or
  non-admin groups and forged administrator headers from an untrusted peer.
- Test real Apple factors, expiry, cancellation and token-only reauth.
- Replace human-prompt matching with a typed exporter protocol upstream.
- Audit transitive dependencies, binary provenance and license compatibility.
- Python runtime dependencies are pinned with committed wheel SHA-256 hashes;
  production/test builds and CI use pip hash-checking mode and reject source
  distributions. See [dependency updates](DEPENDENCIES.md). AppArmor testing,
  SBOM and signed images remain outstanding. Runtime Python OSV checks gate
  delivery, with exact expiring applicability notes for setuptools platform-only
  findings. aiohttp was patched to 3.14.5 after the first advisory scan.
- Browser tests of TLS ingress, CSRF, recovery ownership and redaction.
- Synthetic private-state restore and disk-write failure regression tests pass;
  live Supervisor backup/restore and key deletion/retention policy remain. See
  [backup/restore procedure](BACKUP_RESTORE.md).
- Pairing-token renewal is administrator/CSRF protected and revokes old snapshot
  access immediately. Replacement tokens are sent only through Supervisor
  discovery; companion 0.1.10+ verifies the same instance before updating and
  reloading the existing entry. No token is returned to the browser. Live
  rotation validation remains outstanding; do not rotate during an upgrade.
Focused automated tests do not replace an independent security review.
