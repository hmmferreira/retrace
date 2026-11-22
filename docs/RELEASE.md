# Release readiness and stable operation

## Maintainer decision — 2026-11-22

The maintainer explicitly requested first official publication after the native
license findings were disclosed. Version0.2.0 is authorized by release/0.2.0.json
as source-build only, with unresolved Apple permission disclosed and explicit local
operational consent before native acquisition. This does not approve native rights,
waive terms or turn a checksum into legal clearance. Private evaluation stays off
by default. Apple binaries are not included in Git, app packages or public images.

## Verified for the current Edge candidate

- Edge0.1.14-dev.1.6 runs protected on Home Assistant OS with the native worker
  restricted by AppArmor/seccomp; the original provider/identity remains intact.
- Owner macOS login, trusted-device verification, encrypted session save and
  discovery handoff completed. Apple Music still returns init/-22410.
- Latest observed poll completed12 selected items with0 failures and7 reports;
  8 items have saved locations, including earlier sightings. This does not prove
  continuous location availability or all-device sightings.
- 300 app regressions,877 pinned SDK cases,17 controller cases and16 discovery/Mac
  adapter cases passed. Real anonymous provisioning and three cold native signing
  and machine-restoration cycles passed in disposable containers.
- Shared image build, worker isolation and report-child smoke passed. Apple
  binaries and private state stay outside Git and published image contexts.

## Owner's release scope — 2026-11-22

Stable starts fresh: separate app data, sessions, entities and history. Edge is
for development and may be discarded; its history must not be migrated to Stable.
No cross-channel credential, item-state or entity-history migration is planned.
Do not delete the current Edge installation as part of preparing a release.

Real-world reliability, long-running session behavior and additional recovery
scenarios will continue to be tested as the product is used. Extended soak testing
is not an open-ended first-release gate. Automated security/storage/isolation
regressions remain required, and incomplete scenarios must be described honestly.

## Versioned publication controls

1. App/native/hassfest checks and a fresh networkless stable-image smoke must pass.
2. The renderer requires a version-specific maintainer authorization record.
3. Immutable release tags select the shared stable runtime and require matching
   source/package versions and release notes. Existing stable versions are never
   overwritten. Publishing the source does not establish Apple permission.
4. Fresh Stable uses only macOS by default, keeps private evaluation disabled and
   cannot acquire/provision a native machine until the user consents in protected
   Setup. Edge data, keys, selections and history are never imported.

The earlier review record remains as evidence of unresolved legal questions,
not an up-to-date statement that the maintainer has withheld publication approval.
The owner elected to proceed with those limitations disclosed. Extended field
reliability/recovery remains post-release work, with no false completed-audit claim.

## Companion integration boundary

Both app instances currently use one `custom_components/retrace` package in Core.
Separate app volumes do not isolate integration code versions. For everyday use,
pin that package to a compatible released version and test Edge app API changes
against it. Testing incompatible Edge integration code needs a separate HA test
instance or a separately designed domain; installing prerelease integration code
in the same Core can affect stable app entities too.

## Release acceptance and limitations

A first0.x release may disclose sparse reports, missing battery/street address,
Recorder retention behavior, amd64-only support and unofficial Apple compatibility.
It must not claim unresolved native-use rights or unperformed recovery checks are
cleared. A successful login is necessary evidence, not a complete release audit.

App installation/update remains through the repository UI. Public prebuilt images
remain gated by their component/distribution review. See CHANNELS.md for channel
mechanics and MAC_SIGNER_REVIEW.md for source/build/live evidence. No new household
restart, authentication, backup or migration was performed for this assessment.
