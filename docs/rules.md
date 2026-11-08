# Synchronization rules

[← HLSync README](../README.md)

HLSync automatically honors `.gitignore` files as local exclusions. When the
mapped local root is inside a Git repository, this includes all ancestor
`.gitignore` files up to the nearest repository root, plus files inside the
mapped tree. Without an enclosing repository, ignore scope starts at the mapped
root. Git worktrees are supported; no Git installation is needed.
Explicit HLSync rules override this baseline; profile rules override common rules.
To deploy a Git-ignored path, use `hlsync include vendor/` (or a specific file).
Ignore files above the repository root, Git's global excludes, and the Git index
are not consulted; matching tracked files are excluded too.

**Review `hlsync push --dry -p` before pruning:** with `-p`, locally excluded
files that are already deployed are deleted remotely. Without `-p`, their remote
copies are left alone; remote exclusion rules protect paths even when pruning.

Common rules live in `~/.hlsync/rules.json`, apply to every profile, and are
created with default exclusions for version-control metadata and common logs:

```text
**/.git/**
**/.svn/**
**/.hg/**
**/.DS_Store
**/Thumbs.db
**/desktop.ini
**/.gitignore
**/.gitmodules
**/error_log
```

Manage common exclusions and inclusions from any directory with `-c` /
`--common`. Common paths are rooted at every profile's local root:

```console
hlsync exclude -c '*.tmp'
hlsync include -c 'public/*.tmp'
hlsync rules -c      # inspect common rules
hlsync rules rm c4   # c prefix selects common rules
```

Profile rules are the extra rules for one profile only. Common rules apply
first and profile rules apply afterward, so a profile rule overrides a common
rule for the paths both match. That includes broad profile inclusions: after
`hlsync include gallery/`, a `.DS_Store` inside `gallery/` is included despite
the common exclusion. Add `hlsync exclude --anywhere .DS_Store` to the profile
to exclude it there again.

`hlsync rules` shows the common rules first and then the profile rules, each
grouped by folder. Common rules have `c`-prefixed IDs such as `c4`; profile rule
IDs remain numeric. IDs identify only current rules and may be reused after a
rule is removed. HLSync never silently adds new defaults to an existing common
rules file.

Each `exclude` or `include` takes one path. A path names that file, or a
folder and everything in it:

```console
hlsync exclude run_server.sh
hlsync exclude node_modules
```

A wildcard keeps matching files added later, and it also matches in every
subfolder. Use `-s` / `--shallow` to match in the named folder only:

```console
hlsync include 'gallery/static/*.webp'     # every .webp under gallery/static
hlsync include -s 'gallery/static/*.webp'  # gallery/static itself only
hlsync exclude '*.log'                     # every .log below this folder
```

Quote wildcards. Without quotes, the shell replaces the wildcard with the
matching file names before HLSync runs, and HLSync refuses the resulting list
with `got multiple paths`. If only one file matches, HLSync cannot tell and
records that file. In zsh, `alias hlsync='noglob hlsync'` in
`~/.zshrc` passes wildcards through without quotes.

To match file types without a wildcard, name a folder and use `--ext`:

```console
hlsync include gallery/static --ext jpg,png,webp
```

To name several paths in one command, separate them with commas, or pass
`-m` / `--multiple` to accept space-separated paths, as tab completion and
scripts produce:

```console
hlsync exclude composer.json,composer.lock
hlsync exclude -m composer.json composer.lock
```

A literal filename containing a comma cannot be addressed, because commas
separate paths.

Use `--anywhere` (or `--any`) to match a plain name at every depth below the
current folder:

```console
hlsync exclude --anywhere .DS_Store
hlsync exclude -c --anywhere cache/     # matching folders in every profile
```

Rules are rooted where the command runs. `*` matches within one name, and a
complete `**` segment spans any number of folders; it is accepted but never
needed. HLSync rules are not Gitignore syntax: `!`, `?`, bracket patterns,
absolute paths, parent traversal, and partial-segment `**` are rejected.

Local rules define the authoritative local set. Remote rules instead protect
server-side paths from synchronization:

```console
hlsync exclude --remote subdomains
hlsync include --remote subdomains
```

Remote operands are declarative and never require a connection when recorded.
`subdomains` and `subdomains/` store the same exact boundary. During diff or
push, an existing remote file is left untouched; an existing remote directory
and everything beneath it are left untouched without traversing the directory.
A matching remote inclusion removes or overrides that boundary and returns the
path to normal push policy. Remote directory boundaries cannot be pierced by a
more specific child inclusion. `hlsync rules` groups the two rule targets under
`Local paths` and `Remote paths`.

Local rules keep the original compact JSON form. A missing stored `target`
means local; only remote rules add `"target": "remote"`.

Rules have stable IDs and the highest matching ID wins. HLSync removes provably
redundant exact rules but preserves ambiguous wildcard overlaps.

```console
hlsync rules
hlsync rules rm 3 5 c4
```

`rules rm` takes several IDs, as separate operands or comma groups. Every ID is
checked before any rule is removed. `hlsync rules` describes wildcards in words,
such as `*.webp (all subfolders)` or `*.webp (this folder only)`.
