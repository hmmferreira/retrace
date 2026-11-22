# Release readiness and stable operation

Current assessment after the owner macOS provider test, 2026-11-21. Historical
reviews describe earlier stages; use this checklist with MAC_SIGNER_REVIEW.md.
There is no approved shared-runtime stable release yet. The workflow and renderer
intentionally reject that promotion until these gates are satisfied.

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

## Remaining gates for the first release

1. **Security, provenance and licensing of the actual shared runtime.** Resolve
   the Apple native-component permission question; complete the protocol/emulator
   and transitive notices/source inventory and fix material security findings.
   The legacy Rust exporter is absent from this runtime and is not its gate.
   Separate local binary acquisition is not itself public-release permission.
   See reviews/NATIVE_LICENSE_REVIEW_2026-11-22.md for concrete findings.
2. **Stable packaging and publication.** Prepare a versioned source-build shared
   runtime and a matching released companion integration, with immutable base/
   source/version references and deliberate stable updates. Keep the existing
   stable publication gate closed while item1 is unresolved; a review archive is
   not an approved installer. Never enable private evaluation by default to
   disguise clearance of the Apple component.
3. **Channel separation.** Verify Stable and Edge repository URLs give distinct
   app/data/instance IDs and entity IDs. Stable setup is a new protected login and
   item selection. Edge entities/history remain Edge. There is no migration or
   promise of history continuity between channels.

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
