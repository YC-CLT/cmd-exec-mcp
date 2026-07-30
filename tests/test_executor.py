# tests/test_executor.py
import pytest
from executors.local import LocalExecutor
from models import ExecResult


@pytest.mark.asyncio
async def test_local_executor_basic_command():
    executor = LocalExecutor()
    result = await executor.execute("echo hello")
    assert isinstance(result, ExecResult)
    assert "hello" in result.stdout
    assert result.exit_code == 0
    assert result.is_timeout is False


@pytest.mark.asyncio
async def test_local_executor_failing_command():
    executor = LocalExecutor()
    result = await executor.execute('python -c "exit(1)"')
    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_local_executor_timeout():
    executor = LocalExecutor()
    result = await executor.execute('python -c "import time; time.sleep(10)"', timeout=1)
    assert result.is_timeout is True
    assert result.exit_code == -1


@pytest.mark.asyncio
async def test_local_executor_batch():
    executor = LocalExecutor()
    commands = ["echo one", "echo two", "echo three"]
    results = await executor.execute_batch(commands)
    assert len(results) == 3
    assert all(isinstance(r, ExecResult) for r in results)
    assert "one" in results[0].stdout
    assert "two" in results[1].stdout
    assert "three" in results[2].stdout


@pytest.mark.asyncio
async def test_local_executor_returns_duration():
    executor = LocalExecutor()
    result = await executor.execute("echo test")
    assert result.duration > 0