from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys

import pytest

from hlsync.cli import run
from hlsync.shell import BEGIN, END


def setup(monkeypatch, home, shell="/bin/zsh"):
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)
    monkeypatch.delenv("ZDOTDIR", raising=False)
    output, errors = io.StringIO(), io.StringIO()
    status = run(["setup"], stdout=output, stderr=errors)
    return status, output.getvalue(), errors.getvalue()


def test_setup_adds_one_block_and_updates_it_in_place(tmp_path, monkeypatch):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "zshrc"
    target.write_text("export EDITOR=vim\n")
    target.chmod(0o640)
    (tmp_path / ".zshrc").symlink_to(target)

    status, output, _ = setup(monkeypatch, tmp_path)
    assert status == 0
    assert output.startswith("Added the hlsync shell function in ~/.zshrc.\n")
    assert (tmp_path / ".zshrc").is_symlink()
    target.write_text(target.read_text() + "\nalias ll='ls -l'\n")

    assert setup(monkeypatch, tmp_path)[1].startswith("Updated")
    text = target.read_text()
    assert text.count(BEGIN) == text.count(END) == 1
    assert text.startswith("export EDITOR=vim\n\n" + BEGIN)
    assert text.endswith(END + "\n\nalias ll='ls -l'\n")
    assert target.stat().st_mode & 0o777 == 0o640

    assert setup(monkeypatch, tmp_path, shell="/usr/bin/fish") == (
        1, "", "hlsync: error: setup supports zsh and bash, not 'fish'\n"
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_setup_function_changes_directory_and_passes_other_commands(
    tmp_path, monkeypatch, shell
):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    site = tmp_path / "my site"
    site.mkdir()
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    program = bin_directory / "hlsync"
    program.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m hlsync "$@"\n')
    program.chmod(0o755)
    assert setup(monkeypatch, tmp_path, shell=executable)[0] == 0
    startup = tmp_path / (".zshrc" if shell == "zsh" else ".bashrc")

    script = (
        f"source {startup}\n"
        f"hlsync create prod --host h -r /site --local-root '{site}' >/dev/null\n"
        "hlsync cd prod && pwd\n"
        "cd / && hlsync cd nope; echo status=$? && pwd\n"
        "hlsync root prod\n"
    )
    environment = {**os.environ, "PATH": f"{bin_directory}:{os.environ['PATH']}"}
    result = subprocess.run(
        [executable, "-c", script],
        capture_output=True, text=True, env=environment, check=True,
    )
    assert result.stdout.splitlines() == [
        str(site.resolve()), "status=1", "/", str(site.resolve()),
    ]
    assert "profile 'nope'" in result.stderr


def test_cd_without_the_shell_function_explains_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    errors = io.StringIO()
    assert run(["cd", "prod"], stdout=io.StringIO(), stderr=errors) == 1
    assert errors.getvalue() == (
        "hlsync: error: cd needs the shell function; run 'hlsync setup', "
        "then open a new terminal\n"
    )
