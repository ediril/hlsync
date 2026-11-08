# Synchronization rules

Date: 2026-08-30

## Decision

Explicit synchronization policy has two ordered layers: common rules from
`~/.hlsync/rules.json`, followed by rules stored in the active profile. The
last matching explicit rule wins, allowing profile rules to override common
rules. With no explicit match, use the local
[Git-ignore baseline](2026-09-14-gitignore-defaults.md); otherwise include the path.

The common rules file has its own version and ordered rules. Seed it once with
conservative defaults; after creation it belongs to the user. Later releases
do not merge or restore defaults automatically. Common-rule management does not
require an active profile. Current defaults and CLI syntax belong in `docs/`.

Each stored rule has an explicit include or exclude action and a normalized
profile-relative pattern. A missing target means local; only remote rules
persist an explicit remote target. Common patterns are rooted at each profile.
The explicit pattern language supports segment-local `*` and complete `**`
segments across directory levels. Reject absolute paths and parent traversal.
Git-ignore syntax belongs to its separate maintained matcher.

Rule commands record wildcards as patterns, never as a snapshot of current
matches, and a wildcard also matches in subfolders unless `--shallow` limits it
to the named folder. The shell expands unquoted wildcards before HLSync runs and
leaves no trace of the original pattern, so rule commands accept one operand and
take several paths only as a comma group. Several operands are refused rather
than recorded as exact paths.

Rule IDs are positive integers scoped to their storage files, derived as the
highest current ID plus one. They are disposable removal handles, not lasting
model identity: deleted IDs can be reused and no allocation counter is stored.
Transient effective-policy assembly may reindex rules for matching without
altering persisted sequences. The CLI exposes storage scope when selecting
rules for removal; its spelling does not affect matching.

Adding the same normalized pattern replaces its prior rule in that storage
layer. Further cleanup requires proof that effective layered policy stays the
same, including explicit inclusions needed to override Git ignores. Inspection
may group and sort rules, but evaluation remains ordered.

Local rules define the authoritative local set. Remote rules define boundaries
that must not be traversed, uploaded, replaced, or deleted. Remote operands are
recorded declaratively without connecting or inspecting either filesystem.
At comparison or transfer time, the remote entry kind determines whether a
boundary protects one file or a complete subtree. A remote inclusion removes
or overrides that boundary and returns the path to ordinary local-authority
behavior. Child inclusions cannot pierce an excluded remote directory.

## Rationale

A user-owned common layer removes repetitive setup while keeping policy
editable. Applying profile rules last preserves deployment-specific exceptions.
Separate storage scopes prevent administrative handles from becoming a shared
identity model. Proof-based cleanup avoids changing precedence through a
presentation-oriented simplification.

## Intentionally excluded

- Automatically merging defaults into existing common configuration.
- Inferring remote entry kinds when recording rules.
- Entering remote-excluded directories for narrower child rules.
- Persisting rule-ID allocation history or renumbering surviving rules.
- Extending the explicit pattern language into a second Git-ignore matcher.
- Treating presentation order as evaluation order.
