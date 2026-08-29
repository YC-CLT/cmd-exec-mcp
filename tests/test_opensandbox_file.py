import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import timedelta
import config


class MockFileSandbox:
    def __init__(self):
        self.files = MagicMock()
        self.files.read_file = AsyncMock(return_value="file content")
        self.files.write_file = AsyncMock()
        self.destroy = AsyncMock()


@pytest.fixture
def mock_sandbox_create():
    sandbox = MockFileSandbox()
    with patch("main.Sandbox") as mock:
        mock.create = AsyncMock(return_value=sandbox)
        yield sandbox


@pytest.fixture
def file_module(monkeypatch):
    monkeypatch.setattr("main._ensure_opensandbox_server", lambda: None)
    monkeypatch.setattr("main._opensandbox_sessions", {})
    monkeypatch.setattr("main._opensandbox_sessions_lock", MagicMock())
    monkeypatch.setattr("main._reset_watchdog", AsyncMock())
    import main
    return main


class TestExecuteSandboxFile:
    @pytest.mark.asyncio
    async def test_wrong_backend_returns_error(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "docker")
        result = await file_module.execute_sandbox_file("upload", "/tmp/test.txt", local_path="D:/local.txt")
        assert result["success"] == False
        assert "仅支持 opensandbox" in result["error"]

    @pytest.mark.asyncio
    async def test_relative_path_returns_error(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file("upload", "relative/path.txt", local_path="D:/local.txt")
        assert result["success"] == False
        assert "absolute" in result["error"]

    @pytest.mark.asyncio
    async def test_download_file_with_temp_sandbox(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        with patch("builtins.open", mock_open()) as mock_file:
            result = await file_module.execute_sandbox_file("download", "/tmp/test.txt", local_path="D:/out.txt")
        assert result["success"] == True
        mock_sandbox_create.files.read_file.assert_awaited_once_with("/tmp/test.txt")
        mock_sandbox_create.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_temp_sandbox(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        with patch("builtins.open", mock_open(read_data="print(1)")):
            result = await file_module.execute_sandbox_file("upload", "/tmp/script.py", local_path="D:/script.py")
        assert result["success"] == True
        mock_sandbox_create.files.write_file.assert_awaited_once_with("/tmp/script.py", "print(1)")
        mock_sandbox_create.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_file_operation_with_session_id(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        sandbox = MockFileSandbox()
        file_module._opensandbox_sessions = {
            "test-sid": {
                "sandbox": sandbox,
                "os_session_id": "os-sid-001",
                "last_result": None,
                "alive_timeout": 300,
                "last_used": 0,
                "watchdog_task": None,
            }
        }
        with patch("builtins.open", mock_open(read_data="content")):
            result = await file_module.execute_sandbox_file(
                "upload", "/tmp/test.txt", session_id="test-sid", local_path="D:/test.txt"
            )
        assert result["success"] == True
        sandbox.files.write_file.assert_awaited_once_with("/tmp/test.txt", "content")

    @pytest.mark.asyncio
    async def test_session_not_found(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file(
            "download", "/tmp/test.txt", session_id="nonexistent", local_path="D:/out.txt"
        )
        assert result["success"] == False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_action(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file("unknown", "/tmp/test.txt", local_path="D:/local.txt")
        assert result["success"] == False
        assert "unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_local_path(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file("upload", "/tmp/test.txt")
        assert result["success"] == False
        assert "local_path is required" in result["error"]