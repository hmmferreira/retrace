# Private app-data backup and restore

Use Home Assistant's supported encrypted backup and restore UI. Include the
Retrace app and, for an HA recovery, the companion integration/Core config.
Keep the backup encryption key securely outside this installation. App private
data contains Apple session tokens, item keys and a location-read pairing token;
file permissions alone do not encrypt them. Never attach that archive to an
issue, commit it, or paste its contents into chat/logs.

For a same-channel recovery, restore the app's complete private data with the
same app slug rather than selected individual files. The identity ties the
read API and native entities to this installation. Keep identity, items, key
files, account/exporter sessions, reports and search checkpoints together.
Bootstrap validates the complete private tree before repairing ownership/modes.
Symlink roots, directories and files, hardlinks and special files are rejected.
Missing or malformed identity state fails instead of creating a replacement over
an incomplete restore. Do not work around this by deleting remaining data;
restore a complete backup or retain the old data and use a separate installation.
After starting, confirm the existing integration connects, choices and saved
sighting timestamps are preserved, and a new poll completes. Restored sightings
must retain their original timestamps. A restored session may still have expired
at Apple and require the guided sign-in flow.

Do not run two copies of the restored identity simultaneously. Stop the old copy
before starting its replacement. Cross-channel migration is not a supported
backup restore shortcut: Edge, local and Stable use different app slugs and
separate data. Do not restore over a working installation merely to test this.

Automated coverage uses only synthetic private files copied with their modes.
It verifies stable identity, choices, key/session bytes, reports and checkpoints,
health reset on startup, corrupt JSON rejection, and no secret fields in the
public snapshot. Fault injection also verifies failed selection, metadata and
report writes are not published in memory. This does not validate Supervisor's
archive/encryption implementation or actual Apple session validity. A live
Supervisor backup/restore round trip is still a release checklist item.


## Generation cleanup and backup mode — source review, 2026-11-22

The prepared app config sets `backup: cold`. Supervisor stops the app while
capturing its private files, avoiding an archive racing machine-generation
publication/cleanup. Tracking pauses during that backup. This is packaging
preparation; it does not change the currently installed Edge app or prove a live
restore. Preserve the whole private app directory and keep backups confidential.
