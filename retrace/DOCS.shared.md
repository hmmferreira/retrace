# Retrace Edge

This shared-auth private evaluation uses the current Retrace app identity and
private data. A clean installation does not import pre-rename sessions or keys.

## First use

Open **Web UI**, use the main Apple account form, and explicitly enable item-key
recovery for discovery. Choose the verification method and enter its matching
code. Discovery then uses that same authenticated account. A trusted-device
unlock passcode is a separate Keychain step: it is not an Apple password or SMS
code. Enter credentials only in this protected UI.

After discovery, choose the items to track and save the selection. New items are
unselected. The overview shows reported positions and original timestamps, with
per-item refresh and scheduled checks every 15 minutes. No laptop is required.
Battery/street-address fields are not supplied by this location source. Native
Home Assistant zones and Recorder provide integration history.

## Secure setup and recovery

The shared runtime verifies an enforced native worker boundary before component
setup or sign-in. HAOS uses the dedicated restricted AppArmor child profile plus
seccomp; Landlock is used on supported Linux hosts. Never disable protection mode.

Setup is explicit: `runtime_mode: shared`, `private_evaluation: true`,
`install_reviewed_component: true`, and `create_new_identity: true` enable this
private first-time evaluation. The component is fetched only from the fixed vendor
URL, with source/member/bundle hashes checked before use. No vendor binary is in
this repository or app image. Existing components and signing identities are
reused; corrupted or missing saved material is not silently replaced.

**The signing identity is created lazily when you first press Connect Apple account,
not when the app starts.** Keep `create_new_identity: true` until the first
successful sign-in and discovery have completed. A healthy web UI does not prove
that this identity exists. After that first completed setup, return the two
setup-only flags to false. Existing saved identities are reused even while the
creation flag is true; it never authorizes replacing corrupt saved identity data.
Keep private evaluation enabled
for this evaluation scope.

Sessions and signing identity are encrypted in private generation files. A backup
must retain the full app directory, including matching keys, ciphertext, manifests,
component and item keys. Encryption does not protect against complete host or
backup access. Lost keys require explicit recovery; expired account tokens require
main-form reauthentication. Do not post passwords, passcodes or exports in logs,
issues or chat.

This is a technical private evaluation, not a statement that Apple licenses have
been cleared for this use or redistribution. Apple's published Music Android
software terms are at https://www.apple.com/legal/sla/docs/AppleMusic.pdf . Stable
promotion and live protocol/recovery verification remain separate release work.
