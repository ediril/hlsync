"""Directory progress based on work discovered by the remote traversal."""

from __future__ import annotations

import os
import shutil
from pathlib import PurePosixPath
from typing import TextIO


class DirectoryReadProgress:
    """Status for remote reads.

    A transient status only redraws one terminal line and leaves no log or
    summary behind; the default also logs to redirected output and finishes
    with a directory count.
    """

    def __init__(self, output: TextIO, *, transient: bool = False) -> None:
        self.output = output
        self.terminal = output.isatty() and os.environ.get("TERM") != "dumb"
        self.transient = transient
        self.directory = "."
        self.counted = False
        self.completed = 0
        self.discovered = 1
        self.files: tuple[int, int] | None = None

    def _draw(self) -> None:
        directory = f"{self.directory}/"
        text = (
            f"  {self.completed}/{self.discovered} discovered directories read"
            f" · {directory}"
            if self.counted
            else f"  Reading {directory}"
        )
        if self.files is not None:
            read, listed = self.files
            text += f" · {read}/{listed} files"
        if self.terminal:
            width = max(1, shutil.get_terminal_size().columns - 1)
            print(f"\r\033[2K{text[:width]}", end="", file=self.output, flush=True)
        elif not self.transient:
            print(text, file=self.output, flush=True)

    def __enter__(self) -> DirectoryReadProgress:
        return self

    def reading(self, directory: PurePosixPath) -> None:
        self.directory = directory.as_posix()
        self.files = None
        self._draw()

    def counts(self, completed: int, discovered: int) -> None:
        self.counted = True
        self.completed = completed
        self.discovered = discovered
        if self.terminal:
            self._draw()

    def file_read(self, read: int, listed: int) -> None:
        self.files = (read, listed)
        if self.terminal:
            self._draw()

    def clear(self) -> None:
        if self.terminal:
            print("\r\033[2K", end="", file=self.output, flush=True)

    def message(self, message: str) -> None:
        self.clear()
        print(f"  {message}", file=self.output, flush=True)
        if self.terminal:
            self._draw()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.clear()
        if exc_type is None and not self.transient:
            print(
                f"  Read {self.completed}/{self.discovered} directories.",
                file=self.output, flush=True,
            )
