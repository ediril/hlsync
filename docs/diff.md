# Diff

[← HLSync README](../README.md)

`diff` is read-only and shows what the corresponding push would do:

```console
hlsync diff
hlsync diff templates
hlsync diff -s
hlsync diff templates --shallow
hlsync diff index.html app.js styles.css
hlsync diff '**/*.css'
```

Local path existence decides what is uploaded or replaced. In the default
push view, remote-only paths are retained because push never deletes without
`-p`. Preview a pruning push with:

```console
hlsync diff --prune
hlsync diff -p
```

`--pull` changes the perspective for changed existing files and retains
remote-only paths.

Diff compares one folder at a time and prints each folder's changes as soon as
it is compared. While a folder is being read, interactive terminals show a
status line such as `Reading gallery/static/ · 312/644 files`, which clears
before results print. Redirected output contains only the results.

By default, diff shows only what the matching push or pull would do: uploads,
updates, deletions, and conflicts, under their folder headings. A final
`Not shown:` line counts what was hidden. Widen the view with:

```console
hlsync diff -x      # also show excluded paths (--excluded)
hlsync diff -I      # compare locally excluded paths as included (--include-excluded)
hlsync diff -a      # show everything, including unchanged and kept paths (--all)
```
Recursive diff keeps file-browser order in both views: directories and their
indented contents appear before files at the parent level.
Rows without status markers retain blank status columns so names stay aligned.
Status columns stay fixed at the left; tree indentation applies to path names.
The status has three slots: action (`+`, `~`, `-`, `?`, `=`), exclusion
(`x` local, `#` remote), and presence (`l`, `r`, or blank for both sides), so
`-x` marks an excluded path that `--prune` would delete.
The `▸` marker means contents were not inspected, including excluded folders.
Diff reads directories as it traverses the tree and groups their entries under
folder headings, without separate per-directory read announcements.

For pruning, a locally excluded file is treated as absent. If it exists
remotely, default diff marks it ` x` and retains it; `diff -p` marks its
deletion as `-x`. The presence column still reports the actual copies:
blank when both exist, `r` when only the remote copy exists. An excluded
directory is a traversal boundary and is retained with `x`. An explicit local
inclusion for a descendant permits traversal;
remote exclusions remain hard boundaries. Hiding exclusions never hides a
deletion: with `-p`, an excluded path that would be deleted always shows as `-x`.

`-I` / `--include-excluded` treats locally excluded paths as included for one
`diff`, `push`, or `pull`. Exclusion rules and `.gitignore` files are not
consulted, so nested paths such as `.git/` and `.DS_Store` count too. Remote
exclusions still apply.

```console
hlsync diff -I collectiq/data
hlsync pull -I collectiq/data/.waitlist.sqlite
hlsync push -I collectiq/data --dry
```

Diff enters eligible child folders by default. `diff -s` or
`diff templates --shallow` reads only immediate contents. Unentered child
folders retain the `▸` marker and are retained, matching `push -s`. Unentered
folders appear by default only when they could still hold changes; an
unentered remote-only folder appears as `   r folder/ ▸` with `-a`. Without
`-p`, diff does not enter remote-only folders, since push would neither change
nor delete their contents.

Show the current status and directory notation without connecting:

```console
hlsync --legend
```

Diff prints each directory as it is compared. For a shell-driven review,
`--paged` prints one directory, exits, and provides the exact stateless
`--resume` command for the next deterministic directory.

Colors are automatic on terminals, disabled for pipes and redirection, and
suppressed when `NO_COLOR` is set. Text markers retain the core meaning without
color. The left column reports action or status: `x` means locally excluded
and `#` means remotely excluded. The right column reports presence: `l` means
local only, `r` means remote only, and a blank means both sides. For example,
`x   notes/ ▸` exists on both sides but is locally excluded, while
`# r millionminds/ ▸` exists only remotely and is remotely excluded. Exclusion
source never changes the presence column.

## Slow listings

Servers that support MLSD return a whole folder, with exact sizes and times, in
one request. Without MLSD, HLSync reads the folder with LIST and then asks for
each file's size and time separately, two requests per file, so a folder of
several hundred files can take a minute. HLSync reports this after connecting,
and `hlsync connect` reports it too. vsFTPd has no MLSD support at all;
servers such as ProFTPD and Pure-FTPd provide it, so ask your host whether
another FTP server is available. Push's remote scan has the same cost.
