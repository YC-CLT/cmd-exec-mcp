import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import config
from models import ExecResult


class MockSessionExecution:
    def __init__(self, stdout_text="", stderr_text="", exit_code=0, duration_ms=100):
        self.exit_code = exit_code
        self.complete = MagicMock()
        self.complete.execution_time_in_millis = duration_ms
        self.logs = MagicMock()
        self.logs.stdout = [MagicMock(text=stdout_text)]
        self.logs.stderr = [MagicMock(text=stderr_text)]


class MockOsSandbox:
    def __init__(self):
        self.commands = MagicMock()
        self.commands.create_session = AsyncMock(return_value="os-sid-001")
        self.commands.run_in_session = AsyncMock(
            return_value=MockSessionExecution(stdout_text="hello")
        )
        self.commands.delete_session = AsyncMock()
        self.destroy = AsyncMock()
        self.files = MagicMock()


@pytest.fixture
def mock_opensandbox_executor():
    mock = MagicMock()
    mock.create_session = AsyncMock(return_value=(MockOsSandbox(), "os-sid-001"))
    mock.run_in_session = AsyncMock(
        return_value=ExecResult(stdout="hello", exit_code=0, duration=0.1)
    )
    mock.delete_session = AsyncMock()
    mock.conn = MagicMock()
    return mock


@pytest.fixture
def session_module(monkeypatch, mock_opensandbox_executor):
    monkeypatch.setattr("main.opensandbox", mock_opensandbox_executor)
    monkeypatch.setattr("main._ensure_opensandbox_server", lambda: None)
    monkeypatch.setattr("main._opensandbox_sessions", {})
    import main
    return main


class TestOpenSandboxSessionManagement:
    def test_initial_state(self):
        import main
        assert main._opensandbox_sessions == {}
        assert isinstance(main._opensandbox_sessions_lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_create_session_returns_session_id(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 300
        )
        assert "session_id" in result
        assert len(result["session_id"]) == 36
        assert result["session_id"] in session_module._opensandbox_sessions

    @pytest.mark.asyncio
    async def test_create_session_executes_initial_command(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 300
        )
        sid = result["session_id"]
        session = session_module._opensandbox_sessions[sid]
        assert session["last_result"] is not None
        assert session["last_result"].stdout == "hello"

    @pytest.mark.asyncio
    async def test_create_session_empty_command_no_last_result(self, session_module):
        result = await session_module._opensandbox_session_create(
            "", None, 300
        )
        sid = result["session_id"]
        session = session_module._opensandbox_sessions[sid]
        assert session["last_result"] is None

    @pytest.mark.asyncio
    async def test_dispatch_send_returns_result(self, session_module):
        result = await session_module._opensandbox_session_create(
            "", None, 300
        )
        sid = result["session_id"]
        send_result = await session_module._opensandbox_session_dispatch(
            sid, "send", "ls -la", timeout=30
        )
        assert send_result["stdout"] == "hello"
        assert send_result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_dispatch_read_returns_last_result(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 300
        )
        sid = result["session_id"]
        read_result = await session_module._opensandbox_session_dispatch(
            sid, "read", "", timeout=None
        )
        assert read_result["stdout"] == "hello"
        assert read_result["exit_code"] == 0
        assert read_result["is_running"] == False

    @pytest.mark.asyncio
    async def test_dispatch_read_empty_session(self, session_module):
        result = await session_module._opensandbox_session_create(
            "", None, 300
        )
        sid = result["session_id"]
        read_result = await session_module._opensandbox_session_dispatch(
            sid, "read", "", timeout=None
        )
        assert read_result["stdout"] == ""
        assert read_result["exit_code"] is None
        assert read_result["is_running"] == True

    @pytest.mark.asyncio
    async def test_dispatch_kill_removes_session(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 300
        )
        sid = result["session_id"]
        kill_result = await session_module._opensandbox_session_dispatch(
            sid, "kill", "", timeout=None
        )
        assert kill_result["killed"] == True
        assert kill_result["session_id"] == sid
        assert sid not in session_module._opensandbox_sessions

    @pytest.mark.asyncio
    async def test_dispatch_session_not_found(self, session_module):
        result = await session_module._opensandbox_session_dispatch(
            "nonexistent", "read", "", timeout=None
        )
        assert result["success"] == False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_send_sandbox_error(self, session_module, mock_opensandbox_executor):
        mock_opensandbox_executor.run_in_session = AsyncMock(
            side_effect=RuntimeError("sandbox crashed")
        )
        result = await session_module._opensandbox_session_create(
            "", None, 300
        )
        sid = result["session_id"]
        send_result = await session_module._opensandbox_session_dispatch(
            sid, "send", "bad command", timeout=30
        )
        assert send_result["success"] == False
        assert "sandbox error" in send_result["error"]
        assert sid not in session_module._opensandbox_sessions

    @pytest.mark.asyncio
    async def test_watchdog_cleans_up_session(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 1
        )
        sid = result["session_id"]
        assert sid in session_module._opensandbox_sessions
        await asyncio.sleep(1.5)
        assert sid not in session_module._opensandbox_sessions

    @pytest.mark.asyncio
    async def test_reset_watchdog_extends_lifetime(self, session_module):
        result = await session_module._opensandbox_session_create(
            "echo hello", None, 1
        )
        sid = result["session_id"]
        await asyncio.sleep(0.5)
        await session_module._reset_watchdog(sid)
        await asyncio.sleep(0.8)
        assert sid in session_module._opensandbox_sessions
        await asyncio.sleep(1.0)
        assert sid not in session_module._opensandbox_sessions

    @pytest.mark.asyncio
    async def test_cleanup_all_clears_all_sessions(self, session_module):
        await session_module._opensandbox_session_create("cmd1", None, 300)
        await session_module._opensandbox_session_create("cmd2", None, 300)
        assert len(session_module._opensandbox_sessions) == 2
        await session_module._cleanup_all_opensandbox_sessions()
        assert len(session_module._opensandbox_sessions) == 0

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self, session_module):
        results = await asyncio.gather(*[
            session_module._opensandbox_session_create(f"cmd{i}", None, 300)
            for i in range(10)
        ])
        assert len(session_module._opensandbox_sessions) == 10
        await session_module._cleanup_all_opensandbox_sessions()
        assert len(session_module._opensandbox_sessions) == 0