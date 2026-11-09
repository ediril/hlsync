# Push and pull

[← HLSync README](../README.md)

Push local changes or replace explicitly selected existing local files from the
remote side:

```console
hlsync push
hlsync push templates
hlsync push templates -r
hlsync pull index.html
hlsync pull templates -r
```

Push uploads local-only files and replaces changed remote files. Pull replaces
changed existing local files but never restores a missing local path. A changed
file is replaced only when the source copy is strictly newer than the
destination. If the destination is newer or the same age (for example, a file
edited on the server after your last push), diff shows `?` and push or pull
stops before changing anything, listing the conflicting paths. Use `--force` to
overwrite them, or select other paths. Because HLSync copies timestamps on every
transfer, a later edit on either side makes that side newer; the check assumes
the local and server clocks roughly agree. Locally
excluded paths are not uploaded or pulled unless `-I` / `--include-excluded` is
given, which applies to everything in scope, so review `push -I --dry` first:
a bare `push -I` would upload `.git/`, `.env`, and anything else your rules keep
out. Remote-excluded paths are never
traversed or changed. Push never deletes unless `-p` / `--prune` is given;
then it deletes selected remote-only paths, including remote copies of locally
excluded files. Excluded directories on
either side are retained and never entered; an explicit local inclusion beneath
an excluded local directory is the only reason to enter that local boundary.
Push recurses into selected directories by default, including remote-only
deletion targets when pruning. `-s` /
`--shallow` processes immediate contents without entering child folders,
creating them, or deleting them. A selected remote-only directory containing
an unentered child folder is also retained.

Preview the exact push scope and operation order without changing either side:

```console
hlsync push --dry
hlsync push templates --dry
hlsync push templates -s --dry
```

Both `diff` and `push --dry` inherit push's recursive default. Dry push
honors `-s`, `-p`, remote exclusions, and explicit directory scope exactly as a
real push would. Interrupted-upload recovery is projected and reported but not
performed. After planning, dry push runs the live transfer executor and skips
only its mutation calls, preserving preflight, operation order, feedback, and
counts.

Dry and live push identify each local and remote directory as they scan it. A
parent is fully classified before HLSync enters eligible children, and excluded
directories are never entered. Dry-run plans use diff's compact colored `+`,
`~`, and `-` action markers under an explicit dry-push heading.

Live transfers print the colored `+`, `~`, or `-` action and path after each
operation succeeds. A failure appears immediately; the final summary contains
counts without repeating errors. Dry runs use the same feedback to
show planned operations without performing them.
When no operation is needed, HLSync prints `Nothing to push` or `Nothing to
pull` without announcing an empty transfer phase. An empty push also reports
how many included files are up to date in the selected scope. Push summaries
report the outcome without a retained-path reminder.

After scanning, push shows the planned upload count and total size. Interactive
terminals show remote reads as completed/discovered directories (such as 2/12)
and the current path, without animation. The discovered total grows as eligible
subdirectories are found. During uploads, interactive
terminals display a progress bar with bytes sent and files installed. File
counts advance only after timestamp verification and installation; failures
remain visible immediately. Redirected output keeps ordinary per-file logs.
Dry runs show planned totals without simulating byte progress.

Push uploads up to four files at once, each over its own FTPS connection.
Use `-j` / `--jobs` to choose from 1 to 10 connections; `-j 1` uploads one file
at a time:

```console
hlsync push -j 6
hlsync push -j 1
```

Shared hosts often limit connections per account. When the server refuses an
extra connection, push uses the connections it already has and reports, for
example, `Using 2 of 4 connections; the server refused more`. Push never opens
more connections than it has files to upload, and the final summary repeats
the count, as in `Push complete: 612 changes over 4 connections.` Folder creation
and deletions still run on one connection, and deletions start only after every
upload succeeds. Each file is printed as soon as it is installed, so with
several connections the order can differ between runs. Dry runs open no extra
connections.

Delete selected remote-only paths explicitly with:

```console
hlsync push --prune
hlsync push -p 'generated/*.html'
```

Deletion is limited to the selected scope and runs only after every upload
succeeds. Pull never deletes remote paths.

## Safe file replacement

Remote ownership and permissions are controlled by the server. HLSync does not
apply local modes or issue remote chmod/chown commands. Staging files are created
beside their destinations and retain server-assigned permissions when installed.
For shared writable app-data trees (for example, `ftps-deploy` and `www-data`),
configure setgid directories and an appropriate umask or default ACL to create
`664` files and `2775` directories. Setgid alone does not grant group write;
replacement files receive the staging file's mode, not the old file's mode.

HLSync never uploads directly over a live destination. A direct FTP upload can
truncate or expose a partial live file when the connection fails. Instead,
HLSync:

1. Uploads to a uniquely named staging file beside the destination.
2. Verifies its size.
3. Applies the local whole-second UTC timestamp with MFMT (writable MDTM on
   vsFTPd) and independently
   reads it back with MDTM.
4. Moves the existing destination to a temporary backup.
5. Renames the verified staging file into place, then removes the backup.

This makes each file replacement recoverable, not the complete project
transactional—FTPS has no project-wide transaction. A later failure does not
roll back files already installed.

During a push, HLSync recovers its exact reserved artifacts as each selected
remote directory is read. It does not perform a separate recursive cleanup
scan. Abandoned upload files are deleted; obsolete backups are deleted when
their destination exists; a sole backup is restored when its destination is
missing. This cleanup is independent of remote-only deletion policy and does
not affect ordinary remote-only files. Concurrent pushes to one profile are not
supported.

Push stops at the first failure, with one connection or several: a folder that
cannot be created, a file that cannot be uploaded or read, or a lost
connection. No new uploads start, uploads already in progress on other
connections finish their staged installation, and deletions do not run. The
summary counts what completed, what failed, and what was not started, for
example `Push stopped after a failure for profile 'prod': 41 completed, 1
failed, 558 not started.`, and the command exits nonzero.
