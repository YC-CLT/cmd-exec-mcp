import pytest
from executors.sandbox import SandboxExecutor


@pytest.mark.asyncio
async def test_create_session_returns_proc():
    executor = SandboxExecutor()
    proc = await executor.create_session("echo hello")
    assert proc is not None
    assert hasattr(proc, "stdin")
    assert hasattr(proc, "stdout")
    assert hasattr(proc, "stderr")
    proc.terminate()
    proc.wait()