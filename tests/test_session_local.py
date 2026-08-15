import pytest
from executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_create_session_returns_proc():
    executor = LocalExecutor()
    proc = await executor.create_session("echo hello", ".", {}, 300)
    assert proc is not None
    assert hasattr(proc, "stdin")
    assert hasattr(proc, "stdout")
    assert hasattr(proc, "stderr")
    proc.terminate()
    proc.wait()


@pytest.mark.asyncio
async def test_create_session_ignores_alive_timeout():
    executor = LocalExecutor()
    proc = await executor.create_session("echo hello", ".", {}, 300)
    proc.wait()
    assert proc.returncode == 0