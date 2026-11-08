# Paths, traversal, and listing

[← HLSync README](../README.md)

Paths are relative to the current directory inside the mapped root. Multiple
paths and wildcard patterns form one deterministic selection. Absolute paths,
parent traversal, and paths escaping the mapped root are rejected.

| Command | No path | Explicit directory | Depth option |
| --- | --- | --- | --- |
| `list` / `list --remote` | Current directory, one level | Directory contents, one level | `-r` includes descendants |
| `diff` | Complete current subtree | Complete directory subtree | `-s` limits to immediate contents |
| `push` | Complete current subtree | Complete directory subtree | `-s` limits to immediate contents |
| `pull` | Error: path required | Directory contents, one level | `-r` includes descendants |

Diff and push accept `-s` / `--shallow`; `-r` / `--recursive` remains available
to explicitly select the default. The two flags cannot be combined.

`.` explicitly selects the current directory. An immediate child directory
outside the traversal depth appears with `▸` but is diagnostic-only: it is not
created, replaced, deleted, or entered. The selected directory itself may be
created when selected files require it as their parent. An explicitly selected
remote-only directory is the deletion target itself, so recursive push
enumerates that subtree and removes its contents deepest-first. With `-s`,
deeper folders and their deletion ancestors are retained.

## Local and remote listing

`list` reads only the local filesystem, includes dotfiles, and applies the
configured rules:

```console
hlsync list
hlsync list templates
hlsync list '*.md'
hlsync list -r
hlsync list -r -i
```

Use `--remote`—or the `lsr` shorthand—to inspect the equivalent FTPS
tree with the same operands and traversal controls:

```console
hlsync list --remote
hlsync list --remote templates -r
hlsync lsr
```

Remote listing connects read-only. Remote-excluded paths use `#` and their
directories are shown as boundaries without being entered.

Directories appear before files at each level, with each group sorted by name.
Directories end in `/`; local exclusions use `x`, remote exclusions use `#`.
Single-side listings do not report whether the other side has a copy. `-i`, `--inc`, and
`--included-only` hide excluded paths. `hlsync ls` remains an unadvertised
compatibility spelling.
