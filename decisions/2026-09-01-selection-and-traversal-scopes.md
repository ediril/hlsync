# Selection and traversal scopes

Date: 2026-09-01

## Decision

With no operands, `list` and `diff` select the current directory's immediate
contents. Bare `push` selects the complete current subtree and is equivalent to
`push -r`. Pull requires at least one explicit operand.

A selected directory includes its immediate contents and adds descendants only
with `-r` / `--recursive`. `.` selects the current directory. Multiple paths or
wildcards form a deterministic union. A leading profile establishes its root as
a one-command virtual working directory. Paths cannot escape the profile root.

Traversal lists a directory, classifies each child, and only then schedules
eligible child directories. A directory excluded on the remote side is a hard
boundary: it is displayed but never entered, deleted, or otherwise mutated. A
locally excluded directory is also retained and not entered, because FTP cannot
delete a nonempty directory without traversing it. A later local inclusion that
may match a descendant permits the local walk needed to honor that inclusion;
remote boundaries cannot be pierced.

`-I` / `--include-excluded` removes the local boundary for one `diff`, `push`,
or `pull` by dropping local rules and Git ignores from that command's RuleSet.
Excluded paths then follow the same comparison and transfer path as included
ones, and pruning treats them as present, not absent. Remote rules stay in that
RuleSet. Naming a path does not lift an exclusion by itself.

Locally excluded files remain file-level absences and may be deleted remotely
by an explicitly pruning push (`-p`). Without pruning, remote-only directories
are retained and not entered. With it, included remote-only directories may be
inventoried and deleted recursively when they are inside recursive push scope. An explicitly
selected remote-only directory is likewise inventoried fully so FTP can delete
its contents deepest-first. A protected descendant retains its deletion
ancestors.

Bare diff remains shallow but marks an immediate included remote-only directory
as a collapsed recursive deletion because bare push will enter it. An explicit
shallow operand does not project implicit recursion. A directory outside
selected traversal depth remains visible with a collapsed marker, but is
diagnostic only and is not authorization to create or delete its contents.

Recursive comparison streams deterministic directory subtrees. Paged comparison
uses an explicit resume path and reconstructs traversal from a fresh read;
there is no persisted session or cached comparison cursor. Presentation details
and command spellings are documented in README.

## Rationale

Filtering before descent makes exclusions useful as scalability and safety
boundaries, while preserving recursive push for the included tree. Retaining a
locally excluded directory avoids pretending HLSync can prune it without doing
the very traversal the exclusion forbids. File-level pruning remains useful for
ordinary generated or unwanted files.

An explicit option keeps one rule for every path: exclusions apply unless the
command says otherwise. Lifting them implicitly for a named path made the same
file behave differently depending on whether its parent folder was excluded, and
a shell-expanded `push *` would have uploaded excluded folders without asking.

Stateless paging avoids retaining stale remote state between invocations.

## Intentionally excluded

- Entering an excluded directory merely to inspect or prune it, without `-I`.
- Piercing a remote exclusion with a narrower child inclusion.
- Implicit recursion for `list`, `diff`, or an explicit directory operand.
- A bare pull operation.
- Walking ancestor directories merely to reach an exact selected directory.
- Persisting selection or traversal state between commands.
- Treating a visible untraversed directory as authorization to mutate it.
- Using `--prune` to change traversal depth.
