> Historical legacy/Edge observations follow. For the official0.2.0 macOS provider,
> current setup, scope and licensing disclosure, read releases/0.2.0.md.

# Release readiness and known limitations

Verified 2026-11-16 against the installed Edge app:

- Before bounded searching, repeated polls of five selected items produced three
  reports and two 120-second timeouts. Diagnostics showed 46–48 empty report
  batches per timed-out item. Bounded searches now revisit 580 recent key indices
  then at most 2,320 older indices, saving a private continuation checkpoint.
  Incomplete searches are marked explicitly. This reduces repeated work; it
  cannot guarantee Apple has a sighting. The first live bounded poll completed all five item queries without failures:
  three sightings and two continuing searches. These two items still have no
  saved sighting; receiving reports for them remains unverified.
- Manual refresh retrieves Apple's stored report; it cannot make an AirTag
  broadcast or make nearby Apple devices relay a new sighting.
- Location polling and item discovery have separate initial authorizations.
  Valid sessions are reused; expiry needs sign-in and discovery may still need
  a trusted-device unlock passcode.
- Battery level and street address are unavailable. Recorder history starts
  with collected reports; historical backfill is not implemented.
- amd64 is the only supported app architecture. Supervisor builds from source.
  Public prebuilt container redistribution remains pending dependency licensing
  review, including the pinned exporter with no clear license declaration.
- Credential isolation, CSRF/read-only API and recovery ownership have automated
  tests. Supervisor backend authorization was source-reviewed and the app additionally
  enforces administrator groups (Supervisor 2026.11.0+). Independent security
  review, real non-admin browser validation,
  full session-expiry recovery and live Supervisor backup/restore validation are
  incomplete. Pairing revocation and strict private restore validation now have
  regression coverage. Channel delivery also requires native Core tests,
  hassfest and an OSV package check. Setuptools has scoped, expiring platform-only
  applicability notes; see DEPENDENCIES.md. This is not an independent audit.
- Edge, local and future Stable app installations have separate private data.
  Switching installation/channel currently needs one-time account setup.
  The companion integration uses one shared code package in Core; installing
  Edge integration code does not provide separate Core-code versions per app.
- Existing registry IDs are preserved during the Beta-to-Edge display-label
  migration. Renaming old entity IDs requires checking their consumers first.
  New entity IDs already contain their channel.
- Friendly model names cover a bounded catalog. Unknown models retain the raw
  model code. Pairing dates mean the exported pairing date, not purchase date.

Model facts are checked against DeviceKit's generated hardware catalog
(https://github.com/devicekit/DeviceKit/blob/master/Source/Device.generated.swift)
and Apple Support's MacBook Pro identification page
(https://support.apple.com/en-us/108052). No online model lookup is performed
during use, and hardware serials are not shown in descriptive labels.

A first official 0.x preview can disclose these limits. Production-Stable
promotion must not claim the outstanding validation has passed.
