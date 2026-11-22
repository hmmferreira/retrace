# Third-party notices

## FindMy.py protocol candidate (Shared Edge)

Upstream: https://github.com/parawanderer/FindMy.py
Revision: `8ecfae6cb34b29caf0bd8176ee73155ca81415a8`.
Copyright (c) 2023 FindMy.py Contributors. License: MIT.

The complete upstream license below is retained verbatim. A matching copy is
packaged at `/app/licenses/FindMy.py-MIT.txt`, with attribution in
`/app/licenses/NOTICE.md`. The shared image also retains the original upstream
`LICENSE.md` beside `/opt/retrace-protocol/findmy`. Source channel packages retain
these app files. Original project copyright remains in the root LICENSE; it does
not replace upstream copyright. Preserve both on redistribution and retain any
additional notices when adopting other code.

This entry covers the pinned protocol candidate only. Python wheel metadata,
Leaflet notices and other component licenses remain separate. This is not a
complete SBOM, provenance certification or approval of native-component rights.
See THIRD_PARTY_REVIEW.md and DEPENDENCY_BOUNDARY.md for outstanding gates.

## Complete upstream license

```text
MIT License

Copyright (c) 2023 FindMy.py Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Use, changes and voluntary support

The declared MIT license permits reuse, modification and commercial distribution
with the copyright and permission notice retained. It does not require publishing
our modifications or sharing donation proceeds. The upstream disclaimer remains;
license permission does not certify security or confer Apple-component rights.
Project-owned code currently also uses MIT, so others can reuse it under those
terms too. Keep upstream origins visible if maintaining a fork; copied code is
not an original clean-room implementation.

An optional external support link can support Retrace development without
claiming upstream/Apple/Home Assistant endorsement. Prefer a plain external link
over an embedded payment widget on the account UI, so no third-party scripts or
payment requests run there. Do not send account/item data in that link. No payment
account URL has been configured. Platform terms and applicable income obligations
are separate from MIT licensing.


## macOS signing engine (experimental Edge)

Source: https://github.com/parawanderer/os-findmy-e at
`595d39810639d750715babc30b063d4ac8f2c437`.
The unchanged files `tools/machoadi/{adi_run,harness,stubs,macho}.py` are retained
under `retrace/rootfs/app/retrace/mac_engine`, with their original comments,
repository GPL-2.0 license text and per-file SHA-256 provenance manifest.
The upstream package declares GPL-2.0-only. These files are not covered by the
Retrace root MIT license. Complete corresponding source for this retained Python
component accompanies the package and image in the same directory. Preserve the
GPL text and source on redistribution; process separation is not a general legal
clearance. Its own references to Dadoum/apple-crates remain intact.

The account parent does not import this engine; the networkless restricted child
loads it from verified source and brokered library bytes. No upstream HTTP client,
authentication CLI, filesystem session manager or runtime downloader is used.
Unicorn remains a separately licensed installed dependency; its notices/metadata
must also be preserved. Apple's CoreADI binary is acquired separately for explicit
private evaluation, is not GPL/MIT licensed by this project, and is excluded from
Git and image build contexts. Stable/native-rights review gates remain unchanged.
