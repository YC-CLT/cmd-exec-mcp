import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from executors.remote import RemoteExecutor


@pytest.mark.asyncio
async def test_create_session_returns_proc():
    executor = RemoteExecutor()
    mock_conn = MagicMock()
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_conn.create_process = AsyncMock(return_value=mock_proc)
    executor._conn = mock_conn

    with patch.object(executor, '_get_connection', return_value=mock_conn):
        proc = await executor.create_session("echo hello")
        assert proc is not None
        assert hasattr(proc, "stdin")
        assert hasattr(proc, "stdout")
        assert hasattr(proc, "stderr")