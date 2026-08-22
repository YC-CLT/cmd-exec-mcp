import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta
import config


class MockFileSandbox:
    def __init__(self):
        self.files = MagicMock()
        self.files.read_file = AsyncMock(return_value="file content")
        self.files.write_file = AsyncMock()
        self.files.list_directory = AsyncMock(return_value=[
            MagicMock(model_dump=lambda: {"name": "file1.txt", "type": "file"}),
            MagicMock(model_dump=lambda: {"name": "dir1", "type": "directory"}),
        ])
        self.files.delete_files = AsyncMock()
        self.files.get_file_info = AsyncMock(return_value=[])
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
    monkeypatch.setattr("main._reset_watchdog", lambda sid: None)
    import main
    return main


class TestExecuteSandboxFile:
    @pytest.mark.asyncio
    async def test_wrong_backend_returns_error(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "docker")
        result = await file_module.execute_sandbox_file("read", "/tmp/test.txt")
        assert result["success"] == False
        assert "仅支持 opensandbox" in result["error"]

    @pytest.mark.asyncio
    async def test_relative_path_returns_error(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file("read", "relative/path.txt")
        assert result["success"] == False
        assert "absolute" in result["error"]

    @pytest.mark.asyncio
    async def test_read_file_with_temp_sandbox(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("read", "/tmp/test.txt")
        assert result["success"] == True
        assert result["data"] == "file content"
        mock_sandbox_create.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_file_with_temp_sandbox(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file(
            "write", "/tmp/script.py", content="print(1)"
        )
        assert result["success"] == True
        mock_sandbox_create.files.write_file.assert_awaited_once_with(
            "/tmp/script.py", "print(1)"
        )

    @pytest.mark.asyncio
    async def test_list_directory(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("list", "/tmp")
        assert result["success"] == True
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "file1.txt"

    @pytest.mark.asyncio
    async def test_delete_file(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("delete", "/tmp/old.txt")
        assert result["success"] == True
        mock_sandbox_create.files.delete_files.assert_awaited_once_with(["/tmp/old.txt"])

    @pytest.mark.asyncio
    async def test_exists_returns_true(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("exists", "/tmp/exists.txt")
        assert result["success"] == True
        assert result["data"] == True

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, file_module, monkeypatch, mock_sandbox_create):
        mock_sandbox_create.files.get_file_info = AsyncMock(
            side_effect=RuntimeError("not found")
        )
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("exists", "/tmp/missing.txt")
        assert result["success"] == True
        assert result["data"] == False

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
        result = await file_module.execute_sandbox_file(
            "read", "/tmp/test.txt", session_id="test-sid"
        )
        assert result["success"] == True
        assert result["data"] == "file content"
        sandbox.files.read_file.assert_awaited_once_with("/tmp/test.txt")

    @pytest.mark.asyncio
    async def test_session_not_found(self, file_module, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        result = await file_module.execute_sandbox_file(
            "read", "/tmp/test.txt", session_id="nonexistent"
        )
        assert result["success"] == False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_action(self, file_module, monkeypatch, mock_sandbox_create):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")
        monkeypatch.setattr(config, "SANDBOX_OPEN_ENTRYPOINT", None)
        monkeypatch.setattr(config, "SANDBOX_OPEN_TEMPLATE", "template")
        mock_conn = MagicMock()
        monkeypatch.setattr(file_module.opensandbox, "conn", mock_conn)
        result = await file_module.execute_sandbox_file("unknown", "/tmp/test.txt")
        assert result["success"] == False
        assert "unknown action" in result["error"]