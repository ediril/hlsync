# Transfer execution

Date: 2026-09-02

## Decision

Push, pull, and dry push consume one deterministic ordered operation stream.
The executor performs preflight and preserves create-before-upload and
file-before-directory deletion ordering. Dry push uses that same executor with
mutations disabled, including timestamp changes and artifact recovery.

Push uploads through a unique staging file beside the destination, verifies
size and server-observed timestamp, and installs it by rename. Replacement
keeps a temporary backup until installation succeeds. Timestamp capabilities
and read-back guarantees are defined in the
[remote metadata decision](2026-09-13-remote-listings.md); remote permissions
remain governed by [server policy](2026-09-13-server-permissions.md).

Artifact recovery occurs while selected remote directories are read. Live push
repairs exact HLSync-owned artifacts; dry push projects those repairs into its
snapshot without mutation. Remote-excluded directories are never entered for
recovery or transfer. Reserved artifacts use the `.hlsync-` namespace; artifacts
from obsolete runtime names are not recovered.

Pull replaces only changed existing local files. It downloads and syncs a
temporary file beside the destination, verifies size, preserves local
permissions, applies the remote timestamp, and atomically renames it into place.

Push deletes selected remote-only files and then directories deepest first,
only after all uploads succeed. Retention policy suppresses those deletions.
Push stops at its first failure, whether a folder cannot be created, a file
cannot be uploaded or read, or a session fails: no new operation starts,
uploads already running on other sessions finish, deletions do not run, and the
result counts the operations that were not started. The same rule applies with
one session or several. Pull also stops at its first failure.

Uploads run concurrently over independent FTPS sessions: the scanning session
plus extra sessions opened only for the upload phase. Each session performs the
complete staged upload for one file at a time. All files wait in one queue that
hands each file to exactly one session, and a session takes the next file as
soon as it finishes. Directory creation, artifact recovery, and deletions stay
on the scanning session, before and after the upload phase. Each outcome is
reported as soon as it is known, so the live order of upload lines can vary
between runs while the set of outcomes and the summary do not. When the server
refuses an extra session, the push continues with the sessions already open,
because shared hosts cap connections per account.

The executor emits successful-operation events after completion and failure
events when they occur. Dry push uses the same callback for
planned operations. Byte-send events belong to the transport; bytes sent are
not installed files until verification and rename finish. Display observes these
events and never decides transfer completion or pruning eligibility.

Traversal reports discovered and completed directories from the same selected
walk, after exclusion filtering and artifact handling. Progress must not trigger
a second traversal, enter protected trees, or modify the plan. Marker spelling,
refresh rates, summaries, and optional tips belong in `docs/` and commit history.

## Rationale

A shared executor prevents dry-run plans from drifting away from execution.
Per-file staging makes replacement recoverable within FTP's capabilities.
Independent sessions are how established FTP clients parallelize transfers, and
each file stays an atomic staged unit, so concurrency changes throughput without
changing what a file installation guarantees.
Delete-last ordering preserves remote content until uploads are safely
installed, while traversal-scoped recovery avoids an unrelated tree sweep.

Outcome events keep completion authority in the executor and make failures
observable as they happen. Stopping at the first failure keeps a failed deploy
close to a known state instead of continuing around a problem. Separate byte and installation
events prevent presentation from claiming success before verification.

## Intentionally excluded

- Mutations in dry-run mode or treating a dry run as a write-permission check.
- A profile-wide artifact sweep or preliminary traversal to count work.
- Project-wide transactions, concurrent push commands against one profile, or
  resumable partial uploads.
- Splitting one file across several connections.
- Continuing past a failure to upload the remaining files.
- Persistently excluding a path because a transfer lacked permission.
- Pruning after an upload failure or counting failed files as installed.
