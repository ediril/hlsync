"""Shell startup integration that lets 'hlsync cd' change directory."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from hlsync.storage import write_text_atomic

BEGIN = "# >>> hlsync shell setup >>>"
END = "# <<< hlsync shell setup <<<"

# A program cannot change its parent shell's directory, so 'cd' is handled by
# this function; every other command passes through to the hlsync program.
BLOCK = f"""{BEGIN}
# Lets 'hlsync cd [PROFILE]' change to a profile's local root.
hlsync() {{
  if [ "$1" = cd ]; then
    shift
    local dir
    dir="$(command hlsync root "$@")" && cd "$dir"
  else
    command hlsync "$@"
  fi
}}
{END}
"""

STARTUP_FILES = {"zsh": ".zshrc", "bash": ".bashrc"}


class ShellSetupError(RuntimeError):
    pass


def startup_file(environment: dict[str, str] | None = None) -> Path:
    """Return the interactive startup file of the user's login shell."""
    environment = os.environ if environment is None else environment
    shell = Path(environment.get("SHELL", "")).name
    if shell not in STARTUP_FILES:
        raise ShellSetupError(
            f"setup supports zsh and bash, not '{shell or 'unknown'}'"
        )
    home = Path(environment.get("HOME") or Path.home())
    directory = Path(environment.get("ZDOTDIR") or home) if shell == "zsh" else home
    return directory / STARTUP_FILES[shell]


def install_shell_function(path: Path) -> bool:
    """Write the shell function block; return True if it replaced an older one."""
    # Write through a symlink so dotfile managers keep their link.
    target = path.resolve() if path.is_symlink() else path
    try:
        existing = target.read_text(encoding="utf-8")
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        existing, mode = "", 0o644
    start, end = existing.find(BEGIN), existing.find(END)
    if start != -1 and end > start:
        rest = existing[end + len(END):]
        updated = existing[:start] + BLOCK + rest.removeprefix("\n")
        replaced = True
    else:
        separator = "" if not existing else "\n" if existing.endswith("\n") else "\n\n"
        updated = existing + separator + BLOCK
        replaced = False
    write_text_atomic(target, updated, mode=mode)
    return replaced


def display_path(path: Path) -> str:
    """Show a startup file path with the home directory as '~'."""
    home = Path.home()
    try:
        return f"~/{path.relative_to(home).as_posix()}"
    except ValueError:
        return os.fspath(path)
