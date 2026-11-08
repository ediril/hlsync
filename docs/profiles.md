# Profiles and mapping

[← HLSync README](../README.md)

A profile identifies one deployment target: protocol, host, port, remote root,
credential environment-variable names, and one local root. Multiple
profiles may use the same server. Credential values are never stored in
`~/.hlsync/configs.json`.

FTPS is the default and currently the only protocol. Override credential
variable names when creating a profile if needed:

```console
hlsync create staging \
  --host ftp.example.com \
  --remote-root /public_html/staging \
  --local-root /path/to/project \
  --username-env STAGING_FTPS_USERNAME \
  --password-env STAGING_FTPS_PASSWORD
```

HLSync stores the canonical absolute local root and maps every descendant to
the same relative path under the remote root. Roots may not overlap across
profiles. Remapping requires confirmation and defaults to no.

Use `map` to change either side after creation. Omit `--local-root` to use the
current directory; changing only the remote root preserves the local root:

```console
hlsync map staging --local-root /new/local/path
hlsync map staging --remote-root /new/remote/root
```

The normal workflow is to run HLSync inside a mapped root or one of its
descendants. The current directory selects the containing profile and relative
local scope automatically:

```console
hlsync profiles          # all profiles; * marks the current one
hlsync profile           # current profile name
hlsync profile --details # current profile details
hlsync profile staging   # verify and print a named profile
hlsync profile staging --details
hlsync root staging      # print the mapped local root only
hlsync connect            # verify FTPS, then disconnect
hlsync remove staging    # remove local configuration only
```

Outside every mapped root, `hlsync profile` reports that no profile is active
and suggests `hlsync PROFILE COMMAND`. Commands that require a profile need
that explicit profile prefix. Named and inferred lookups both require
`--details` for the full view.

Because `root` writes only the canonical path, it can be composed with the
shell when you want to switch directories:

```console
cd "$(hlsync root staging)"
```

An unqualified profile-aware command fails outside every mapped root. When you
intentionally need to operate from elsewhere—or override the profile inferred
from the current directory—put the profile before the command. The override
lasts for that command only and uses the selected profile's local root as its
working directory:

```console
hlsync staging list
hlsync staging diff templates
hlsync staging push templates -r
```

No profile selection is persisted between commands.
