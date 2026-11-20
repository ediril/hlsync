# Setting up a server for SFTP

This guide prepares an Ubuntu server running OpenSSH for HLSync SFTP profiles.
It creates one `deploy` account with key login. Each site is a folder in that
account's home folder, and the first push creates the folder, so a new site
needs no work on the server.

Replace `HOST` with the server's hostname or IP address, and `admin` with an
account that can run `sudo`. Use the same `HOST` everywhere: `~/.ssh/config`,
`~/.ssh/known_hosts`, and the profile match only that exact string.

## 1. Create the deploy account (server)

```console
sudo adduser --disabled-password --gecos "" --home /srv/hlsync deploy
sudo chmod 755 /srv/hlsync
grep -i '^subsystem' /etc/ssh/sshd_config
```

- `/srv/hlsync` is the account's home and holds every site. Any folder works.
- OpenSSH refuses key login when the home folder is writable by group or
  others. Mode `755` satisfies that and lets a web server read the sites.
- The last command must print a `Subsystem sftp` line. Ubuntu enables it by
  default.

To move an existing account's home instead, run
`sudo usermod -d /srv/hlsync deploy`, make `deploy` the owner of the folder, and
move its `.ssh` folder into it.

## 2. Create a deploy key (your computer)

```console
ssh-keygen -t ed25519 -f ~/.ssh/hlsync_deploy -C hlsync-deploy
```

HLSync cannot ask for a passphrase. If you give the key one, add it to
ssh-agent. On macOS this also stores the passphrase in the keychain:

```console
ssh-add --apple-use-keychain ~/.ssh/hlsync_deploy
```

After a restart, run `ssh-add --apple-load-keychain`, or `ssh` to the server
once, before you run `hlsync`.

## 3. Install the public key (your computer)

Log in with your admin account and append the key to `deploy`'s
`authorized_keys`:

```console
ssh admin@HOST 'sudo install -d -m 700 -o deploy -g deploy ~deploy/.ssh &&
  sudo tee -a ~deploy/.ssh/authorized_keys >/dev/null &&
  sudo chown deploy:deploy ~deploy/.ssh/authorized_keys &&
  sudo chmod 600 ~deploy/.ssh/authorized_keys' < ~/.ssh/hlsync_deploy.pub
```

## 4. Name the key for the server (your computer)

Add this to `~/.ssh/config`. HLSync reads `IdentityFile` from it:

```text
Host HOST
  IdentityFile ~/.ssh/hlsync_deploy
```

Once a host has an `IdentityFile` line, `ssh` no longer tries your default keys,
such as `~/.ssh/id_ed25519`, for that host. If you also log in to the server
as another account with a default key, list that key too, or that login falls
back to asking for a password:

```text
Host HOST
  IdentityFile ~/.ssh/hlsync_deploy
  IdentityFile ~/.ssh/id_ed25519
```

## 5. Verify the host key (your computer)

HLSync connects only to servers listed in `~/.ssh/known_hosts`. Log in once
with `ssh` to check and save the server's key:

```console
ssh deploy@HOST pwd
```

Before you answer `yes`, compare the fingerprint with the output of
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server. The command
prints `/srv/hlsync` when the login works.

## 6. Create a profile (your computer)

Run this in the site's local folder:

```console
export PROD_SFTP_HOST=HOST
export PROD_SFTP_USERNAME=deploy
hlsync create blog --protocol sftp -r blog
hlsync connect
hlsync push
```

`-r blog` is relative, so it resolves to `/srv/hlsync/blog`. `connect` reports
that the folder does not exist yet, and the first push creates it. Repeat
`hlsync create` with another name and folder for each site.

Leave `PROD_SFTP_PASSWORD` unset. `deploy` logs in with the key and has no
password.

> **Warning:** Do not use `-r .`. It deploys into the home folder itself, and
> `push -p` then deletes `.ssh/authorized_keys`, which locks the account out.

See [SFTP profiles](profiles.md#sftp-profiles) for how HLSync logs in and which
variables it reads.
