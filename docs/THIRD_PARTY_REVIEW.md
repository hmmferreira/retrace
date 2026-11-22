# Current shared-runtime review — 2026-11-22

Use [the current native/dependency review](reviews/NATIVE_LICENSE_REVIEW_2026-11-22.md)
for the working macOS provider. It includes the exact Apple artifact, MIT protocol,
GPL Mac engine/Unicorn distinctions, installed-package notice inventory, SBOM,
security fixes and remaining permission question. The Rust exporter/helper below
are absent from the shared runtime and do not block that runtime's review.

The runtime inventory contains32 installed Python distributions (31 locked plus
base-image pip),106 Debian packages and66 Python notice files. See reviews/ for
machine-readable evidence. Public prebuilt native images remain unapproved;
source-build packaging does not establish Apple-component use permission.

## Historical legacy redistribution review — 2026-11-17


This is an evidence inventory, not a completed license/compliance review.
The project's MIT license covers its own code; it does not grant rights over
bundled dependencies. Keep public container publishing disabled while the
unresolved entries below remain. A public repository or downloadable image is
not itself a substitute for a license declaration.

| Component | Build reference / evidence | Release status |
| --- | --- | --- |
| FindMy.py | Version 0.10.2, recorded in requirements.lock; upstream MIT license | Preserve notices; transitive audit remains |
| findmy-export | Checkout 29f44e20da97e98ebac8083b5a542a571551f26a; root Cargo.toml has no license field and no root license was found; GitHub license API returned 404 on review | Obtain clear upstream licensing/redistribution permission before public binary delivery |
| rustpush and associated crates | Exporter Cargo.lock pins 295ef9078aae30de4adab2e3f6aa4b5162c4ad07; reviewed source checkout contains Server Side Public License v1 and LICENSE.exceptions naming OpenBubbles | Review applicable obligations and exception scope; do not assume the named exception applies to this project |
| anisette-v3-server | Dockerfile pins image digest d551c75454bcbee68dc262d4247d5f87fa309dfc8f2125644d333c648596e3c7; current upstream root tree and dub.json do not provide a clear license declaration | Establish the image-to-source revision and redistribution terms, including its Provision dependency |
| Python transitive wheels | Thirty exact runtime versions and wheel hashes in requirements.lock | Integrity checking exists; full license/advisory audit and notices inventory remain |
| Leaflet | Vendored 1.9.4 with accompanying license/hashes | Preserve notices; OpenStreetMap attribution stays visible |
| Base images and Debian libraries | Runtime/build image references and apt packages are in Dockerfile | Complete SBOM, license notices and image provenance review before public images |

Sources:
- [Pinned exporter package manifest](https://github.com/malmeloo/findmy-export/blob/29f44e20da97e98ebac8083b5a542a571551f26a/Cargo.toml)
- [Exporter repository](https://github.com/malmeloo/findmy-export)
- [Pinned rustpush license](https://github.com/malmeloo/rustpush/blob/295ef9078aae30de4adab2e3f6aa4b5162c4ad07/LICENSE)
- [Pinned rustpush exceptions](https://github.com/malmeloo/rustpush/blob/295ef9078aae30de4adab2e3f6aa4b5162c4ad07/LICENSE.exceptions)
- [Helper package manifest](https://github.com/Dadoum/anisette-v3-server/blob/main/dub.json)

Next steps are upstream clarification for the exporter/helper, a complete
transitive dependency inventory, review of obligations, and the required notices
and source availability. No maintainer messages have been sent. Source builds
on the user's own Home Assistant are the current experimental deployment path;
that does not establish clearance for an official community distribution.
