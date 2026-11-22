# Retrace clean installation

The owner chose a clean break, accepting a fresh setup rather than retaining old
technical identifiers. Current project-owned code, package folders, app slugs,
HA integration domain/discovery service and entity prefixes use `retrace`.
The canonical repository is https://github.com/hmmferreira/retrace.

- App source and Python package: `retrace/` and `retrace/rootfs/app/retrace/`.
- Companion integration/domain: `custom_components/retrace`, domain `retrace`.
- App slug: `retrace`; optional separate evaluation app: `retrace_shared`.
- Capability probe slug/source: `retrace_runtime_probe`.
- Private data root: `/data/retrace`; optional override: `RETRACE_DATA`.
- Internal runtime settings: `RETRACE_RUNTIME_MODE`, `RETRACE_PRIVATE_EVALUATION`.
- Native profile: `retrace-native`; pinned protocol source: `/opt/retrace-protocol`.
- Encrypted session/signing format markers use Retrace names. Old ciphertext,
  identity manifests and app data are deliberately not auto-imported.
- New entity IDs are suggested as `retrace_edge_…` / `retrace_stable_…`.

## Existing household replacement

1. Decide whether to take a Home Assistant backup before uninstalling apps or
   integration entries. Teardown loses saved sessions and registry identities;
   Git source is not a backup of them. Backups contain sensitive data and stay
   in the user's normal private backup system, never in Git or chat.
2. Add the canonical `https://github.com/hmmferreira/retrace#edge` app repository.
   Install Retrace Edge. This is a fresh app, not an in-place upgrade of the
   pre-rename slugs. Keep old services stopped while using the new poller.
3. Install/redownload the companion through Marketplace. Remove old integration
   entries through HA's supported API/UI before removing their old component
   files. Update dashboard/automation consumers or remove obsolete references.
   Activate the new component with the normal Core restart; no .storage edits.
4. Configure explicit private-evaluation setup options for this experimental
   runtime, open protected ingress and authenticate again. Recovery consent,
   factors and trusted-device unlock stay in the UI. Select the items anew.
5. Approve the discovered Retrace integration. Verify fresh entities, polling,
   zone behavior and new Recorder history. Old history is not automatically
   transferred to the new IDs; do not purge the Recorder database to rename it.
6. Once the chosen backup/teardown conditions are met, remove old app/integration
   installations and the old repository registration through supported controls.
   Do not delete unrelated MQTT tracking, iCloud3 or other household integrations.

Private evaluation and release/security gates remain unchanged. This is not a
stable-release promotion. Setup may require the user to accept the Marketplace
warning and enter Apple credentials; agents must not bypass either requirement.

## Names that belong to others

Apple Find My, iCloud, FindMy.py, findmy-export and other third-party projects
retain their real names, import namespaces, copyright/license notices and source
URLs. They are dependencies/services, not former Retrace branding. Renaming them
would obscure provenance and can break protocol compatibility. Retrace currently
supports Apple Find My; other ecosystems remain a future direction.

## Project icon

The project owner supplied and selected the Retrace artwork on 2026-11-20.
The app icon is retrace/icon.png (128px). Custom integration brand icons are
256px and 512px under custom_components/retrace/brand. Web header/favicon and
home-screen bookmark PNGs are local static assets. These are resized format
exports of the supplied artwork, without a redesign or third-party image service.
App store metadata, integration brand images and the ingress header are separate
surfaces; the HA sidebar continues to use its configured Material Design icon.
