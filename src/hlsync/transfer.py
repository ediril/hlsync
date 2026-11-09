from __future__ import annotations

import os
import queue
import stat
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from hlsync.comparison import ComparisonEntry, ComparisonPlan
from hlsync.snapshot import EntryKind, TreeEntry, TreeSnapshot
from hlsync.transport import PathOperationError, RemoteTransport, TransportError


class TransferError(RuntimeError):
    """Raised when a transfer plan cannot be executed safely."""


@dataclass(frozen=True)
class TransferIssue:
    path: str
    reason: str


@dataclass(frozen=True)
class TransferOperation:
    action: Literal["add", "update", "delete", "create"]
    path: str
    kind: EntryKind


TransferProgress = Callable[[TransferOperation | TransferIssue], None]


def _record_issue(
    issues: list[TransferIssue],
    issue: TransferIssue,
    progress: TransferProgress | None,
) -> None:
    issues.append(issue)
    if progress is not None:
        progress(issue)


@dataclass(frozen=True)
class TransferResult:
    plan: ComparisonPlan
    completed_paths: frozenset[str]
    issues: tuple[TransferIssue, ...] = ()
    not_started_count: int = 0

    @property
    def changed_count(self) -> int:
        return len(self.completed_paths)

    @property
    def unchanged_file_count(self) -> int:
        return sum(
            entry.action == "unchanged" and entry.local_kind == "file"
            for entry in self.plan.entries
        )

    @property
    def failed_count(self) -> int:
        return len(self.issues)

    @property
    def succeeded(self) -> bool:
        return not self.issues


def _entry_map(snapshot: TreeSnapshot) -> dict[str, TreeEntry]:
    return {entry.path: entry for entry in snapshot.entries}


def _preflight(plan: ComparisonPlan, local_root: Path, local: TreeSnapshot) -> None:
    conflicts = [entry for entry in plan.entries if entry.action == "conflict"]
    if conflicts:
        message = "transfer has unresolved conflict(s): " + ", ".join(
            entry.path for entry in conflicts
        )
        if any(entry.state == "destination-newer" for entry in conflicts):
            message += (
                "; destination files not older than their source are kept"
                " unless --force is given"
            )
        raise TransferError(message)
    local_entries = _entry_map(local)
    for entry in plan.entries:
        if entry.action not in {"upload", "replace-remote", "replace-local"}:
            continue
        expected = local_entries[entry.path]
        path = local_root / Path(*PurePosixPath(entry.path).parts)
        try:
            current = path.stat(follow_symlinks=False)
        except OSError as error:
            raise TransferError(
                f"could not validate local source '{path}': {error}"
            ) from error
        if not stat.S_ISREG(current.st_mode):
            raise TransferError(f"local source is no longer a file: {path}")
        if (
            current.st_size != expected.size
            or current.st_mtime_ns != expected.modified_ns
        ):
            raise TransferError(f"local source changed after snapshot: {path}")


def _remote_directories_to_create(
    plan: ComparisonPlan,
    remote: TreeSnapshot,
) -> tuple[str, ...]:
    existing = remote.listed_directories | {
        entry.path for entry in remote.entries if entry.kind == "directory"
    }
    required = {
        entry.path
        for entry in plan.entries
        if entry.action == "create-remote"
    }
    for entry in plan.entries:
        if entry.action not in {"upload", "replace-remote"}:
            continue
        parent = PurePosixPath(entry.path).parent
        while parent.parts:
            if parent.as_posix() not in existing:
                required.add(parent.as_posix())
            parent = parent.parent
    return tuple(
        sorted(
            required,
            key=lambda path: (len(PurePosixPath(path).parts), path),
        )
    )


def planned_transfer_operations(
    plan: ComparisonPlan,
    remote: TreeSnapshot,
) -> tuple[TransferOperation, ...]:
    """Return successful-path operations in their execution order."""
    if plan.direction == "pull":
        return tuple(
            TransferOperation("update", entry.path, "file")
            for entry in plan.entries
            if entry.action == "replace-local"
        )
    creations = tuple(
        TransferOperation("create", path, "directory")
        for path in _remote_directories_to_create(plan, remote)
    )
    uploads = tuple(
        TransferOperation(
            "add" if entry.action == "upload" else "update",
            entry.path,
            "file",
        )
        for entry in plan.entries
        if entry.action in {"upload", "replace-remote"}
    )
    deletions = tuple(
        entry for entry in plan.entries if entry.action == "delete-remote"
    )
    files = sorted(
        (entry for entry in deletions if entry.remote_kind != "directory"),
        key=lambda entry: entry.path,
    )
    directories = sorted(
        (entry for entry in deletions if entry.remote_kind == "directory"),
        key=lambda entry: (-len(PurePosixPath(entry.path).parts), entry.path),
    )
    deletes = tuple(
        TransferOperation("delete", entry.path, entry.remote_kind or "file")
        for entry in (*files, *directories)
    )
    return creations + uploads + deletes


