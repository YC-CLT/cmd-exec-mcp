import pytest
from unittest.mock import AsyncMock, MagicMock


class MockStdoutMsg:
    def __init__(self, text):
        self.text = text


class MockStderrMsg:
    def __init__(self, text):
        self.text = text


class MockExecution:
    def __init__(self, stdout_text="", stderr_text="", exit_code=0):
        self.exit_code = exit_code
        self.logs = MagicMock()
        self.logs.stdout = [MockStdoutMsg(stdout_text)]
        self.logs.stderr = [MockStderrMsg(stderr_text)]


class MockSandbox:
    def __init__(self, execution=None):
        self.execution = execution or MockExecution()
        self.commands = MagicMock()
        self.commands.run = AsyncMock(return_value=self.execution)
        self.destroy = AsyncMock()


@pytest.fixture
def _patch_opensandbox_import(monkeypatch):
    mock_opensandbox = MagicMock()
    mock_config = MagicMock()
    mock_config.ConnectionConfig = MagicMock(return_value=MagicMock())
    mock_opensandbox.config = mock_config

    mock_sandbox_mod = MagicMock()
    mock_sandbox_mod.Sandbox = MagicMock()
    mock_sandbox_mod.Sandbox.create = AsyncMock()
    mock_opensandbox.sandbox = mock_sandbox_mod

    monkeypatch.setitem(
        __import__("sys").modules, "opensandbox", mock_opensandbox
    )
    monkeypatch.setitem(
        __import__("sys").modules, "opensandbox.config", mock_config
    )
    monkeypatch.setitem(
        __import__("sys").modules, "opensandbox.sandbox", mock_sandbox_mod
    )


@pytest.fixture
def executor_module(_patch_opensandbox_import):
    import executors.opensandbox
    return executors.opensandbox


class TestOpenSandboxExecutor:
    @pytest.mark.asyncio
    async def test_execute_returns_exec_result(self, executor_module, monkeypatch):
        sandbox = MockSandbox(MockExecution(stdout_text="hello world"))
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(return_value=sandbox)
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        from models import ExecResult
        result = await executor.execute("echo hello")
        assert isinstance(result, ExecResult)
        assert result.stdout == "hello world"
        assert result.exit_code == 0
        assert result.command_echo == "echo hello"
        sandbox.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self, executor_module, monkeypatch):
        sandbox = MockSandbox()
        sandbox.commands.run = AsyncMock(side_effect=TimeoutError("timed out"))
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(return_value=sandbox)
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        with pytest.raises(TimeoutError, match="timed out"):
            await executor.execute("sleep 100", timeout=1)
        sandbox.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_batch_runs_parallel(self, executor_module, monkeypatch):
        sandbox1 = MockSandbox(MockExecution(stdout_text="one"))
        sandbox2 = MockSandbox(MockExecution(stdout_text="two"))
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(side_effect=[sandbox1, sandbox2])
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        results = await executor.execute_batch(["echo one", "echo two"])
        assert len(results) == 2
        assert results[0].stdout == "one"
        assert results[1].stdout == "two"
        sandbox1.destroy.assert_awaited_once()
        sandbox2.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_called_on_exception(self, executor_module, monkeypatch):
        sandbox = MockSandbox()
        sandbox.commands.run = AsyncMock(side_effect=RuntimeError("boom"))
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(return_value=sandbox)
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        with pytest.raises(RuntimeError, match="boom"):
            await executor.execute("bad command")
        sandbox.destroy.assert_awaited_once()


class MockSessionExecution:
    def __init__(self, stdout_text="", stderr_text="", exit_code=0, duration_ms=100):
        self.exit_code = exit_code
        self.complete = MagicMock()
        self.complete.execution_time_in_millis = duration_ms
        self.logs = MagicMock()
        self.logs.stdout = [MockStdoutMsg(stdout_text)]
        self.logs.stderr = [MockStderrMsg(stderr_text)]


class MockSessionSandbox:
    def __init__(self, execution=None):
        self._execution = execution or MockSessionExecution()
        self.commands = MagicMock()
        self.commands.create_session = AsyncMock(return_value="os-sid-001")
        self.commands.run_in_session = AsyncMock(return_value=self._execution)
        self.commands.delete_session = AsyncMock()
        self.destroy = AsyncMock()


class TestOpenSandboxSessionMethods:
    @pytest.mark.asyncio
    async def test_create_session_returns_sandbox_and_session_id(self, executor_module, monkeypatch):
        sandbox = MockSessionSandbox()
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(return_value=sandbox)
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        s, sid = await executor.create_session("echo hello")
        assert s is sandbox
        assert sid == "os-sid-001"
        sandbox.commands.create_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_session_destroys_on_failure(self, executor_module, monkeypatch):
        sandbox = MockSessionSandbox()
        sandbox.commands.create_session = AsyncMock(side_effect=RuntimeError("session failed"))
        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create = AsyncMock(return_value=sandbox)
        monkeypatch.setattr(executor_module, "Sandbox", mock_sandbox_cls)

        executor = executor_module.OpenSandboxExecutor()
        with pytest.raises(RuntimeError, match="session failed"):
            await executor.create_session("echo hello")
        sandbox.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_in_session_returns_exec_result(self, executor_module):
        executor = executor_module.OpenSandboxExecutor()
        sandbox = MockSessionSandbox(
            MockSessionExecution(stdout_text="hello session", exit_code=0, duration_ms=500)
        )
        from models import ExecResult
        result = await executor.run_in_session(sandbox, "os-sid-001", "echo hello")
        assert isinstance(result, ExecResult)
        assert result.stdout == "hello session"
        assert result.exit_code == 0
        assert result.duration == 0.5
        assert result.command_echo == "echo hello"
        sandbox.commands.run_in_session.assert_awaited_once_with(
            "os-sid-001", "echo hello", timeout=None
        )

    @pytest.mark.asyncio
    async def test_run_in_session_with_timeout(self, executor_module):
        from datetime import timedelta
        executor = executor_module.OpenSandboxExecutor()
        sandbox = MockSessionSandbox()
        await executor.run_in_session(sandbox, "os-sid-001", "sleep 10", timeout=5)
        sandbox.commands.run_in_session.assert_awaited_once_with(
            "os-sid-001", "sleep 10", timeout=timedelta(seconds=5)
        )

    @pytest.mark.asyncio
    async def test_delete_session_calls_destroy(self, executor_module):
        executor = executor_module.OpenSandboxExecutor()
        sandbox = MockSessionSandbox()
        await executor.delete_session(sandbox, "os-sid-001")
        sandbox.commands.delete_session.assert_awaited_once_with("os-sid-001")
        sandbox.destroy.assert_awaited_once()