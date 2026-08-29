import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import config
from models import ExecResult


class MockSSHConnection:
    def __init__(self, stdout="", stderr="", exit_status=0):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_status = exit_status

    def is_closed(self):
        return False

    def close(self):
        pass

    async def run(self, command, timeout=None, env=None):
        return self

    def start_sftp_client(self):
        mock_sftp = MagicMock()
        mock_sftp.put = AsyncMock()
        mock_sftp.get = AsyncMock()
        mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
        mock_sftp.__aexit__ = AsyncMock(return_value=False)
        return mock_sftp


def _setup_remote_mocks(monkeypatch, ssh_persistent):
    import executors.remote as remote_mod
    monkeypatch.setattr(remote_mod, "SSH_PERSISTENT", ssh_persistent)
    monkeypatch.setattr(remote_mod, "SSH_CONNECTION_TIMEOUT", 10)

    mock_asyncssh = MagicMock()
    mock_asyncssh.connect = AsyncMock()
    monkeypatch.setattr(remote_mod, "asyncssh", mock_asyncssh)
    return mock_asyncssh


class TestParseTarget:
    def test_host_only(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("rpig")
        assert host == "rpig"
        assert user is None
        assert port == 22

    def test_host_with_port(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("rpig:8022")
        assert host == "rpig"
        assert user == "root"
        assert port == 8022

    def test_user_at_host(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("pi@rpig")
        assert host == "rpig"
        assert user == "pi"
        assert port == 22

    def test_user_at_host_with_port(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("pi@rpig:8022")
        assert host == "rpig"
        assert user == "pi"
        assert port == 8022

    def test_ipv6_bracket(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("user@[::1]:8022")
        assert host == "::1"
        assert user == "user"
        assert port == 8022

    def test_ipv6_bracket_no_port(self):
        from executors.remote import RemoteExecutor
        host, user, port = RemoteExecutor._parse_target("user@[::1]")
        assert host == "::1"
        assert user == "user"
        assert port == 22


class TestRemoteExecutorConnection:
    @pytest.mark.asyncio
    async def test_connect_with_host_only(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection()

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        conn = await executor._connect("rpig")

        mock_asyncssh.connect.assert_awaited_once()
        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["host"] == "rpig"
        assert "config" in call_kwargs
        assert conn is not None

    @pytest.mark.asyncio
    async def test_connect_with_user_and_port(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection()

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        conn = await executor._connect("pi@rpig:8022")

        mock_asyncssh.connect.assert_awaited_once()
        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["host"] == "rpig"
        assert call_kwargs["port"] == 8022
        assert call_kwargs["username"] == "pi"


class TestConnectionPool:
    @pytest.mark.asyncio
    async def test_persistent_reuses_connection(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, True)
        mock_asyncssh.connect.return_value = MockSSHConnection()

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        conn1 = await executor._get_connection("rpig")
        conn2 = await executor._get_connection("rpig")

        assert conn1 is conn2
        mock_asyncssh.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_different_targets_use_different_connections(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, True)
        conn_a = MockSSHConnection()
        conn_b = MockSSHConnection()
        mock_asyncssh.connect.side_effect = [conn_a, conn_b]

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        c1 = await executor._get_connection("rpig")
        c2 = await executor._get_connection("other")

        assert c1 is conn_a
        assert c2 is conn_b


class TestFileTransfer:
    @pytest.mark.asyncio
    async def test_upload_file(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_conn = MockSSHConnection()
        mock_asyncssh.connect.return_value = mock_conn

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        await executor.upload_file("/local/path.txt", "/remote/path.txt", target="rpig")

        mock_asyncssh.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_download_file(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_conn = MockSSHConnection()
        mock_asyncssh.connect.return_value = mock_conn

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        await executor.download_file("/remote/path.txt", "/local/path.txt", target="rpig")

        mock_asyncssh.connect.assert_awaited_once()


class TestRemoteExecutorExecute:
    @pytest.mark.asyncio
    async def test_execute_command(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="hello world")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("echo hello", target="rpig")

        assert isinstance(result, ExecResult)
        assert result.stdout == "hello world"
        assert result.exit_code == 0
        assert result.command_echo == "echo hello"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, monkeypatch):
        mock_conn = MockSSHConnection()
        mock_conn.run = AsyncMock(side_effect=asyncio.TimeoutError())

        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = mock_conn

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("sleep 100", target="rpig", timeout=1)

        assert result.is_timeout is True
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_nonzero_exit(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="", stderr="error msg", exit_status=1)

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("bad command", target="rpig")

        assert result.exit_code == 1
        assert result.stderr == "error msg"

    @pytest.mark.asyncio
    async def test_persistent_mode_reuses_connection(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, True)
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result1 = await executor.execute("cmd1", target="rpig")
        result2 = await executor.execute("cmd2", target="rpig")

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        mock_asyncssh.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_with_cwd(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_conn = MockSSHConnection(stdout="ok")
        mock_conn.run = AsyncMock(return_value=mock_conn)
        mock_asyncssh.connect.return_value = mock_conn

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("ls", target="rpig", cwd="/home/user")

        call_args = mock_conn.run.call_args
        assert 'cd "/home/user"' in call_args[0][0]
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_batch(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        results = await executor.execute_batch(["cmd1", "cmd2", "cmd3"], target="rpig")

        assert len(results) == 3
        for r in results:
            assert isinstance(r, ExecResult)
            assert r.exit_code == 0


class TestRemoteExecutorExecuteBatch:
    @pytest.mark.asyncio
    async def test_batch_parallel(self, monkeypatch):
        mock_asyncssh = _setup_remote_mocks(monkeypatch, False)
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        results = await executor.execute_batch(["echo one", "echo two"], target="rpig")

        assert len(results) == 2
        assert results[0].command_echo == "echo one"
        assert results[1].command_echo == "echo two"