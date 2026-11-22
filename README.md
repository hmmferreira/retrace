# Retrace

<img src="retrace/icon.png" alt="Retrace icon" width="96" height="96">

Location history for your belongings in Home Assistant. **Supports Apple Find My
items and devices** with guided account setup, item selection, native trackers
and timestamped sightings. Other tracking sources are a future direction.

## Install Retrace 0.2.1

Add the [Stable app repository](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fhmmferreira%2Fretrace%23stable),
then install **Retrace** in Home Assistant Apps. The repository URL is
`https://github.com/hmmferreira/retrace#stable`. Home Assistant builds locally;
no public prebuilt image or Apple binary is supplied by this project.

Start the app, open its Web UI and follow Setup: review local native-component
consent, connect your Apple account, complete Apple verification and recover item
keys using a trusted device's unlock passcode if requested. Passwords, codes and
passcodes are transient. Select items, save, and approve the discovered integration.
No laptop or Mac needs to stay running.

The companion integration is a separate HACS/custom Integration repository,
`hmmferreira/retrace`, release `v0.2.1`. Updating its code may need a Core restart.
Existing compatible Retrace companion installations can discover the new app.
Read the [release notes](docs/releases/0.2.1.md) and [setup documentation](retrace/DOCS.stable.md).

## Stable and Edge

Stable starts with its own sessions, item selections, entities and history.
**Edge entities stay Edge and are disposable development data.** There is no
history/credential migration or automatic deletion of Edge.

For development add `https://github.com/hmmferreira/retrace#edge` and install
**Retrace Edge**. Stable is updated deliberately through versioned releases;
Edge remains separate. Both app instances use one companion integration package
in Core, so incompatible integration-code testing needs a separate HA test instance.

## Distribution and licensing

Retrace is independent of Apple. The release uses an unofficial macOS signing
provider. After explicit local consent, it downloads pinned CoreADI bytes directly
from Apple and runs them in a restricted worker. Apple's EA1510 terms apply;
permission for extracting/emulating that component on Linux has not been
established by this project. The maintainer authorized publication with that
uncertainty disclosed. Publication is not legal clearance, Apple endorsement,
or a grant of third-party rights. See the [licensing review](docs/reviews/NATIVE_LICENSE_REVIEW_2026-11-22.md).

Project-authored code is MIT licensed. FindMy.py retains Copyright (c) 2023
FindMy.py Contributors and its MIT notice. Retained Mac-engine source and Unicorn
native components have GPL/LGPL obligations; the project MIT license does not
replace them. Source pins, component notices, installed-package inventory and SBOM
are retained in the repository/image. See [third-party notices](docs/THIRD_PARTY_NOTICES.md).

## Supported scope and limits

amd64 Home Assistant OS/Supervised; minimum tested Core 2026.9.3 and Supervisor
2026.11.0+. HA Container without Supervisor is not supported by this app package.
Sparse reports are not continuous GPS. Manual refresh cannot force an AirTag to
report. Battery level, street address and historical backfill are unavailable.
Recorder controls history retention. Apple compatibility can change; longevity,
expiry and additional recovery scenarios remain ongoing field validation.

Encrypted tokens and item keys stay private, but root, compromised parent code or
a decrypted full backup can expose them. This is not an independently security-
audited product. Protect backups and do not expose the internal API publicly.
App cold backups pause tracking briefly for consistent state capture.

## Development

The supported source-build runtime uses `retrace/Dockerfile.shared`; channel
rendering selects it explicitly. Legacy Dockerfile/exporter code remains for
historical development, not the Stable runtime. Device requests use bounded async
workers; native execution is restricted and account HTTP destinations are controlled.
Never put household credentials, sessions, raw exports or locations into Git/tests.

Run `python3 tools/docker-check.py test --non-root` with the local Portainer helper,
then the relevant protocol/isolation checks. Release tags run app/native/hassfest
checks before publishing the Stable repository and matching GitHub release.
See [release policy](docs/RELEASE.md), [dependency boundary](docs/DEPENDENCY_BOUNDARY.md)
and [contributor instructions](AGENTS.md).

## Buy me a coffee

Enjoying Retrace? [Buy me a coffee](https://buymeacoffee.com/hmmferreira).
