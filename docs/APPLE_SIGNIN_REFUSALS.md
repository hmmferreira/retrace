# Initial Apple sign-in refusal

## Observed boundary — 2026-11-20

Retrace's typed diagnostics recorded `apple_step=init`, `apple_code=-22410`.
At this stage the pinned SDK has sent the username, initial SRP value and client
metadata; it has not calculated/submitted the password proof. This is not evidence
of a wrong password. The code alone does not establish an account ban, a temporary
rate limit, a specific identity defect, or a universal recovery procedure.

A separate Linux collector reported the same initial error before 2FA on
2026-11-19/20: https://github.com/parawanderer/OpenTagViewer/issues/288 . That
report also describes an affected account completing Apple's web sign-in. These
are observations from that reporter, not a diagnosis of this household account.

Upstream main was inspected at 37d5ca0; changes after our pinned 8ecfae6 concern
hsc=409 second-factor detection after the SRP exchange. They are not an established
fix for this initial refusal, so the runtime pin has not been changed.

## Offline identity consistency check

Startup checks an existing signing identity without provisioning or signing in.
The restricted native worker compares its saved device ID, local-user ID and
client-info string against the saved account metadata. Only three booleans and a
fixed status/error label are logged as `Retrace identity check`. No IDs, serials,
OTP headers, tokens, passwords or native-state bytes enter diagnostics. No header
is generated, no account/client network request is made, and no saved files are
replaced. A missing identity is reported as not_saved and never created by this
check. Cancellation closes/reaps the worker.

`consistent` rules out those three mismatches; it does not prove Apple's acceptance
of the machine/client or establish why -22410 was returned. `mismatch` is diagnostic,
not permission to silently change/reprovision the identity. Preserve saved state
and investigate before any explicit recovery action.

Do not repeatedly replay sign-in, reset the account password based on this code,
substitute somebody else's hardware identifiers, or add an unreviewed remote
signing provider. Direct sign-in on Apple's own website is a separate human check
for account-level problems. It must not put credentials or verification codes in
chat, logs, fixtures or Git. No upstream maintainer message has been sent.

## Verified household check

Edge0.1.14-dev.1.5 completed the offline check on Home Assistant: device ID,
local-user ID and client-info comparisons all returned true (`consistent`).
This eliminates those saved-native-vs-account mismatches as an explanation for
this installation's observed refusal. It does not establish the server's reason
or validate the account through Apple's web flow; that human check is pending.
Private signing identity and account session were retained without another login.
Validation: 280 app regressions, 877 upstream cases, 17 controller cases and
15 discovery cases passed, along with the isolated worker/report-child smoke.

## Upstream macOS signer lead — 2026-11-21

The latest observed failure remains `apple_step=init`, `apple_code=-22410`.
OpenTagViewer commit [05b5d7c](https://github.com/parawanderer/OpenTagViewer/commit/05b5d7cb26c9a48925f5fa580f063da4c1bed3b0)
introduces emulated macOS CoreADI in place of Android-derived signing. Its commit
explicitly says a real sign-in has not yet been verified. This is a candidate,
not an established fix. See [the source-only review](MAC_SIGNER_REVIEW.md).

The related `macOS` versus `Mac OS X` client-label change is not sufficient here:
Retrace's pinned SDK already uses `Mac OS X`. No runtime dependency, native
artifact, saved identity or session was replaced during this review.

## Working-versus-failing change audit — 2026-11-21

The owner confirms normal sign-in on Apple's account website succeeds. This
narrows the problem to this client path; it does not exclude restrictions scoped
to a client, service or provisioned machine.

Contemporaneous handoff notes recorded successful login, SMS request/submission,
session save and discovery handoff in the renamed Retrace installation, followed
by two failed sign-ins before delivery of Edge1.4's typed diagnostics. This places
both success and failure on Edge0.1.14-dev.1.3 (delivery83decc2). The earlier
generic errors did not retain an Apple error code; do not retrospectively label
those failures -22410. The currently retained log confirms init/-22410 on Edge1.5,
but no longer contains the historical successful sequence or identity-check line.

Read-only Git comparison results:

| Compared artifact | Result |
| --- | --- |
| Working Shared source a8c3eff versus current delivery1cae6df: account construction, provisioning, offline signer, HTTP transport, native artifact policy | Identical after namespace/path substitution |
| Both Python dependency lockfiles across that comparison | Byte-identical |
| Working shared Dockerfile versus current rendered Dockerfile | Identical after namespace/path/user substitution |
| Retrace delivery83decc2 versus1cae6df: account construction, provisioning, offline signer, HTTP transport, native artifact policy, private session store and owned session | Byte-identical |
| Protocol revision/archive pin | Remains 8ecfae6 / 676e871098ec60a9c5e6718ea8cc18215631b036b99117a814ac1eb87d4e99e7 |

Changes after Edge1.3 are error classification/UI diagnostics and an offline
identity comparison. They postdate the first recorded failures. The rename did
create fresh storage/identity, as explicitly requested, but the renamed install
subsequently authenticated successfully. The earlier setup flag mistake was a
separate local failure and was corrected before that success.

Limits: matching build recipes do not establish identical OS/Python base image
bytes (base tags and apt packages are not digest-pinned). No historical native
state snapshot or complete time-stamped success/failure trace is available for
comparison. We have not established whether Apple's policy, machine acceptance,
state evolution, timing or another runtime condition changed. A server/client
acceptance issue is plausible, supported by independent upstream reports, but
remains a hypothesis. No code regression explaining init/-22410 was identified;
that is not proof that all possible client defects are excluded.

The audit used source/build comparisons and existing safe diagnostics only. No
household authentication was replayed, identity regenerated, private state read
into tools, or app update/restart performed. A rollback is not an established fix
because the same earlier release already exhibited failed sign-ins.
