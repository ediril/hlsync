"""SFTP over SSH, supplying the primitives of the shared remote transport."""

from __future__ import annotations

import os
import socket
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import paramiko

from hlsync.config import ProfileConfiguration
from hlsync.transport import (
    PathOperationError,
    RemoteChild,
    RemoteTransport,
    TransportError,
)

_BLOCK_SIZE = 32_768
_SECOND_NS = 1_000_000_000
# Failures that end the SSH session rather than one path operation.
_SESSION_ERRORS = (paramiko.SSHException, EOFError, socket.timeout, ConnectionError)


def _identity_files(host: str) -> list[str]:
    """IdentityFile entries ~/.ssh/config gives for the host, if present."""
    path = Path("~/.ssh/config").expanduser()
    if not path.is_file():
        return []
    try:
        config = paramiko.SSHConfig.from_path(os.fspath(path))
    except (OSError, paramiko.ssh_exception.ConfigParseError) as error:
        raise TransportError(f"could not read ~/.ssh/config: {error}") from error
    names = config.lookup(host).get("identityfile", [])
    files = (os.path.expanduser(name) for name in names)
    return [name for name in files if Path(name).is_file()]


class _NoCredentials(Exception):
    """No key, agent identity, or password was available to offer."""


def _connect_ssh(ssh: paramiko.SSHClient, host: str, **options: object) -> None:
    try:
        ssh.connect(host, **options)
    except paramiko.SSHException as error:
        # paramiko reports an empty set of credentials as a generic SSHException.
        if str(error) == "No authentication methods available":
            raise _NoCredentials("no SSH key, agent identity, or password") from error
        raise


