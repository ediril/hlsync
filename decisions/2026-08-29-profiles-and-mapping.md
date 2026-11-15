# Profiles and mapping

Date: 2026-08-29

## Decision

Each configured entry is a deployment profile, not a server. A profile owns
its protocol and endpoint, credential environment-variable names, a remote
root, and at most one canonical absolute local root. A remote root is absolute,
or relative to the folder the account logs in to; the transport resolves a
relative root when it connects, from the login folder the server reports (FTP
PWD, SFTP REALPATH of '.'), so the stored value never depends on a server
lookup. Profiles may share
a host, but their local roots may not equal, contain, or be contained by one
another. Every descendant keeps the same profile-relative path beneath the
remote root.

Configuration stores these entries under the `profiles` key in
`~/.hlsync/configs.json`, using schema version 9. The model and public APIs use
profile terminology consistently; there is no parallel project representation.
Earlier runtime names and configuration schemas are not recognized or migrated.

New profiles always record a local root. A profile without a local root cannot
synchronize or own rules and must be completed through mapping.

Profile updates validate the complete proposed profile, including local-root
overlap, and require explicit confirmation, because a changed root, endpoint,
or protocol redirects every later transfer. They change only the given
settings and preserve the profile's rules. A protocol change moves settings
that are still on the old protocol's defaults to the new protocol's defaults,
so one protocol's credential variables never follow a profile to another
protocol's server.

A profile-aware command either names a profile explicitly or resolves the one
mapped root containing the current directory. No profile selection persists
between commands. Commands requiring a profile fail outside mapped roots;
`hlsync profile` instead reports that no profile is active. Removing a profile
deletes only its local configuration and never connects to its endpoint.

## Rationale

The complete local-to-remote target is the meaningful safety boundary; a host
alone cannot distinguish deployments. One non-overlapping local root makes
path translation and current-directory inference deterministic. Requiring the
command or filesystem context to identify the profile prevents hidden state
from redirecting a transfer.

A clean schema break is preferable while the tool is pre-alpha because it
avoids aliases and migration paths for representations that no longer match
the model. Current runtime names and CLI usage are documented in README and `docs/`.

## Intentionally excluded

- Treating a configured entry as a deduplicated server record.
- Multiple or overlapping local roots.
- Creating a new unmapped profile.
- A global or directory-scoped `use` setting.
- Guessing a profile or falling back to the first configured profile.
- Silently changing a profile's roots or endpoint.
- Storing credential values in profile configuration.
- Reading or migrating legacy runtime configuration and project schemas.
- Connecting to or deleting remote content when a profile is removed.
