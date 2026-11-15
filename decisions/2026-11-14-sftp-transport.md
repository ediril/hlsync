# SFTP transport

Date: 2026-11-14

## Decision

HLSync supports SFTP as a second protocol beside FTPS. A profile's existing
`type` field selects it (`ftps` or `sftp`); the profile document gains no
fields, so the configuration version does not change.

One protocol-independent `RemoteTransport` base owns every guarantee: the
selected remote walk, artifact recovery, staged upload with size and timestamp
verification, backed-up replacement with restore, deletion, and missing-root
detection state. Each protocol supplies only connection handling and primitive
operations: list a folder, store, stat size, set and read modification time,
rename, delete, create and remove folders, and retrieve. Each protocol also
classifies its own errors into a path failure, after which the session remains
usable, or a session failure.

SFTP uses paramiko. Paths are joined to the remote root on the client; there is
no working directory. A listing returns each entry's type, size, and
whole-second modification time in one request. Timestamps are set with SETSTAT
and read back with STAT before installation, as with FTPS.

Login follows the SSH client model: ssh-agent identities, `IdentityFile`
entries that `~/.ssh/config` gives for the host, and default keys in `~/.ssh`.
The password variable is optional and is offered when set. The username
variable is required. Each protocol has its own default host, username, and
password variables (`PROD_SFTP_*` for SFTP), so one protocol's secret is never
offered to another protocol's server. Other `~/.ssh/config` options are not
applied, because the profile records host, port, and username explicitly.

Host keys are verified against `~/.ssh/known_hosts`. Unknown hosts and changed
keys are refused; HLSync never adds or updates host keys. The error names the
`ssh` command that verifies and saves the key.

Parallel uploads open one SSH connection per session, matching the FTPS
session model and its refusal handling.

## Rationale

SFTP is the standard file-transfer protocol on servers with SSH access and
avoids FTP's per-file metadata requests and separate data connections. Keeping
the staging, verification, and recovery rules in one base means a second
protocol cannot weaken them, and the existing FTPS tests exercise the shared
rules through FTPS primitives. Refusing unknown host keys gives SFTP the same
verified-server guarantee that certificate checking gives FTPS; trusting a key
on first use would accept an unverified server silently.

## Intentionally excluded

- Adding or updating entries in `~/.ssh/known_hosts`.
- Applying `~/.ssh/config` `HostName`, `Port`, `User`, `ProxyJump`, or other
  options beyond `IdentityFile`.
- Prompting for passwords or key passphrases; encrypted keys need ssh-agent.
- Running commands on the server, rsync, or server-side checksums.
- Several SFTP channels over one SSH connection.
- Server-specific rename extensions; installation uses the same backup and
  rename sequence as FTPS.
