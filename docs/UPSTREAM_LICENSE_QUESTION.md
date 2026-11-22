# Draft licensing clarification request — not submitted

We are developing Retrace, a Home Assistant app for guided Find My item
setup and tracking. It currently builds findmy-export at
29f44e20da97e98ebac8083b5a542a571551f26a locally and includes private-session,
service-discovery and export-filename fixes maintained as build patches.

Before publishing a community container, could you clarify the intended license
for findmy-export and whether distribution of a modified compiled exporter is
permitted? We could not find a root license or a Cargo package license field.
Please also identify any required notices/source obligations and whether the
pinned rustpush dependency's SSPL and named exception affect this use.

We can provide the public patch recipe and proposed distribution structure for
review. We have not treated the repository's public availability as permission
to redistribute a binary. Thank you.

A separate clarification is needed for anisette-v3-server and the source revision
corresponding to its pinned container artifact. Do not post either draft without
an explicit instruction from the repository owner.
