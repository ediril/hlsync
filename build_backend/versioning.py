"""Advance a starting release version along its baseline's first-parent history."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from email.parser import Parser
from pathlib import Path

VERSION_PATTERN = re.compile(r"[1-9][0-9]*\.(?:0|[1-9][0-9]*)\.[1-9][0-9]*")


def git_version(root: Path) -> str:
    baseline = json.loads((root / "version.json").read_text())
    version, commit = baseline["version"], baseline["commit"]
    if (
        not isinstance(version, str)
        or VERSION_PATTERN.fullmatch(version) is None
        or not isinstance(commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", commit) is None
    ):
        raise ValueError(
            "version.json requires a valid starting version and a full commit SHA"
        )
    major, work_day, increment = map(int, version.split("."))
    result = subprocess.run(
        ["git", "log", "--first-parent", "--format=%H %cI", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    dates = []
    for line in result.stdout.splitlines():
        sha, timestamp = line.split()
        dates.append(datetime.fromisoformat(timestamp).date())
        if sha == commit:
            break
    else:
        raise ValueError(
            "version baseline is missing from first-parent history; "
            "fetch the full history or correct version.json"
        )
    if dates != sorted(dates, reverse=True):
        raise ValueError("commit dates go backwards in the version baseline's history")
    work_day += len(set(dates)) - 1
    daily_commits = dates.count(dates[0])
    if dates[0] == dates[-1]:
        daily_commits += increment - 1
    return f"{major}.{work_day}.{daily_commits}"


def release_version(root: Path) -> str:
    if (root / ".git").exists():
        return git_version(root)

    # An sdist carries the version fixed when it was built, without needing Git.
    metadata = root / "PKG-INFO"
    if not metadata.is_file():
        raise ValueError("version requires a Git checkout or a built source archive")
    version = Parser().parsestr(metadata.read_text())["Version"]
    if version is None or VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError("source archive has an invalid release version")
    return version


def write_version(root: Path) -> str:
    version = release_version(root)
    path = root / "src" / "hlsync" / "_version.py"
    content = f'# Generated at build time; do not edit.\n__version__ = "{version}"\n'
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
    return version
