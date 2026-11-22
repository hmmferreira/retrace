# Native component and dependency release review — 2026-11-22

Scope: the working shared runtime and macOS provider, not the legacy Rust/helper
image. This records evidence and unresolved questions; it is not legal clearance
or an independent security audit. No maintainer/Apple/legal adviser was contacted.

## Result

**Apple component-use permission remains unresolved.** After this review, the
maintainer explicitly authorized the first official source-only release with that
uncertainty disclosed. The earlier publication hold is superseded by that decision;
this is not Apple permission or a change to the legal assessment.
A passing checksum, successful login, local download or user checkbox does not
establish permission. This review does not conclude that use is unlawful either.

## Apple CoreADI

- Exact private artifact: iTunes12.8.3, CoreADI4.19 x86_64; SHA256
  `2eafc3c79c7f41a8afbfbeaaf23ee5dab5ad5bda55ec8e54dbc0ddf1d20ce630`.
  Source/range/payload pins are in ARTIFACT_PROVENANCE.md and macos_artifact.py.
- [Published iTunes terms](https://www.apple.com/legal/sla/docs/iTunes.pdf),
  English sections2A/2B,3 and5B, describe limited installation/use, restrictions on
  copying/reverse engineering/modification with exceptions, redistribution
  restrictions and additional service/account terms. They do not explicitly
  describe this extraction-and-emulation arrangement on a Linux HA host.
- Apple's [license index](https://www.apple.com/legal/sla/) warns that the license
  accompanying a particular product can differ from the currently published one.
  Inspected the exact12.8.3 installer and found the English app License.rtf,
  identifier EA1510, dated2017-08-31,28816bytes, SHA256
  eda6a88a807d38bbfcc62befabbfef463d40ad9041285d85dec1e0d1d556be97.
  Its relevant sections2A/2B/3 match the concerns in the published PDF. The full
  installer was291523996bytes, SHA256
  dd08b9967db3e5847955fa168ce880303abf5f36de12abb2061e7ef1a25be214.
  Installer/package/license originals remain private review files outside Git;
  no Apple executable was run for this inspection.
- Project packages/images contain no Apple binary. The user acquires fixed bytes
  directly from Apple. This addresses project binary redistribution, but does
  not by itself settle copying, execution or service-use permission.
- Required closure: obtain a supported
  permission/applicable-exception assessment for this distribution/use model.
  That assessment may require qualified legal advice or permission from the
  relevant rights holder. The code cannot manufacture that authorization.

## Open-source engine and protocol

- FindMy.py candidate8ecfae6: MIT text/copyright retained in app licenses and next
  to the pinned source in the shared image. PyPI FindMy0.10.2 is also installed;
  the pinned source shadows it. Both are identified; do not hide the redundant
  installed distribution from the inventory.
- Mac engine595d398: four unchanged Python files, exact hashes, original comments,
  complete GPLv2 text and corresponding retained source are shipped together.
  Retrace's MIT license does not replace those terms.
- Unicorn2.1.4 wheel metadata advertises BSD and has no notice files. Upstream
  [README](https://github.com/unicorn-engine/unicorn/blob/8028ec436f2d9376525352dd38ed9ed6b9f6be10/README.md)
  and COPYING identify the native engine as GPLv2; additional LGPL/other components
  have their own notices. The wheel classifier is insufficient to describe the
  complete native distribution. Retained COPYING, COPYING.LGPL2, COPYING_GLIB,
  AUTHORS.TXT and CREDITS.TXT with source hashes/revision are under app/licenses.
- [GNU's FAQ](https://www.gnu.org/licenses/gpl-faq.html#MereAggregation) treats
  communication mechanism and semantics as relevant to combined-work analysis;
  separate processes alone are not a blanket clearance. Keep the complete source
  and notices, and review the actual IPC/distribution arrangement. No claim that
  this entire package is exclusively MIT or that a subprocess erases obligations.
- First packaging target is source-build only. Native wheel binaries are acquired
  by the user's build from hash-pinned PyPI artifacts. Public prebuilt images need
  a separate complete corresponding-source/build-materials delivery assessment;
  upstream links and a copied GPL text alone are not represented as sufficient.

## Inventory and security evidence

- Disposable networkless shared image inventory:32 Python distributions (31 locked
  packages plus the base-image pip),106 Debian packages and66 Python notice files.
  Raw public metadata and retained notice text are in runtime-inventory JSON;
  CycloneDX1.6 snapshot lists installed Python/OS components. Vendored protocol and
  Mac-engine source pins are tracked separately. This is a snapshot, not an
  assertion that package metadata declares every embedded component correctly.
- Current OSV query:31 locked package versions,0 unreviewed findings,3 existing
  exact/expiring applicability notes. This does not scan Apple native code, all
  OS packages or guarantee absence of vulnerabilities. Exceptions expire2026-12-17.
- Project-owned HTTP restricts credential destinations/methods, TLS, redirects,
  environment proxies and response limits. Artifact-only transport rejects account
  credentials and permits one pinned URL/range. No remote signer is introduced.
- Native execution stays inside the networkless read-restricted worker, with
  bounded asynchronous IPC, timeouts/cancellation and worker reaping. Protocol
  Python remains trusted same-process code able to access transient credentials.
- Encrypted machine generations were unbounded. Added a separate shared-reader/
  exclusive-writer store lock and retention of current plus two previous machine
  generations. Cleanup touches only exact machine filenames in the Mac namespace;
  account-session files, original provider data and device history are untouched.
  Source app packaging uses Supervisor `backup: cold` so an archive does not race
  generation cleanup; polling pauses while that backup runs. This does not claim
  that live backup/restore testing has been completed.
  Reference: https://contributors.home-assistant.io/apps/reference/configuration/#backups
- Shared Docker build/runtime base images are now pinned to the digests used by
  the tested build. Apt packages still resolve through Debian repositories; the
  inventory records the resulting versions, not a fully reproducible OS snapshot.
- Keys and ciphertext share the host/backup trust boundary. Root or a compromised
  parent image can expose them. Hardware-backed protection is not claimed.

## Scope chosen for the first release

Stable starts fresh and never inherits Edge identities, selections, credentials
or history. Edge remains discardable development data. Extended field reliability
and additional recovery scenarios continue after release; they are not an indefinite
soak gate. Automated security regressions and honest limitation disclosure remain.
Stable publication records must continue to disclose unresolved Apple permission; maintainer publication authorization is not native-rights approval.


## Validation and packaging outcome

303 app regressions passed, including concurrent generation readers/writers,
bounded retention, failed publication, channel metadata and review-archive private
file exclusion/determinism. The pinned shared image built successfully. Its smoke
check verified retained notice files, non-root execution, the real restricted
worker boundary, default artifact refusal and the isolated report child. No Apple
login, provisioning, HA restart, live data deletion or deployment was performed.

A deterministic source review archive is prepared with a per-file SHA256 manifest,
source commit, intended0.2.0 stable channel, `history_migration:false`, and explicit
`installable_release:false`/permission-unresolved status. The production stable
renderer/workflow gate remains intact. The archive contains no Apple binaries,
private state, credentials or implied license approval. Package mechanics are
ready for review; it must not be advertised as an approved Stable installer.


## Official release decision — 2026-11-22

The owner explicitly requested first official publication despite the findings.
`release/0.2.0.json` authorizes source-only publication, excludes Apple binaries,
requires local operational consent and prohibits history migration. Stable starts
without an Android artifact or Apple download; protected Setup acquires the fixed
macOS component only after explicit consent. Private evaluation remains disabled
by default. No native license field has been relabelled approved. Release notes
retain the uncertainty and field-validation limitations.