def _push_files(
    plan: ComparisonPlan,
    local_root: Path,
    local: TreeSnapshot,
    transport: RemoteTransport,
    progress: TransferProgress | None,
    operations: tuple[TransferOperation, ...],
    dry_run: bool,
    byte_progress: Callable[[int], None] | None,
    upload_sessions: Sequence[RemoteTransport],
) -> tuple[set[str], list[TransferIssue], int]:
    """Create folders, upload files, then delete, stopping at the first failure.

    Returns the completed paths, the failure if one occurred, and how many
    planned operations were not started because of it.
    """
    local_entries = _entry_map(local)
    completed: set[str] = set()
    issues: list[TransferIssue] = []
    started = 0
    planned_creations = {
        entry.path
        for entry in plan.entries
        if entry.action == "create-remote"
    }
    display = threading.Lock()

    def fail(issue: TransferIssue) -> tuple[set[str], list[TransferIssue], int]:
        _record_issue(issues, issue, progress)
        return completed, issues, len(operations) - started

    for operation in (item for item in operations if item.action == "create"):
        started += 1
        try:
            if not dry_run:
                transport.make_directory(operation.path)
        except PathOperationError as error:
            return fail(TransferIssue(operation.path, str(error)))
        if progress is not None:
            progress(operation)
        if operation.path in planned_creations:
            completed.add(operation.path)

    def sent(byte_count: int) -> None:
        with display:
            byte_progress(byte_count)

    def upload(
        operation: TransferOperation, session: RemoteTransport
    ) -> TransferIssue | None:
        metadata = local_entries[operation.path]
        if metadata.size is None or metadata.modified_ns is None:
            raise TransferError(
                f"local file metadata is incomplete: {operation.path}"
            )
        path = local_root / Path(*PurePosixPath(operation.path).parts)
        try:
            if not dry_run:
                with path.open("rb") as source:
                    session.upload_file(
                        source,
                        operation.path,
                        size=metadata.size,
                        modified_ns=metadata.modified_ns,
                        replace=operation.action == "update",
                        byte_progress=sent if byte_progress is not None else None,
                    )
        except TransportError as error:
            return TransferIssue(operation.path, str(error))
        except OSError as error:
            return TransferIssue(
                operation.path, f"could not read local file '{path}': {error}"
            )
        return None

    uploads = tuple(item for item in operations if item.action in {"add", "update"})
    for operation, issue in _run_uploads(
        uploads, (transport, *upload_sessions), upload
    ):
        started += 1
        with display:
            if issue is not None:
                _record_issue(issues, issue, progress)
                continue
            completed.add(operation.path)
            if progress is not None:
                progress(operation)
    if issues:
        return completed, issues, len(operations) - started

    for operation in (item for item in operations if item.action == "delete"):
        started += 1
        try:
            if not dry_run:
                transport.delete_path(
                    operation.path,
                    is_directory=operation.kind == "directory",
                )
        except PathOperationError as error:
            return fail(TransferIssue(operation.path, str(error)))
        completed.add(operation.path)
        if progress is not None:
            progress(operation)
    return completed, issues, 0