@dataclass
class SFTPTransport(RemoteTransport):
    configuration: ProfileConfiguration
    timeout: float = 30.0

    protocol_name = "SFTP"

    def __post_init__(self) -> None:
        super().__post_init__()
        self._ssh: paramiko.SSHClient | None = None
        self._client: paramiko.SFTPClient | None = None

    @property
    def _connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        configuration = self.configuration
        username = os.environ.get(configuration.username_env)
        if username is None:
            raise TransportError(
                "missing credential environment variable(s): "
                f"{configuration.username_env}"
            )
        # SSH offers keys from the agent and ~/.ssh first; a password is optional.
        password = os.environ.get(configuration.password_env) or None
        host, port = configuration.host, configuration.port
        ssh = paramiko.SSHClient()
        known_hosts = Path("~/.ssh/known_hosts").expanduser()
        if known_hosts.is_file():
            try:
                ssh.load_host_keys(os.fspath(known_hosts))
            except (OSError, paramiko.SSHException) as error:
                raise TransportError(
                    f"could not read ~/.ssh/known_hosts: {error}"
                ) from error
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        known_name = host if port == 22 else f"[{host}]:{port}"
        if ssh.get_host_keys().lookup(known_name) is None:
            command = f"ssh {username}@{host}" if port == 22 else (
                f"ssh -p {port} {username}@{host}"
            )
            raise TransportError(
                f"{known_name} is not in ~/.ssh/known_hosts; run '{command}' once "
                "to verify and save the server's host key"
            )
        try:
            _connect_ssh(
                ssh,
                host,
                port=port,
                username=username,
                password=password,
                key_filename=_identity_files(host) or None,
                allow_agent=True,
                look_for_keys=True,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
            )
            client = ssh.open_sftp()
            client.get_channel().settimeout(self.timeout)
            self._missing_root = self._find_missing_root(client)
        except paramiko.BadHostKeyException as error:
            ssh.close()
            raise TransportError(
                f"the host key of {known_name} does not match ~/.ssh/known_hosts; "
                "update that entry only if the server's key changed on purpose"
            ) from error
        except (paramiko.AuthenticationException, _NoCredentials) as error:
            ssh.close()
            raise TransportError(
                f"SSH login failed for {username}@{host}: "
                f"{str(error).rstrip('.')}. HLSync offers "
                "keys from ssh-agent and ~/.ssh, and the password in "
                f"{configuration.password_env} when it is set."
            ) from error
        except (OSError, EOFError, paramiko.SSHException, TransportError) as error:
            ssh.close()
            if isinstance(error, TransportError):
                raise
            raise TransportError(
                f"could not open SFTP profile at {host}:{port}"
                f"{configuration.remote_root}: {error}"
            ) from error
        self._ssh, self._client = ssh, client

    def _find_missing_root(self, client: paramiko.SFTPClient) -> tuple[str, ...]:
        """Return the absent folders of the remote root, outermost first."""
        root = PurePosixPath(self.configuration.remote_root)
        for folder in (root, *root.parents):
            try:
                attributes = client.stat(folder.as_posix())
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(attributes.st_mode or 0):
                raise TransportError(
                    f"remote root '{root}' cannot be used: '{folder}' is not a folder"
                )
            return root.parts[len(folder.parts):]
        raise TransportError(f"remote root '{root}' has no existing folder above it")

    def close(self) -> None:
        client, ssh = self._client, self._ssh
        self._client = self._ssh = None
        try:
            if client is not None:
                client.close()
        finally:
            if ssh is not None:
                ssh.close()

    def _session_alive(self) -> bool:
        ssh_transport = self._ssh.get_transport() if self._ssh is not None else None
        return (
            ssh_transport is not None
            and ssh_transport.is_active()
            and self._client is not None
            and not self._client.sock.closed
        )

    @contextmanager
    def _failure(self, description: str, *, hint: str = "") -> Iterator[None]:
        try:
            yield
        except _SESSION_ERRORS as error:
            reason = str(error) or type(error).__name__
            raise TransportError(f"could not {description}: {reason}") from error
        except OSError as error:
            # A closed channel also surfaces as a plain OSError.
            if not self._session_alive():
                raise TransportError(f"could not {description}: {error}") from error
            raise PathOperationError(
                f"could not {description}: {error}{hint}"
            ) from error

    def _sftp(self) -> paramiko.SFTPClient:
        if self._client is None:
            raise TransportError("SFTP transport is not connected")
        return self._client

    def _remote(self, path: str) -> str:
        return (PurePosixPath(self.configuration.remote_root) / path).as_posix()

    def _list_children(
        self,
        directory: PurePosixPath,
        file_progress: Callable[[int, int], None] | None,
    ) -> list[RemoteChild]:
        del file_progress  # one request returns every entry's metadata
        children: list[RemoteChild] = []
        listing = self._sftp().listdir_attr(self._remote(directory.as_posix()))
        for attributes in listing:
            name = attributes.filename
            path = (directory / name).as_posix()
            mode = attributes.st_mode or 0
            if stat.S_ISDIR(mode):
                children.append(RemoteChild(name, "directory"))
            elif stat.S_ISLNK(mode):
                children.append(RemoteChild(name, "symlink"))
            elif stat.S_ISREG(mode):
                if attributes.st_size is None or attributes.st_mtime is None:
                    raise TransportError(
                        f"remote file metadata is incomplete for '{path}'"
                    )
                children.append(
                    RemoteChild(
                        name,
                        "file",
                        attributes.st_size,
                        int(attributes.st_mtime) * _SECOND_NS,
                        _SECOND_NS,
                    )
                )
            else:
                raise TransportError(f"unsupported remote entry type for '{path}'")
        return children

    def _store(
        self, path: str, source: BinaryIO, progress: Callable[[int], None] | None
    ) -> None:
        with self._sftp().open(self._remote(path), "wb") as remote:
            remote.set_pipelined(True)
            while block := source.read(_BLOCK_SIZE):
                remote.write(block)
                if progress is not None:
                    progress(len(block))

    def _size(self, path: str) -> int:
        size = self._sftp().stat(self._remote(path)).st_size
        if size is None:
            raise TransportError(f"missing remote size for '{path}'")
        return size

    def _set_modified(self, path: str, seconds: int) -> None:
        self._sftp().utime(self._remote(path), (seconds, seconds))

    def _read_modified(self, path: str) -> tuple[int, int]:
        modified = self._sftp().stat(self._remote(path)).st_mtime
        if modified is None:
            raise TransportError(f"missing remote modification time for '{path}'")
        return int(modified) * _SECOND_NS, _SECOND_NS

    def _rename(self, source: str, destination: str) -> None:
        self._sftp().rename(self._remote(source), self._remote(destination))

    def _delete_file(self, path: str) -> None:
        self._sftp().remove(self._remote(path))

    def _make_dir(self, path: str) -> None:
        self._sftp().mkdir(self._remote(path))

    def _remove_dir(self, path: str) -> None:
        self._sftp().rmdir(self._remote(path))

    def _retrieve(self, path: str, destination: BinaryIO) -> None:
        self._sftp().getfo(self._remote(path), destination)

    def _make_absolute_directory(self, path: str) -> None:
        self._sftp().mkdir(path)

    def _enter_root(self) -> None:
        """Paths are joined to the root, so there is no directory to enter."""
