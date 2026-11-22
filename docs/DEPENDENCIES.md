# Python dependency updates

`retrace/requirements.txt` records direct dependency intent.
`retrace/requirements.lock` records the complete tested CPython 3.12 Linux
runtime set. Production Docker builds, the test image and GitHub CI install this
lock with `--require-hashes --only-binary=:all:` and run `pip check`.

The initial lock preserves the 30 installed versions of the tested 0.1.8 amd64
image, excluding pip itself. SHA-256 hashes were obtained from the corresponding
non-yanked PyPI wheel metadata and committed for subsequent install verification.
This follows [pip's secure-install guidance](https://pip.pypa.io/en/stable/topics/secure-installs/).
No running app credentials or private state were used to create it.

For an update, resolve the direct requirements in a clean CPython 3.12 Linux
sandbox, review transitive version changes and licensing/advisories, and record
exact versions plus permitted wheel hashes in the lock. Do not regenerate during
app startup or Docker builds. Build the image from the updated lock, run the
synthetic tests and startup smoke check, then deploy Edge and verify real polling.
Promote only after the remaining release checks pass. A missing wheel must fail
the build; do not silently fall back to an unreviewed source distribution.

The hashes detect artifact changes after this reviewed lock; they do not prove
that a package is safe or that PyPI was uncompromised when the hashes were
selected. Rust uses its pinned checkout and Cargo lock separately. Base images,
Debian packages, SBOM/provenance and public image signatures need separate work;
this Python lock does not make the complete container bit-for-bit reproducible.

## Advisory check — 2026-11-17

`python tools/audit-python.py` queries OSV using only the public package/version
pairs in the lock, in bounded concurrent batches. CI runs it before delivery.
Network failure, new unreviewed findings, or expired applicability notes fail
validation. This covers Python packages only, not Rust, the helper or OS images.

The first scan found published advisories for aiohttp 3.13.2. It was upgraded to
3.14.5 with matching wheel hashes, regression tests and a new production build.
A follow-up query reports no aiohttp findings for that version. OSV findings can
change later; passing once is not a permanent security guarantee.

Setuptools 80.9.0 remains for the legacy `fs` dependency's pkg_resources use.
Three reported identifiers (including an alias) have exact, expiring notes in
`security/advisory-exceptions.json` on main: the affected features are macOS sdist
normalization and Windows legacy wheel installation. This app/test/CI runs Linux,
uses pip with hash-checked wheels, and does not execute those build/install paths.
This is an applicability assessment, not removal of the affected package. Review
by 2026-12-17; a new advisory or version is never covered by these notes. Replacing
the legacy fs/pkg_resources dependency remains preferable to indefinite notes.


## Shared release review — 2026-11-22

Rechecked all31 locked versions, including the shared protobuf lock: no unreviewed
OSV findings and3 existing exact/expiring applicability notes. Recorded32 installed
Python distributions (including base-image pip),106 Debian packages and66 notice
files from a disposable networkless shared image. The inventory and CycloneDX
snapshot are under docs/reviews. Retained installed Python notices in app/licenses;
added the missing upstream Unicorn native-engine GPL/LGPL/author/provenance files.
Do not infer the native engine's license from its wheel's BSD classifier.
Shared base images now have exact digest pins; apt repositories remain mutable.
No package upgrade, Apple binary redistribution or household state inspection was
performed in this review. These changes are source preparation, not a live update.