def _run_uploads(
    uploads: tuple[TransferOperation, ...],
    sessions: tuple[RemoteTransport, ...],
    upload: Callable[[TransferOperation, RemoteTransport], TransferIssue | None],
):
    """Upload over every session at once and yield each outcome as it finishes.

    All files wait in one queue, and each worker session takes the next file as
    soon as it is free; the queue hands every file to exactly one worker. The
    first failure stops new uploads; uploads already running on other sessions
    finish and are yielded. An unexpected error is raised once every session
    has stopped.
    """
    pending: queue.SimpleQueue[TransferOperation] = queue.SimpleQueue()
    for operation in uploads:
        pending.put(operation)
    finished: queue.SimpleQueue[
        tuple[TransferOperation, TransferIssue | None | BaseException] | None
    ] = queue.SimpleQueue()
    stop = threading.Event()

    def work(session: RemoteTransport) -> None:
        try:
            while not stop.is_set():
                try:
                    operation = pending.get_nowait()
                except queue.Empty:
                    return
                try:
                    outcome = upload(operation, session)
                except BaseException as error:
                    stop.set()
                    finished.put((operation, error))
                    return
                if outcome is not None:
                    stop.set()
                finished.put((operation, outcome))
        finally:
            finished.put(None)

    workers = [
        threading.Thread(target=work, args=(session,), daemon=True)
        for session in sessions[: len(uploads)]
    ]
    for worker in workers:
        worker.start()
    error: BaseException | None = None
    try:
        remaining = len(workers)
        while remaining:
            item = finished.get()
            if item is None:
                remaining -= 1
                continue
            operation, outcome = item
            if isinstance(outcome, BaseException):
                error = error or outcome
                continue
            yield operation, outcome
    finally:
        stop.set()
        for worker in workers:
            worker.join()
    if error is not None:
        raise error


def _replace_local_file(
    root: Path,
    comparison: ComparisonEntry,
    local_entry: TreeEntry,
    remote_entry: TreeEntry,
    transport: RemoteTransport,
) -> None:
    destination = root / Path(*PurePosixPath(comparison.path).parts)
    try:
        mode = stat.S_IMODE(destination.stat(follow_symlinks=False).st_mode)
    except OSError as error:
        raise TransferError(
            f"could not inspect local destination '{destination}': {error}"
        ) from error
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.hlsync-pull-",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            transport.download_file(comparison.path, target)
            target.flush()
            os.fsync(target.fileno())
        actual_size = temporary.stat().st_size
        if actual_size != remote_entry.size:
            raise TransferError(
                f"download size mismatch for '{comparison.path}': expected "
                f"{remote_entry.size}, got {actual_size}"
            )
        os.chmod(temporary, mode)
        if remote_entry.modified_ns is None:
            raise TransferError(
                f"remote file timestamp is missing: {comparison.path}"
            )
        os.utime(
            temporary,
            ns=(remote_entry.modified_ns, remote_entry.modified_ns),
        )
        current = destination.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_size != local_entry.size
            or current.st_mtime_ns != local_entry.modified_ns
        ):
            raise TransferError(
                f"local destination changed during download: {destination}"
            )
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _pull_files(
    plan: ComparisonPlan,
    local_root: Path,
    local: TreeSnapshot,
    remote: TreeSnapshot,
    transport: RemoteTransport,
    progress: TransferProgress | None,
    operations: tuple[TransferOperation, ...],
) -> set[str]:
    completed: set[str] = set()
    local_entries = _entry_map(local)
    remote_entries = _entry_map(remote)
    entries = {entry.path: entry for entry in plan.entries}
    for operation in operations:
        entry = entries[operation.path]
        _replace_local_file(
            local_root,
            entry,
            local_entries[operation.path],
            remote_entries[operation.path],
            transport,
        )
        completed.add(operation.path)
        if progress is not None:
            progress(operation)
    return completed


def execute_transfer(
    plan: ComparisonPlan,
    *,
    local_root: Path,
    local: TreeSnapshot,
    remote: TreeSnapshot,
    transport: RemoteTransport,
    progress: TransferProgress | None = None,
    dry_run: bool = False,
    byte_progress: Callable[[int], None] | None = None,
    upload_sessions: Sequence[RemoteTransport] = (),
) -> TransferResult:
    if dry_run and plan.direction != "push":
        raise TransferError("dry run is supported only for push")
    _preflight(plan, local_root, local)
    operations = planned_transfer_operations(plan, remote)
    if plan.direction == "pull":
        completed = _pull_files(
            plan, local_root, local, remote, transport, progress, operations
        )
        return TransferResult(plan, frozenset(completed))
    completed, issues, not_started = _push_files(
        plan,
        local_root,
        local,
        transport,
        progress,
        operations,
        dry_run,
        byte_progress,
        upload_sessions,
    )
    return TransferResult(plan, frozenset(completed), tuple(issues), not_started)
