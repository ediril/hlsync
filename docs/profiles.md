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

`--host` defaults to the `PROD_FTPS_HOST` environment variable, and
`-r` is short for `--remote-root`. With the host set in your shell, a profile
needs only a name and a remote root:

```console
export PROD_FTPS_HOST=ftp.example.com
hlsync create staging -r /public_html/staging
```

`create` copies the host into the profile and names it in its output, so later
changes to `PROD_FTPS_HOST` do not affect existing profiles.

HLSync stores the canonical absolute local root and maps every descendant to
the same relative path under the remote root. Roots may not overlap across
profiles. Remapping requires confirmation and defaults to no.

The remote root does not need to exist yet. `connect`, `diff`, and
`push --dry` report `Remote root /public_html/staging does not exist yet; push
will create it.` and treat the remote as empty, so check that path for typos.
`push` then creates every missing folder of the root, such as both `staging/`
and a missing parent, before uploading. A root path that exists but cannot be
entered, such as a file or a folder without permission, still fails to connect.

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
hlsync cd staging        # change to it (after a one-time hlsync setup)
hlsync connect            # verify FTPS, then disconnect
hlsync remove staging    # remove local configuration only
```

Outside every mapped root, `hlsync profile` reports that no profile is active
and suggests `hlsync PROFILE COMMAND`. Commands that require a profile need
that explicit profile prefix. Named and inferred lookups both require
`--details` for the full view.

To switch to a profile's folder, run `hlsync setup` once. It adds a small
`hlsync` shell function to `~/.zshrc` or `~/.bashrc`, chosen from `$SHELL`.
Open a new terminal, and then:

```console
hlsync cd staging   # change to the staging profile's local root
hlsync cd           # back to the current profile's root from a subfolder
```

A program cannot change its shell's directory, so `cd` needs that function;
without it, `hlsync cd` explains how to run `setup`. The function only handles
`hlsync cd`; every other command runs `hlsync` unchanged. Running `setup` again
updates the function in place, and a symlinked startup file stays a symlink.
Without setup, `root` prints only the path, so `cd "$(hlsync root staging)"`
also works.

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
