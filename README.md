# Retrace

<img src="retrace/icon.png" alt="Retrace icon" width="96" height="96">

Location history for your belongings in Home Assistant. **Currently supports
Apple Find My items and devices**, with guided account setup, latest reported
locations and timestamped sightings recorded through Home Assistant. Other
tracking sources are a future direction, not currently implemented.

Retrace is an independent community project, not affiliated with or endorsed by
Apple. It runs independently of an existing MQTT tracker. Development remains
experimental; sparse sightings are not continuous GPS tracking.

This version uses a new Retrace integration and app identity. See the
[clean-install procedure](docs/BRANDING.md) before replacing an older installation.

## User journey
1. Open the app through Home Assistant ingress.
2. Connect the polling account and choose SMS or trusted-device 2FA.
3. Discover items through guided key recovery. Accept the Keychain trust
   explanation, authenticate, choose a trusted device, and enter its unlock passcode.
4. Select items with checkboxes. New items start disabled; rediscovery keeps choices.
5. Approve the discovered native integration. It creates separate channel-specific devices,
   GPS trackers and last-sighting sensors. HA zones and Recorder handle history.
6. Open Items for the overview and optional map preview. Add items later in Setup.

The legacy runtime uses separate polling and recovery sessions. Shared Edge
reuses the main account with a separate trusted-device unlock for key recovery.
No Mac needs to stay running. Shared Edge still relies on third-party protocol
code and native components: see [ownership and trust boundaries](docs/DEPENDENCY_BOUNDARY.md).

## Status and limits
This is development source, not a published or security-audited release.
Transport/recovery tests use synthetic credentials without Apple network access.
Repository Edge has partial real-account validation on Home Assistant OS;
this does not complete the release/security checklist. Only amd64 is targeted.
Minimum tested Core is 2026.9.3, with Supervisor 2026.11.0+ required for trusted
administrator group headers. Home Assistant Container without Supervisor is not
supported by this app installation path.
Battery status and street addresses are not available from this report source.
History follows the user's Recorder configuration; no retention period or backfill
is promised. Sparse sightings are not a continuous GPS track.

## Packaging
- retrace/: Supervisor app, ingress UI, local helper, patched exporter,
  selected-item polling, owner-only runtime state.
- custom_components/retrace/: native integration, config/reauth flows,
  coordinator, trackers, timestamps, Repairs and sanitized diagnostics.
- tests/: isolated transport, security, recovery and polling tests.
- docs/SECURITY.md: trust boundaries, storage and remaining review.
- docs/RELEASE.md: install/compare checklist and community-release gates.

## Install and update through Home Assistant

Add the [Edge app repository](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhmmferreira%2Fretrace%23edge), then install **Retrace Edge**.
Updates appear in Settings → Apps. No terminal archive copying is needed.
The initial source build can take a while; subsequent builds reuse cached layers.

Edge delivery is explicit after tests on main; source pushes do not overwrite
the installed Shared Edge evaluation package. Stable is reserved for manually promoted,
validated releases at `https://github.com/hmmferreira/retrace#stable`.
Do not add stable until its first release has passed live validation.
Both channels remain experimental until the security/release checks are complete.

The native integration is separate from the app. HACS can install it as a custom
Integration repository; enable prerelease versions for Edge integration updates. Stable integration
releases are published only on explicit stable promotion.
See [channel delivery and migration](docs/CHANNELS.md).

## Usability update (0.1.3)

Setup explains location access versus item-key discovery. Discovery reuses its
saved session and accepts email/password together on first sign-in. Item choices
show exact save feedback, and each tracked item has an asynchronous refresh
button. Manual refresh uses a one-minute anti-spam guard and always respects
Apple's rate-limit pause. New Edge native entities have explicit Edge labels
and channel-marked IDs. The app map is an optional preview; use HA's native
map and tracker history for daily use. See [the implemented behavior and native
UI direction](docs/USABILITY.md).

Finish an active import before updating the app. Update the companion through
HACS and restart Core for the new native naming before confirming discovery.

## Identifying items

The chooser and item cards show secondary text with the original Apple name,
model name/code, pairing date and a short app ID. Existing cached items are
enriched during upgrade; no new sign-in or key rewrite is needed. Development
installations use Edge consistently. Existing registry IDs are retained.
See [known limitations and release readiness](docs/KNOWN_LIMITATIONS.md).

## Development
Build from the retrace directory using its Dockerfile. It compiles the pinned
exporter with the known protocol/session fixes and bundles the anisette helper
locally; no public anisette service is used. Leaflet 1.9.4 is vendored with license
and hashes; scripts do not load from a CDN. Maps fetch OpenStreetMap tiles.

The local Portainer helper runs python tools/docker-check.py test or build.
Set PORTAINER_DOCKER_API and PORTAINER_KEY_FILE for another environment.
It is developer tooling, not part of the app. Tests have no network or live
runtime mounts. Do not copy production sessions into test fixtures.

## Attribution

FindMy.py retains **Copyright (c) 2023 FindMy.py Contributors** under MIT.
See [third-party notices](docs/THIRD_PARTY_NOTICES.md) for the complete license
and packaged notice locations; this does not clear other component release gates.

## Buy me a coffee

Enjoying Retrace? [Buy me a coffee](https://buymeacoffee.com/hmmferreira) to
optionally support its development and maintenance. Retrace remains free, with
all features available to everyone. Support goes to this project's maintainer;
upstream contributors retain their credits and licenses.


## License scope and release review

Retrace-authored code is MIT licensed. Retained macOS engine source is GPLv2;
Unicorn's native engine includes GPL/LGPL components, regardless of its Python
wheel's BSD classifier. Component notices and source provenance remain separate
under app/licenses and docs/THIRD_PARTY_NOTICES.md. The project license grants no
rights over Apple's native component. See
[the current release review](docs/reviews/NATIVE_LICENSE_REVIEW_2026-11-22.md).
A source review archive is not an approved Stable installer. Stable starts fresh;
Edge data/entities/history are never migrated into it.
