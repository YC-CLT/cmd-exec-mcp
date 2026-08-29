import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import config
from executors.session import SessionManager


class MockSessionManager(SessionManager):
    def __init__(self):
        super().__init__()
        self._sessions = {}
        self._lock = MagicMock()


@pytest.fixture
def session_module(monkeypatch):
    monkeypatch.setattr("main._opensandbox_sessions", {})
    monkeypatch.setattr("main._opensandbox_sessions_lock", MagicMock())
    import main
    return main


class TestExecuteSession:
    @pytest.mark.asyncio
    async def test_list_empty(self, session_module):
        result = await session_module.execute_session("list")
        assert result == {"result": []}

    @pytest.mark.asyncio
    async def test_list_with_opensandbox(self, session_module):
        session_module._opensandbox_sessions = {
            "os-sid-1": {
                "sandbox": MagicMock(),
                "os_session_id": "os-001",
                "last_result": None,
                "alive_timeout": 300,
                "last_used": 0,
                "watchdog_task": None,
            }
        }
        result = await session_module.execute_session("list")
        assert len(result["result"]) == 1
        assert result["result"][0]["session_id"] == "os-sid-1"
        assert result["result"][0]["is_running"] is True

    @pytest.mark.asyncio
    async def test_list_with_local(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm._sessions = {"local-1": MagicMock(exit_code=None, alive_timeout=300)}
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("list")
        assert len(result["result"]) == 1
        assert result["result"][0]["session_id"] == "local-1"

    @pytest.mark.asyncio
    async def test_missing_session_id(self, session_module):
        result = await session_module.execute_session("read")
        assert result["success"] == False
        assert "session_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_read_local_session(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm.read = MagicMock(return_value={"stdout": "hello", "stderr": "", "exit_code": 0, "is_running": False})
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("read", session_id="local-1")
        assert result["stdout"] == "hello"

    @pytest.mark.asyncio
    async def test_send_local_session(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm.send = MagicMock()
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("send", session_id="local-1", command="data")
        assert result == {"sent": True, "session_id": "local-1"}

    @pytest.mark.asyncio
    async def test_kill_local_session(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm.kill = MagicMock(return_value={"killed": True, "session_id": "local-1"})
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("kill", session_id="local-1")
        assert result == {"killed": True, "session_id": "local-1"}

    @pytest.mark.asyncio
    async def test_status_local_session(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm.status = MagicMock(return_value={
            "session_id": "local-1", "is_running": True, "alive_timeout": 300
        })
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("status", session_id="local-1")
        assert result["session_id"] == "local-1"
        assert result["is_running"] is True

    @pytest.mark.asyncio
    async def test_unknown_action(self, session_module):
        result = await session_module.execute_session("unknown", session_id="local-1")
        assert result["success"] == False
        assert "unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_session_not_found(self, session_module, monkeypatch):
        mock_sm = MockSessionManager()
        mock_sm.read = MagicMock(side_effect=ValueError("session not found"))
        monkeypatch.setattr(session_module, "session_manager", mock_sm)
        result = await session_module.execute_session("read", session_id="nonexistent")
        assert result["success"] == False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_opensandbox_read(self, session_module, monkeypatch):
        session_module._opensandbox_sessions = {
            "os-sid": {
                "sandbox": MagicMock(),
                "os_session_id": "os-001",
                "last_result": None,
                "alive_timeout": 300,
                "last_used": 0,
                "watchdog_task": None,
            }
        }
        mock_dispatch = AsyncMock(return_value={"stdout": "output", "is_running": True})
        monkeypatch.setattr(session_module, "_opensandbox_session_dispatch", mock_dispatch)
        result = await session_module.execute_session("read", session_id="os-sid")
        assert result["stdout"] == "output"

    @pytest.mark.asyncio
    async def test_opensandbox_status(self, session_module):
        session_module._opensandbox_sessions = {
            "os-sid": {
                "sandbox": MagicMock(),
                "os_session_id": "os-001",
                "last_result": None,
                "alive_timeout": 300,
                "last_used": 0,
                "watchdog_task": None,
            }
        }
        result = await session_module.execute_session("status", session_id="os-sid")
        assert result["session_id"] == "os-sid"
        assert result["is_running"] is True