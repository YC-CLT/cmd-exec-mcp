import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock
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

    async def run(self, command, timeout=None):
        return self


def _setup_remote_mocks(monkeypatch, ssh_config_mode, ssh_persistent):
    import executors.remote as remote_mod
    monkeypatch.setattr(remote_mod, "SSH_CONFIG_MODE", ssh_config_mode)
    monkeypatch.setattr(remote_mod, "SSH_PERSISTENT", ssh_persistent)
    monkeypatch.setattr(remote_mod, "SSH_CONNECTION_TIMEOUT", 10)

    mock_asyncssh = MagicMock()
    mock_asyncssh.read_config = AsyncMock()
    mock_asyncssh.connect = AsyncMock()
    monkeypatch.setattr(remote_mod, "asyncssh", mock_asyncssh)
    return mock_asyncssh


class TestRemoteExecutorConnection:
    @pytest.mark.asyncio
    async def test_standard_mode_reads_ssh_config(self, monkeypatch):
        import executors.remote as remote_mod
        monkeypatch.setattr(remote_mod, "SSH_HOST_NAME", "test-host")
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.connect.return_value = MockSSHConnection()

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        conn = await executor._connect()

        mock_asyncssh.connect.assert_awaited_once()
        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["host"] == "test-host"
        assert "config" in call_kwargs
        assert conn is not None

    @pytest.mark.asyncio
    async def test_custom_mode_reads_dotenv(self, monkeypatch):
        monkeypatch.setenv("SSH_HOST", "192.168.1.100")
        monkeypatch.setenv("SSH_PORT", "2222")
        monkeypatch.setenv("SSH_USER", "deploy")
        monkeypatch.setenv("SSH_KEY_PATH", "~/.ssh/id_rsa")
        monkeypatch.setenv("SSH_PASSWORD", "")
        monkeypatch.setenv("SSH_KNOWN_HOSTS", "true")

        mock_asyncssh = _setup_remote_mocks(monkeypatch, "custom", False)
        mock_asyncssh.connect.return_value = MockSSHConnection()

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        conn = await executor._connect()

        mock_asyncssh.connect.assert_awaited_once()
        call_kwargs = mock_asyncssh.connect.call_args.kwargs
        assert call_kwargs["host"] == "192.168.1.100"
        assert call_kwargs["port"] == 2222
        assert call_kwargs["username"] == "deploy"

    @pytest.mark.asyncio
    async def test_missing_host_raises(self, monkeypatch):
        _setup_remote_mocks(monkeypatch, "custom", False)
        monkeypatch.delenv("SSH_HOST", raising=False)

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        with pytest.raises(RuntimeError, match="SSH_HOST not set"):
            await executor._connect()


class TestRemoteExecutorExecute:
    @pytest.mark.asyncio
    async def test_execute_command(self, monkeypatch):
        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="hello world")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("echo hello")

        assert isinstance(result, ExecResult)
        assert result.stdout == "hello world"
        assert result.exit_code == 0
        assert result.command_echo == "echo hello"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, monkeypatch):
        mock_conn = MockSSHConnection()
        mock_conn.run = AsyncMock(side_effect=asyncio.TimeoutError())

        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = mock_conn

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("sleep 100", timeout=1)

        assert result.is_timeout is True
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_nonzero_exit(self, monkeypatch):
        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="", stderr="error msg", exit_status=1)

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result = await executor.execute("bad command")

        assert result.exit_code == 1
        assert result.stderr == "error msg"

    @pytest.mark.asyncio
    async def test_persistent_mode_reuses_connection(self, monkeypatch):
        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", True)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        result1 = await executor.execute("cmd1")
        result2 = await executor.execute("cmd2")

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        mock_asyncssh.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_batch(self, monkeypatch):
        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        results = await executor.execute_batch(["cmd1", "cmd2", "cmd3"])

        assert len(results) == 3
        for r in results:
            assert isinstance(r, ExecResult)
            assert r.exit_code == 0


class TestRemoteExecutorExecuteBatch:
    @pytest.mark.asyncio
    async def test_batch_parallel(self, monkeypatch):
        mock_ssh_config = MagicMock()
        mock_ssh_config.hosts = {"test-host": {"HostName": "10.0.0.1", "Port": 22, "User": "admin"}}
        mock_asyncssh = _setup_remote_mocks(monkeypatch, "standard", False)
        mock_asyncssh.read_config.return_value = mock_ssh_config
        mock_asyncssh.connect.return_value = MockSSHConnection(stdout="ok")

        from executors.remote import RemoteExecutor
        executor = RemoteExecutor()
        results = await executor.execute_batch(["echo one", "echo two"])

        assert len(results) == 2
        assert results[0].command_echo == "echo one"
        assert results[1].command_echo == "echo two"