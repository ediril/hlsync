from __future__ import annotations

import ftplib
import os
import re
import ssl
from abc import ABC, abstractmethod
from calendar import timegm
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from hlsync.config import ProfileConfiguration
from hlsync.rules import RuleSet
from hlsync.selection import FileSelection
from hlsync.snapshot import EntryKind, SnapshotError, TreeEntry, TreeSnapshot


class TransportError(RuntimeError):
    """Raised when a remote transport cannot be used safely."""


class PathOperationError(TransportError):
    """Raised when one remote path fails but the session remains usable."""


_HLSYNC_ARTIFACT_NAME = re.compile(
    r"^\.(?P<destination>.+)\.hlsync-(?P<kind>upload|backup)-"
    r"(?P<token>[0-9a-f]{32})$"
)


@dataclass(frozen=True)
class _HLSyncArtifact:
    path: str
    destination: str
    kind: str


@dataclass(frozen=True)
class _ArtifactRecoveryPlan:
    projected: TreeSnapshot
    uploads_to_remove: tuple[str, ...]
    backups_to_remove: tuple[str, ...]
    backups_to_restore: tuple[tuple[str, str], ...]


def _hlsync_artifact(path: str) -> _HLSyncArtifact | None:
    remote = PurePosixPath(path)
    match = _HLSYNC_ARTIFACT_NAME.fullmatch(remote.name)
    if match is None:
        return None
    destination = remote.with_name(match.group("destination")).as_posix()
    return _HLSyncArtifact(path, destination, match.group("kind"))


def _parse_modify_timestamp(
    value: str,
    path: str,
    *,
    source: str,
) -> tuple[int, int]:
    base, separator, fraction = value.partition(".")
    if len(base) != 14 or not base.isdigit() or (
        separator and (not fraction or not fraction.isdigit())
    ):
        raise TransportError(
            f"invalid {source} timestamp {value!r} for '{path}'"
        )
    try:
        timestamp = datetime.strptime(base, "%Y%m%d%H%M%S")
    except ValueError as error:
        raise TransportError(
            f"invalid {source} timestamp {value!r} for '{path}'"
        ) from error
    fraction_digits = min(len(fraction), 9)
    fractional_ns = int(fraction[:9].ljust(9, "0")) if fraction else 0
    precision_ns = 10 ** (9 - fraction_digits) if fraction else 1_000_000_000
    return timegm(timestamp.timetuple()) * 1_000_000_000 + fractional_ns, precision_ns


def _parse_list_line(line: str) -> tuple[str, str] | None:
    """Return (name, kind) for a Unix LIST line, or None for '.', '..', totals."""
    if re.fullmatch(r"total \d+", line):
        return None
    fields = line.split(maxsplit=8)
    if len(fields) != 9 or not re.fullmatch(r"[-dl][rwxStTs-]{9}[+@.]?", fields[0]):
        raise TransportError(f"unsupported LIST entry: {line!r}")
    name = fields[8]
    kind = fields[0][0]
    if kind == "l":
        name = name.split(" -> ", 1)[0]
    if name in {".", ".."}:
        return None
    if not name or "/" in name or "\r" in name or "\n" in name:
        raise TransportError(f"invalid name in remote listing: {name!r}")
    return name, kind


def _parse_mlsd_modify(value: str, path: str) -> tuple[int, int]:
    return _parse_modify_timestamp(value, path, source="MLSD modify")


def _parse_mdtm_response(response: str, path: str) -> tuple[int, int]:
    code, separator, value = response.partition(" ")
    if code != "213" or not separator or not value.strip():
        raise TransportError(
            f"invalid MDTM response for '{path}': {response}"
        )
    return _parse_modify_timestamp(value.strip(), path, source="MDTM")


def _relative_remote_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise TransportError(f"remote operation path must be relative: {value!r}")
    return path.as_posix()


