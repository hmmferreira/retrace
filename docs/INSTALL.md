# Local beta installation with Studio Code Server

This package is experimental. It does not replace the Dragon MQTT bridge or
Item Tracking dashboard. Real Apple UI authentication and Supervisor ingress
still need their first end-to-end trial. Do not publish the bundled exporter
before its license/redistribution rights have been resolved.

## Copy the package
1. Download the retrace-local-0.1.0.tar.gz package to your computer.
2. Open Home Assistant → Studio Code Server. Upload it to /config using
   Explorer's Upload action (or drag the archive into the Explorer).
3. Open Terminal → New Terminal and extract it:

    cd /config
    tar -xzf retrace-local-0.1.0.tar.gz
    cd retrace-local-0.1.0
    python3 install.py

The last command is a dry run. It verifies every packaged file and prints the
two destinations. It refuses to overwrite an existing beta installation. No
credentials or runtime data are in the package. SHA-256 detects transfer errors;
it is not a signature and does not prove who supplied the archive.

The installer detects /local_apps or the older /addons editor mapping.
If neither local-app mount or /config/custom_components is accessible,
stop and check its folder mappings; do not turn off protection mode or expose
a new unauthenticated service to work around it.

## Install and start the beta
4. If the destinations are correct, copy the two beta directories:

    python3 install.py --apply

5. Go to Settings → Apps → App store. Open its menu and Check for updates
   (reload the store). Find the Local apps section and Retrace (experimental).
   Install it. Its first source build includes Rust and can take several minutes.
6. Restart Home Assistant Core once to load the custom integration. This briefly
   pauses automations. No YAML edits or .storage edits are needed.
7. Start the Retrace app, open Web UI, and optionally enable Show in sidebar.
8. In Account & items, connect the polling Apple account. Choose the exact
   verification method and use the code sent by that method.
9. Discover items. Read the Keychain trust explanation, accept it, and follow the
   separate recovery prompts. Use the chosen trusted device's unlock passcode.
   Enter all credentials only in the app UI, over your normal HTTPS HA connection.
10. Select a small test set and save. Newly discovered items are unselected.
11. In Settings → Devices & services, confirm the discovered Retrace entry.
    If it has not appeared, wait up to five minutes with both app and Core running.

The app has its own Overview map. The integration creates Edge-suffixed devices
and native trackers/last-sighting sensors. The old MQTT devices remain separate.
After selection/login, allow the next 15-minute poll; expensive initial key
derivation may also take time. A sighting can be days old even after a new poll.

## Compare and recover
Verify timestamps, unknown items, accuracy, two successive polls and Recorder
history. Sign-in expiry should create a Home Assistant Repair asking you to open
the app. Do not delete the baseline or import real credentials into support files.
Only then consider a wider beta.

To stop the trial, stop the beta app and disable the beta integration. Preserve
private app data until you choose to remove it. Removing the integration/device
registry entries is a separate destructive step; review/back up before doing it.
