# Retrace

Apple Find My item tracking and location history in Home Assistant. Stable and
Edge have independent sessions, selections, entities and history. Start Stable
fresh; nothing is copied from Edge.

## Setup

1. Start the app and open its Web UI → Setup.
2. Review the Apple component notice. The macOS provider downloads a fixed native
   component directly from Apple only after explicit local consent. No Apple
   binaries are bundled. Apple's terms apply; the project's licensing review has
   not established permission for extracting/emulating it on Linux.
3. Enter your Apple account email and password, allow encrypted item-key recovery,
   then connect. Choose SMS or trusted-device verification and use the code for
   that chosen method. Your password and verification code are not saved.
4. If asked, choose a trusted device and enter its unlock passcode to recover item
   keys. This is separate from the Apple password and is not saved.
5. Choose items to track and save. Approve the discovered Retrace integration in
   Settings → Devices & services. Use Home Assistant's map and tracker history.

No Mac or laptop needs to stay running. The app performs polling on the HA host.
The macOS provider is the release default; the older Apple Music path is retained
for Edge development. No private-evaluation option is required for Stable setup.

## Operation

Items update independently. Manual refresh fetches stored reports and cannot force
an AirTag to broadcast. A report can be missing or old; its Apple timestamp is
preserved. Battery status, street addresses and historical backfill are unavailable.
Recorder controls Home Assistant history retention.

Keep backups private: they contain account tokens and item keys. App backups use
cold mode, briefly pausing tracking while state is captured. Encryption keys and
ciphertext live on the same host; this does not protect against host compromise.
Expired/rejected account sessions require explicit sign-in. No automatic password,
verification-code or device-passcode retries are performed.

The app and companion integration update separately. Keep the companion on a
compatible released version; the same Core package serves both Stable and Edge.
Do not install incompatible integration development code into everyday HA.

This is an independent project, not affiliated with Apple or independently
security audited. Apple compatibility and real-world recovery remain ongoing
validation. See the repository's security review and v0.2.0 release notes.
