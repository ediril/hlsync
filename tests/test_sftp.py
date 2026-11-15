from __future__ import annotations

import asyncio
import io
import os
import threading
from pathlib import PurePosixPath

import asyncssh
import pytest

from hlsync.cli import run
from hlsync.config import ConfigurationStore, ProfileConfiguration
from hlsync.rules import RuleSet
from hlsync.sftp import SFTPTransport
from hlsync.snapshot import TreeSnapshot
from hlsync.transport import PathOperationError, TransportError


@pytest.fixture
def sftp_server(tmp_path, monkeypatch):
    """A real SFTP server over SSH, serving tmp_path/remote as '/'."""
    remote = tmp_path / "remote"
    (remote / "home" / "deploy").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    host_key = asyncssh.generate_private_key("ssh-ed25519")
    client_key = asyncssh.generate_private_key("ssh-ed25519")

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return True

        def password_auth_supported(self):
            return True

        def validate_password(self, username, password):
            return (username, password) == ("deploy", "secret")

        def public_key_auth_supported(self):
            return True

        def validate_public_key(self, username, key):
            return username == "deploy" and key.public_data == client_key.public_data

    class LoginFolderServer(asyncssh.SFTPServer):
        """Logs the account in to /home/deploy, like an OpenSSH home folder."""

        def realpath(self, path):
            return b"/home/deploy" if path == b"." else super().realpath(path)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def listen():
        return await asyncssh.listen(
            "127.0.0.1",
            0,
            server_host_keys=[host_key],
            server_factory=Server,
            sftp_factory=lambda channel: LoginFolderServer(
                channel, chroot=os.fspath(remote)
            ),
        )

    acceptor = asyncio.run_coroutine_threadsafe(listen(), loop).result(10)
    port = acceptor.get_port()
    public_host_key = " ".join(host_key.export_public_key().decode().split()[:2])
    known_hosts = home / ".ssh" / "known_hosts"
    known_hosts.write_text(f"[127.0.0.1]:{port} {public_host_key}\n")
    monkeypatch.setenv("HOME", os.fspath(home))
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.setenv("PROD_SFTP_USERNAME", "deploy")
    monkeypatch.setenv("PROD_SFTP_PASSWORD", "secret")
    yield port, remote, home, client_key

    async def stop():
        acceptor.close()
        await acceptor.wait_closed()

    asyncio.run_coroutine_threadsafe(stop(), loop).result(10)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(10)


def test_an_sftp_profile_creates_its_root_and_pushes_replaces_prunes_and_pulls(
    sftp_server, tmp_path, monkeypatch
):
    port, remote, _, _ = sftp_server
    local = tmp_path / "local"
    (local / "assets").mkdir(parents=True)
    (local / "index.html").write_text("index")
    (local / "assets" / "app.js").write_text("app")
    store = ConfigurationStore(tmp_path / "configs.json")
    monkeypatch.chdir(local)

    def invoke(*arguments):
        output, progress = io.StringIO(), io.StringIO()
        status = run(list(arguments), store=store, stdout=output, stderr=progress)
        return status, output.getvalue(), progress.getvalue()

    monkeypatch.setenv("PROD_SFTP_HOST", "127.0.0.1")
    monkeypatch.setenv("PROD_FTPS_HOST", "ftp.unrelated.example")
    created = invoke(
        "create", "prod", "--protocol", "sftp", "--port", str(port),
        "-r", "./sites/demo/", "--local-root", str(local),
    )
    assert created[1].startswith(
        "Created SFTP profile 'prod' on 127.0.0.1 (from PROD_SFTP_HOST).\n"
    )
    profile = store.load().profiles["prod"]
    assert (
        profile.remote_root, profile.port, profile.username_env, profile.password_env
    ) == ("sites/demo", port, "PROD_SFTP_USERNAME", "PROD_SFTP_PASSWORD")
    assert invoke("connect")[1] == (
        "Verified secure connectivity to profile 'prod'.\n"
        "Remote root /home/deploy/sites/demo does not exist yet; push will "
        "create it.\n"
    )

    status, _, progress = invoke("push", "-j", "2")
    assert status == 0, progress
    assert "Connecting securely over SFTP...\n" in progress
    assert "Created remote root /home/deploy/sites/demo.\n" in progress
    assert "Using 2 connections.\n" in progress
    assert not (remote / "sites").exists()
    current = remote / "home" / "deploy" / "sites" / "demo"
    assert (current / "index.html").read_text() == "index"
    assert (current / "assets" / "app.js").read_text() == "app"
    assert int((current / "index.html").stat().st_mtime) == int(
        (local / "index.html").stat().st_mtime
    )
    assert "Nothing to push" in invoke("push")[1]

    (local / "index.html").write_text("index v2")
    os.utime(local / "index.html", (2_000_000_000, 2_000_000_000))
    (local / "assets" / "app.js").unlink()
    status, _, progress = invoke("push", "-p")
    assert status == 0, progress
    assert (current / "index.html").read_text() == "index v2"
    assert sorted(path.name for path in current.rglob("*")) == ["assets", "index.html"]

    (current / "index.html").write_text("edited on the server")
    os.utime(current / "index.html", (2_100_000_000, 2_100_000_000))
    status, _, progress = invoke("pull", "index.html")
    assert status == 0, progress
    assert (local / "index.html").read_text() == "edited on the server"


def test_sftp_logs_in_with_keys_checks_host_keys_and_classifies_failures(
    sftp_server, monkeypatch
):
    port, remote, home, client_key = sftp_server
    profile = ProfileConfiguration(
        type="sftp", host="127.0.0.1", port=port, remote_root="."
    )
    login_folder = remote / "home" / "deploy"
    key_file = home / ".ssh" / "id_ed25519"
    key_file.write_bytes(client_key.export_private_key("openssh"))
    key_file.chmod(0o600)
    monkeypatch.delenv("PROD_SFTP_PASSWORD")
    # An FTPS profile's password must never be offered to an SSH server.
    monkeypatch.setenv("PROD_FTPS_PASSWORD", "secret")

    with SFTPTransport(profile) as transport:
        assert transport.list_directory(PurePosixPath(), RuleSet()) == TreeSnapshot()
        (login_folder / "locked").mkdir(mode=0o500)
        try:
            with pytest.raises(PathOperationError, match="create remote directory"):
                transport.make_directory("locked/inner")
        finally:
            (login_folder / "locked").chmod(0o700)
        transport._ssh.close()
        with pytest.raises(TransportError) as lost:
            transport.make_directory("after-disconnect")
        assert not isinstance(lost.value, PathOperationError)

    key_file.unlink()
    with pytest.raises(TransportError, match="SSH login failed for deploy@127.0.0.1"):
        SFTPTransport(profile).connect()

    (home / ".ssh" / "known_hosts").write_text("")
    with pytest.raises(
        TransportError,
        match=rf"is not in ~/.ssh/known_hosts; run 'ssh -p {port} deploy@127.0.0.1'",
    ):
        SFTPTransport(profile).connect()
