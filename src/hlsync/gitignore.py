"""Repository-scoped Git ignores, loaded lazily for profile-relative paths."""

from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec


class GitIgnores:
    def __init__(self, root: Path) -> None:
        self.root = next(
            (
                directory
                for directory in (root, *root.parents)
                if (directory / ".git").is_dir() or (directory / ".git").is_file()
            ),
            root,
        )
        self._profile_prefix = root.relative_to(self.root)
        self._lines: dict[PurePosixPath, tuple[str, ...]] = {}
        self._specs: dict[PurePosixPath, GitIgnoreSpec] = {}

    def _read(self, directory: PurePosixPath) -> tuple[str, ...]:
        if directory not in self._lines:
            source = self.root.joinpath(*directory.parts, ".gitignore")
            # Like Git, do not follow symlinked ignore files.
            if source.is_symlink():
                lines: tuple[str, ...] = ()
            else:
                try:
                    lines = tuple(
                        source.read_text(
                            encoding="utf-8", errors="surrogateescape"
                        ).splitlines()
                    )
                except FileNotFoundError:
                    lines = ()
            self._lines[directory] = lines
        return self._lines[directory]

    def _spec(self, directory: PurePosixPath) -> GitIgnoreSpec:
        if directory not in self._specs:
            self._specs[directory] = GitIgnoreSpec.from_lines(self._read(directory))
        return self._specs[directory]

    def sources(
        self, directories: tuple[str, ...]
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Patterns per ignore file, shown relative to the local root.

        Files above the local root come first, nearest the repository root
        first, followed by the given profile-relative directories.
        """
        prefix = self._profile_prefix.parts
        scopes = [
            (
                PurePosixPath(*prefix[:depth]),
                PurePosixPath(*[".."] * (len(prefix) - depth)),
            )
            for depth in range(len(prefix))
        ]
        scopes.extend(
            (PurePosixPath(*prefix, directory), PurePosixPath(directory))
            for directory in directories
        )
        found = []
        for scope, shown in scopes:
            patterns = tuple(
                line.rstrip()
                for line in self._read(scope)
                if line.strip() and not line.startswith("#")
            )
            if patterns:
                found.append(((shown / ".gitignore").as_posix(), patterns))
        return tuple(found)

    def excludes(self, path: str, *, is_directory: bool = False) -> bool:
        parts = (PurePosixPath(self._profile_prefix) / path).parts
        scopes: list[PurePosixPath] = []
        for depth in range(len(parts)):
            parent = PurePosixPath(*parts[:depth])
            if self.root.joinpath(*parent.parts).is_symlink():
                return False
            scopes.append(parent)
            directory = depth < len(parts) - 1 or is_directory
            ignored = False
            for scope in scopes:
                candidate = PurePosixPath(
                    *parts[len(scope.parts) : depth + 1]
                ).as_posix()
                result = self._spec(scope).check_file(
                    candidate + ("/" if directory else "")
                )
                if result.include is not None:
                    ignored = result.include
            # A negation inside an ignored parent cannot reopen that parent.
            if ignored:
                return True
        return False
