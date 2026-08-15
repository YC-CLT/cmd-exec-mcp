import asyncio
import pytest
from executors.session import SessionManager


@pytest.fixture
def session_manager():
    mgr = SessionManager()
    yield mgr
    mgr._cleanup()


class FakeExecutor:
    def __init__(self):
        pass

    async def create_session(self, command, cwd, env, alive_timeout):
        return FakeProcess()


class FakeProcess:
    def __init__(self):
        self.pid = 12345
        self.stdin = FakeStdin()
        self.stdout_lines = [b"hello\n", b"world\n"]
        self.stderr_lines = []
        self.returncode = None
        self._stdout_idx = 0

    @property
    def stdout(self):
        return FakeStdout(self)

    @property
    def stderr(self):
        return FakeStderr(self)

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        if self._stdout_idx >= len(self.stdout_lines):
            return 0
        return None

    def terminate(self):
        self.returncode = -15


class FakeStdout:
    def __init__(self, proc):
        self._proc = proc

    def readline(self):
        if self._proc._stdout_idx < len(self._proc.stdout_lines):
            line = self._proc.stdout_lines[self._proc._stdout_idx]
            self._proc._stdout_idx += 1
            return line
        return b""


class FakeStderr:
    def __init__(self, proc=None):
        pass

    def readline(self):
        return b""


class FakeStdin:
    def __init__(self):
        self.written = []
        self.closed = False

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_create_session_returns_session_id(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("echo hello", ".", {}, 300, executor)
    assert "session_id" in result
    assert len(result["session_id"]) == 36


@pytest.mark.asyncio
async def test_send_and_read(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("cat", ".", {}, 300, executor)
    sid = result["session_id"]
    session_manager.send(sid, "input data\n")
    read_result = session_manager.read(sid)
    assert "stdout" in read_result
    assert "stderr" in read_result


@pytest.mark.asyncio
async def test_kill_session(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("cat", ".", {}, 300, executor)
    sid = result["session_id"]
    kill_result = session_manager.kill(sid)
    assert kill_result["killed"] is True
    assert kill_result["session_id"] == sid


@pytest.mark.asyncio
async def test_read_nonexistent_session(session_manager):
    with pytest.raises(ValueError, match="not found"):
        session_manager.read("nonexistent-id")


@pytest.mark.asyncio
async def test_send_nonexistent_session(session_manager):
    with pytest.raises(ValueError, match="not found"):
        session_manager.send("nonexistent-id", "data")


@pytest.mark.asyncio
async def test_kill_nonexistent_session(session_manager):
    with pytest.raises(ValueError, match="not found"):
        session_manager.kill("nonexistent-id")


@pytest.mark.asyncio
async def test_watchdog_timeout(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("cat", ".", {}, 1, executor)
    sid = result["session_id"]
    await asyncio.sleep(1.5)
    read_result = session_manager.read(sid)
    assert read_result["is_running"] is False


@pytest.mark.asyncio
async def test_watchdog_reset_on_read(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("cat", ".", {}, 2, executor)
    sid = result["session_id"]
    await asyncio.sleep(0.5)
    session_manager.read(sid)
    await asyncio.sleep(0.5)
    read_result = session_manager.read(sid)
    assert read_result["is_running"] is True


@pytest.mark.asyncio
async def test_create_session_with_infinite_timeout(session_manager):
    executor = FakeExecutor()
    result = await session_manager.create("cat", ".", {}, -1, executor)
    assert result["alive_timeout"] == -1


@pytest.mark.asyncio
async def test_cleanup_kills_all_sessions(session_manager):
    executor = FakeExecutor()
    r1 = await session_manager.create("cat", ".", {}, 300, executor)
    r2 = await session_manager.create("cat", ".", {}, 300, executor)
    session_manager._cleanup()
    assert len(session_manager._sessions) == 0