def _format_utc(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y%m%d%H%M%S")


@dataclass(frozen=True)
class RemoteChild:
    """One entry of a remote folder listing, before rules are applied."""

    name: str
    kind: EntryKind
    size: int | None = None
    modified_ns: int | None = None
    precision_ns: int | None = None


class RemoteTransport(ABC):
    """Protocol-independent remote tree, staged installation, and recovery.

    Subclasses connect and supply primitive operations on paths relative to the
    remote root; every guarantee built on those primitives lives here: the
    selected walk, artifact recovery, verified staging, and backed-up
    replacement.
    """

    protocol_name = "remote"
    # Whether each file's size and time need separate requests while listing.
    reads_file_metadata_separately = False
    # Server software worth naming to the user, when it limits listing speed.
    server_software: str | None = None

    configuration: ProfileConfiguration

    def __post_init__(self) -> None:
        # The absolute remote root, resolved from the login folder on connect.
        self.remote_root = self.configuration.remote_root
        # Folders of the remote root that do not exist yet, outermost first.
        self._missing_root: tuple[str, ...] = ()

    # -- connection and primitives supplied by each protocol ----------------

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def _connected(self) -> bool: ...

    @abstractmethod
    def _failure(
        self, description: str, *, hint: str = ""
    ) -> AbstractContextManager[None]:
        """Convert protocol errors into PathOperationError or TransportError."""

    @abstractmethod
    def _list_children(
        self,
        directory: PurePosixPath,
        file_progress: Callable[[int, int], None] | None,
    ) -> list[RemoteChild]: ...

    @abstractmethod
    def _store(
        self, path: str, source: BinaryIO, progress: Callable[[int], None] | None
    ) -> None: ...

    @abstractmethod
    def _size(self, path: str) -> int: ...

    @abstractmethod
    def _set_modified(self, path: str, seconds: int) -> None: ...

    @abstractmethod
    def _read_modified(self, path: str) -> tuple[int, int]:
        """Return (modified_ns, precision_ns) as the server reports them."""

    @abstractmethod
    def _rename(self, source: str, destination: str) -> None: ...

    @abstractmethod
    def _delete_file(self, path: str) -> None: ...

    @abstractmethod
    def _make_dir(self, path: str) -> None: ...

    @abstractmethod
    def _remove_dir(self, path: str) -> None: ...

    @abstractmethod
    def _retrieve(self, path: str, destination: BinaryIO) -> None: ...

    @abstractmethod
    def _make_absolute_directory(self, path: str) -> None: ...

    @abstractmethod
    def _enter_root(self) -> None: ...

    def _stage(self, step: str) -> str:
        return {
            "store": "upload staging file",
            "size": "verify upload size",
            "set_time": "set timestamp",
            "read_time": "verify timestamp",
        }[step]

    @property
    def _timestamp_hint(self) -> str:
        return ""

    # -- shared protocol -----------------------------------------------------

    @property
    def missing_remote_root(self) -> bool:
        return bool(self._missing_root)

    def _resolve_root(self, login_folder: str) -> str:
        root = PurePosixPath(self.configuration.remote_root)
        if root.is_absolute():
            return root.as_posix()
        return (PurePosixPath(login_folder) / root).as_posix()

    def _ready(self) -> None:
        if self._missing_root:
            # Until the root exists, relative paths would resolve elsewhere.
            raise TransportError(f"remote root '{self.remote_root}' does not exist")
        if not self._connected:
            raise TransportError(f"{self.protocol_name} transport is not connected")

    def create_remote_root(self) -> None:
        """Create each missing folder of the remote root, then enter it."""
        if not self._connected:
            raise TransportError(f"{self.protocol_name} transport is not connected")
        root = PurePosixPath(self.remote_root)
        folder = PurePosixPath(*root.parts[: len(root.parts) - len(self._missing_root)])
        for name in self._missing_root:
            folder /= name
            with self._failure(f"create remote root folder '{folder}'"):
                self._make_absolute_directory(folder.as_posix())
        with self._failure(f"enter created remote root '{root}'"):
            self._enter_root()
        self._missing_root = ()

    def snapshot(
        self,
        rules: RuleSet,
        selector: FileSelection | None = None,
        *,
        include_excluded: bool = False,
        traverse_excluded: bool = False,
        artifact_recovery: Callable[[str], None] | None = None,
        artifact_preview: Callable[[str], None] | None = None,
        directory_progress: Callable[[PurePosixPath], None] | None = None,
        directory_counts: Callable[[int, int], None] | None = None,
        file_progress: Callable[[int, int], None] | None = None,
    ) -> TreeSnapshot:
        if not self._connected:
            raise TransportError(f"{self.protocol_name} transport is not connected")
        entries: list[TreeEntry] = []
        listed_directories: set[str] = set()
        completed_directories = 0
        discovered_directories = 1
        if directory_counts is not None:
            directory_counts(0, 1)

        def walk(relative_directory: PurePosixPath) -> None:
            nonlocal completed_directories, discovered_directories
            if directory_progress is not None:
                directory_progress(relative_directory)
            listing = self.list_directory(
                relative_directory, rules, file_progress=file_progress
            )
            if relative_directory.parts:
                listed_directories.add(relative_directory.as_posix())
            if artifact_recovery is not None:
                recoveries = self._recover_artifacts(listing, selector, rules)
                for recovery in recoveries:
                    artifact_recovery(recovery)
                if recoveries:
                    listing = self.list_directory(
                        relative_directory, rules, file_progress=file_progress
                    )
            elif artifact_preview is not None:
                recovery = self._plan_artifact_recovery(listing, selector, rules)
                for path in recovery.uploads_to_remove:
                    artifact_preview(f"Would remove abandoned upload '{path}'.")
                for path in recovery.backups_to_remove:
                    artifact_preview(f"Would remove old backup '{path}'.")
                for _, destination in recovery.backups_to_restore:
                    artifact_preview(
                        f"Would restore interrupted replacement '{destination}'."
                    )
                listing = recovery.projected
            descendants: list[PurePosixPath] = []
            for entry in listing.entries:
                relative_path = entry.path
                relative = PurePosixPath(relative_path)
                kind = entry.kind
                excluded = entry.excluded
                visible = not excluded or include_excluded
                selected = visible and (
                    selector is None or selector.matches(relative_path)
                )
                if selected:
                    entries.append(entry)
                selection_may_descend = (
                    selector is None
                    or selector.may_match_descendant(relative_path)
                )
                local_exclusion_may_descend = (
                    traverse_excluded
                    or not excluded
                    or rules.may_include_descendant(relative_path, target="local")
                )
                if (
                    kind == "directory"
                    and selection_may_descend
                    and local_exclusion_may_descend
                    and not entry.remote_excluded
                ):
                    descendants.append(relative)
            discovered_directories += len(descendants)
            completed_directories += 1
            if directory_counts is not None:
                directory_counts(completed_directories, discovered_directories)
            for descendant in descendants:
                walk(descendant)

        walk(PurePosixPath())
        return TreeSnapshot(tuple(entries), frozenset(listed_directories))

    def list_directory(
        self,
        relative_directory: PurePosixPath,
        rules: RuleSet,
        *,
        file_progress: Callable[[int, int], None] | None = None,
    ) -> TreeSnapshot:
        """List one folder as tree entries with local and remote exclusions.

        When a server needs separate requests per file, file_progress receives
        (files read, files listed) after each one.
        """
        if self._missing_root:
            return TreeSnapshot()
        self._ready()
        display = relative_directory.as_posix()
        with self._failure(f"list remote directory '{display}'"):
            children = sorted(
                self._list_children(relative_directory, file_progress),
                key=lambda child: child.name,
            )
        entries: list[TreeEntry] = []
        for child in children:
            if not child.name or "/" in child.name or child.name in {".", ".."}:
                raise TransportError(f"invalid name in remote listing: {child.name!r}")
            relative_path = (relative_directory / child.name).as_posix()
            directory = child.kind == "directory"
            excluded = rules.excludes(
                relative_path, target="local", is_directory=directory
            )
            remote_excluded = rules.excludes(
                relative_path, target="remote", is_directory=directory
            )
            try:
                entries.append(
                    TreeEntry(
                        relative_path,
                        child.kind,
                        size=child.size,
                        modified_ns=child.modified_ns,
                        timestamp_precision_ns=child.precision_ns,
                        excluded=excluded,
                        remote_excluded=remote_excluded,
                    )
                )
            except SnapshotError as error:
                raise TransportError(
                    f"invalid remote file metadata for '{relative_path}': {error}"
                ) from error
        return TreeSnapshot(tuple(entries))

    def make_directory(self, relative_path: str) -> None:
        path = _relative_remote_path(relative_path)
        self._ready()
        with self._failure(f"create remote directory '{path}'"):
            self._make_dir(path)

    def _plan_artifact_recovery(
        self,
        listing: TreeSnapshot,
        selector: FileSelection | None,
        rules: RuleSet,
    ) -> _ArtifactRecoveryPlan:
        entries = {entry.path: entry for entry in listing.entries}
        artifacts = tuple(
            artifact
            for path in sorted(entries)
            for artifact in (_hlsync_artifact(path),)
            if artifact is not None
            and (selector is None or selector.matches(artifact.destination))
        )
        for artifact in artifacts:
            if entries[artifact.path].kind != "file":
                raise TransportError(
                    f"reserved HLSync artifact is not a file: '{artifact.path}'"
                )

        uploads = tuple(
            artifact.path for artifact in artifacts if artifact.kind == "upload"
        )
        projected = dict(entries)
        for path in uploads:
            projected.pop(path)

        backups_by_destination: dict[str, list[_HLSyncArtifact]] = {}
        for artifact in artifacts:
            if artifact.kind == "backup":
                backups_by_destination.setdefault(
                    artifact.destination,
                    [],
                ).append(artifact)
        obsolete_backups: list[str] = []
        restorations: list[tuple[str, str]] = []
        for destination, backups in sorted(backups_by_destination.items()):
            if destination not in entries and len(backups) > 1:
                names = ", ".join(backup.path for backup in backups)
                raise TransportError(
                    f"multiple HLSync backups require manual recovery for "
                    f"'{destination}': {names}"
                )
            if destination in entries:
                for backup in backups:
                    projected.pop(backup.path)
                    obsolete_backups.append(backup.path)
                continue
            backup = backups[0]
            projected.pop(backup.path)
            source = entries[backup.path]
            projected[destination] = TreeEntry(
                destination,
                "file",
                size=source.size,
                modified_ns=source.modified_ns,
                timestamp_precision_ns=source.timestamp_precision_ns,
                excluded=rules.excludes(destination, target="local"),
                remote_excluded=rules.excludes(destination, target="remote"),
            )
            restorations.append((backup.path, destination))
        return _ArtifactRecoveryPlan(
            TreeSnapshot(tuple(projected[path] for path in sorted(projected))),
            uploads,
            tuple(obsolete_backups),
            tuple(restorations),
        )

    def _recover_artifacts(
        self,
        listing: TreeSnapshot,
        selector: FileSelection | None,
        rules: RuleSet,
    ) -> tuple[str, ...]:
        recovery = self._plan_artifact_recovery(listing, selector, rules)
        messages: list[str] = []
        for path in recovery.uploads_to_remove:
            self.delete_path(path, is_directory=False)
            messages.append(f"Removed abandoned upload '{path}'.")
        for path in recovery.backups_to_remove:
            self.delete_path(path, is_directory=False)
            messages.append(f"Removed old backup '{path}'.")
        for backup, destination in recovery.backups_to_restore:
            self._ready()
            with self._failure(
                f"restore HLSync backup '{backup}' to '{destination}'"
            ):
                self._rename(backup, destination)
            messages.append(f"Restored interrupted replacement '{destination}'.")
        return tuple(messages)

    def upload_file(
        self,
        local_path: BinaryIO,
        relative_path: str,
        *,
        size: int,
        modified_ns: int,
        replace: bool,
        byte_progress: Callable[[int], None] | None = None,
    ) -> None:
        """Stage beside the destination, verify size and time, then install.

        A replaced file is renamed to a backup first and restored if the
        installation rename fails.
        """
        path = _relative_remote_path(relative_path)
        self._ready()
        remote = PurePosixPath(path)
        token = uuid4().hex
        temporary = str(remote.with_name(f".{remote.name}.hlsync-upload-{token}"))
        backup = str(remote.with_name(f".{remote.name}.hlsync-backup-{token}"))
        seconds = modified_ns // 1_000_000_000

        def discard(candidate: str) -> None:
            try:
                with self._failure(f"discard '{candidate}'"):
                    self._delete_file(candidate)
            except TransportError:
                pass

        try:
            with self._failure(f"{self._stage('store')} for '{path}'"):
                self._store(temporary, local_path, byte_progress)
            with self._failure(f"{self._stage('size')} for '{path}'"):
                uploaded_size = self._size(temporary)
            if uploaded_size != size:
                raise TransportError(
                    f"remote upload size mismatch for '{path}': "
                    f"expected {size}, got {uploaded_size}"
                )
            with self._failure(
                f"{self._stage('set_time')} for '{path}'", hint=self._timestamp_hint
            ):
                self._set_modified(temporary, seconds)
            with self._failure(f"{self._stage('read_time')} for '{path}'"):
                remote_modified_ns, remote_precision_ns = self._read_modified(
                    temporary
                )
            precision_ns = max(remote_precision_ns, 1_000_000_000)
            if (
                remote_modified_ns // precision_ns
                != seconds * 1_000_000_000 // precision_ns
            ):
                raise TransportError(
                    f"remote modification time verification failed for "
                    f"'{path}': expected {_format_utc(seconds)}, got "
                    f"{_format_utc(remote_modified_ns // 1_000_000_000)}"
                )
            current_source = os.fstat(local_path.fileno())
            if (
                current_source.st_size != size
                or current_source.st_mtime_ns != modified_ns
            ):
                raise TransportError(
                    f"local source changed while staging remote file '{path}'"
                )
        except TransportError:
            discard(temporary)
            raise

        install = f"install remote file '{path}'"
        if not replace:
            try:
                with self._failure(install):
                    self._rename(temporary, path)
            except TransportError:
                discard(temporary)
                raise
            return

        try:
            with self._failure(f"stage replacement of remote file '{path}'"):
                self._rename(path, backup)
        except TransportError:
            discard(temporary)
            raise
        try:
            with self._failure(install):
                self._rename(temporary, path)
        except TransportError as error:
            discard(temporary)
            try:
                with self._failure(f"restore its backup '{backup}'"):
                    self._rename(backup, path)
            except TransportError as restore_error:
                raise TransportError(f"{error}; {restore_error}") from error
            raise type(error)(f"{error}; its prior version was restored") from error
        try:
            with self._failure(f"remove backup '{backup}'"):
                self._delete_file(backup)
        except TransportError as error:
            raise TransportError(
                f"installed remote file '{path}', but {error}"
            ) from error

    def download_file(self, relative_path: str, destination: BinaryIO) -> None:
        path = _relative_remote_path(relative_path)
        self._ready()
        with self._failure(f"download remote file '{path}'"):
            self._retrieve(path, destination)

    def delete_path(self, relative_path: str, *, is_directory: bool) -> None:
        path = _relative_remote_path(relative_path)
        self._ready()
        with self._failure(f"delete remote path '{path}'"):
            if is_directory:
                self._remove_dir(path)
            else:
                self._delete_file(path)

    def __enter__(self) -> RemoteTransport:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass
class ExplicitFTPSTransport(RemoteTransport):
    configuration: ProfileConfiguration
    timeout: float = 30.0
    ssl_context: ssl.SSLContext | None = None

    protocol_name = "FTPS"

    def __post_init__(self) -> None:
        super().__post_init__()
        self._client: ftplib.FTP_TLS | None = None
        self.lists_with_mlsd = True
        self.vsftpd = False
        self._timestamp_command = "MFMT"

    @property
    def reads_file_metadata_separately(self) -> bool:  # type: ignore[override]
        return not self.lists_with_mlsd

    @property
    def server_software(self) -> str | None:  # type: ignore[override]
        return "vsFTPd" if self.vsftpd else None

    @property
    def _connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        username = os.environ.get(self.configuration.username_env)
        password = os.environ.get(self.configuration.password_env)
        missing = [
            name
            for name, value in (
                (self.configuration.username_env, username),
                (self.configuration.password_env, password),
            )
            if value is None
        ]
        if missing:
            raise TransportError(
                f"missing credential environment variable(s): {', '.join(missing)}"
            )

        client = ftplib.FTP_TLS(
            context=self.ssl_context or ssl.create_default_context(),
            timeout=self.timeout,
        )
        try:
            client.connect(self.configuration.host, self.configuration.port)
            client.auth()
            client.login(username, password)
            client.prot_p()
            self.remote_root = self._resolve_root(client.pwd())
            features = client.sendcmd("FEAT")
            advertised = {
                line.strip().upper().split(" ", 1)[0]
                for line in features.splitlines()
            }
            self.vsftpd = "vsftpd" in client.getwelcome().lower()
            self._timestamp_command = (
                "MDTM" if "MFMT" not in advertised and self.vsftpd else "MFMT"
            )
            self.lists_with_mlsd = any(
                line.strip().upper().split(" ", 1)[0] in {"MLST", "MLSD"}
                for line in features.splitlines()
            )
            try:
                client.cwd(self.remote_root)
            except ftplib.error_perm as error:
                self._missing_root = self._find_missing_root(client, error)
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            try:
                client.close()
            finally:
                raise TransportError(
                    f"could not open explicit FTPS profile at "
                    f"{self.configuration.host}:{self.configuration.port}"
                    f"{self.configuration.remote_root}: {error}"
                ) from error
        self._client = client

    def _find_missing_root(
        self, client: ftplib.FTP_TLS, refusal: ftplib.error_perm
    ) -> tuple[str, ...]:
        """Return the absent folders of the remote root, outermost first.

        The nearest enterable ancestor must list no entry for the next folder;
        an entry there that cannot be entered keeps the original refusal.
        """
        root = PurePosixPath(self.remote_root)
        for ancestor in root.parents:
            try:
                client.cwd(ancestor.as_posix())
            except ftplib.error_perm:
                continue
            missing = root.parts[len(ancestor.parts):]
            if missing[0] in self._names_in_working_directory(client):
                raise refusal
            return missing
        raise refusal

    def _names_in_working_directory(self, client: ftplib.FTP_TLS) -> set[str]:
        if self.lists_with_mlsd:
            return {name for name, _ in client.mlsd(facts=["type"])}
        lines: list[str] = []
        client.retrlines("LIST -a", lines.append)
        return {
            parsed[0] for parsed in map(_parse_list_line, lines) if parsed is not None
        }

    def close(self) -> None:
        if self._client is None:
            return
        client, self._client = self._client, None
        try:
            client.quit()
        except (OSError, ftplib.Error):
            client.close()

    @contextmanager
    def _failure(self, description: str, *, hint: str = "") -> Iterator[None]:
        try:
            yield
        except ftplib.error_perm as error:
            raise PathOperationError(
                f"could not {description}: {error}{hint}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            raise TransportError(f"could not {description}: {error}") from error

    def _stage(self, step: str) -> str:
        return {
            "store": "upload staging file (STOR)",
            "size": "verify upload size (SIZE)",
            "set_time": f"set timestamp ({self._timestamp_command})",
            "read_time": "verify timestamp (MDTM)",
        }[step]

    @property
    def _timestamp_hint(self) -> str:
        if self._timestamp_command != "MDTM":
            return ""
        return ". Check mdtm_write and file permissions on the FTP server."

    def _ftp(self) -> ftplib.FTP_TLS:
        if self._client is None:
            raise TransportError("FTPS transport is not connected")
        return self._client

    def _list_children(
        self,
        directory: PurePosixPath,
        file_progress: Callable[[int, int], None] | None,
    ) -> list[RemoteChild]:
        remote_directory = directory.as_posix()
        if remote_directory == ".":
            remote_directory = ""
        listed = (
            self._ftp().mlsd(remote_directory, facts=["type", "size", "modify"])
            if self.lists_with_mlsd
            else self._list_facts(directory, file_progress)
        )
        children: list[RemoteChild] = []
        for name, facts in listed:
            entry_type = facts.get("type", "").lower()
            if entry_type in {"cdir", "pdir"}:
                continue
            relative_path = (directory / name).as_posix()
            if entry_type == "dir":
                children.append(RemoteChild(name, "directory"))
                continue
            if entry_type.startswith("os.unix=slink"):
                children.append(RemoteChild(name, "symlink"))
                continue
            if entry_type != "file":
                raise TransportError(
                    f"unsupported remote entry type {entry_type!r} "
                    f"for '{relative_path}'"
                )
            size_value = facts.get("size")
            modified_value = facts.get("modify")
            if size_value is None or modified_value is None:
                raise TransportError(
                    f"remote file metadata is incomplete for '{relative_path}'"
                )
            try:
                size = int(size_value)
            except ValueError as error:
                raise TransportError(
                    f"invalid MLSD size {size_value!r} for '{relative_path}'"
                ) from error
            modified_ns, precision_ns = _parse_mlsd_modify(
                modified_value, relative_path
            )
            children.append(
                RemoteChild(name, "file", size, modified_ns, precision_ns)
            )
        return children

    def _list_facts(
        self,
        directory: PurePosixPath,
        file_progress: Callable[[int, int], None] | None,
    ) -> list[tuple[str, dict[str, str]]]:
        client = self._ftp()
        lines: list[str] = []
        # Keep options separate from paths; servers disagree on LIST -a PATH.
        previous = client.pwd()
        client.cwd(f"./{directory.as_posix()}")
        try:
            client.retrlines("LIST -a", lines.append)
        finally:
            try:
                client.cwd(previous)
            except (OSError, ftplib.Error) as error:
                client.close()
                self._client = None
                raise TransportError(
                    "could not restore remote working directory"
                ) from error
        children: list[tuple[str, dict[str, str]]] = []
        client.voidcmd("TYPE I")
        files_listed = sum(1 for line in lines if line.startswith("-"))
        files_read = 0
        for line in lines:
            parsed = _parse_list_line(line)
            if parsed is None:
                continue
            name, kind = parsed
            facts = {"type": {"d": "dir", "-": "file", "l": "OS.unix=slink"}[kind]}
            if kind == "-":
                remote_path = f"./{(directory / name).as_posix()}"
                size = client.size(remote_path)
                if size is None:
                    raise TransportError(f"missing remote size for '{name}'")
                response = client.sendcmd(f"MDTM {remote_path}")
                _parse_mdtm_response(response, remote_path)
                facts.update(size=str(size), modify=response.partition(" ")[2].strip())
                files_read += 1
                if file_progress is not None:
                    file_progress(files_read, files_listed)
            children.append((name, facts))
        return children

    def _store(
        self, path: str, source: BinaryIO, progress: Callable[[int], None] | None
    ) -> None:
        callback = (
            (lambda block: progress(len(block))) if progress is not None else None
        )
        self._ftp().storbinary(f"STOR {path}", source, callback=callback)

    def _size(self, path: str) -> int:
        size = self._ftp().size(path)
        if size is None:
            raise TransportError(f"missing remote size for '{path}'")
        return size

    def _set_modified(self, path: str, seconds: int) -> None:
        response = self._ftp().sendcmd(
            f"{self._timestamp_command} {_format_utc(seconds)} {path}"
        )
        if len(response) < 3 or not response[:3].isdigit() or response[0] != "2":
            raise ftplib.error_reply(response)

    def _read_modified(self, path: str) -> tuple[int, int]:
        return _parse_mdtm_response(self._ftp().sendcmd(f"MDTM {path}"), path)

    def _rename(self, source: str, destination: str) -> None:
        self._ftp().rename(source, destination)

    def _delete_file(self, path: str) -> None:
        self._ftp().delete(path)

    def _make_dir(self, path: str) -> None:
        self._ftp().mkd(path)

    def _remove_dir(self, path: str) -> None:
        self._ftp().rmd(path)

    def _retrieve(self, path: str, destination: BinaryIO) -> None:
        self._ftp().retrbinary(f"RETR {path}", destination.write)

    def _make_absolute_directory(self, path: str) -> None:
        self._ftp().mkd(path)

    def _enter_root(self) -> None:
        self._ftp().cwd(self.remote_root)
