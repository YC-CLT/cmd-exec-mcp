import asyncio
import atexit
import logging
import uuid
from config import SESSION_DEFAULT_ALIVE_TIMEOUT, SESSION_MAX_OUTPUT_LINES, SESSION_MAX_OUTPUT_BYTES

logger = logging.getLogger("session")


class SessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = asyncio.Lock()
        atexit.register(self._cleanup)

    async def create(self, command, cwd, env, alive_timeout, executor):
        if alive_timeout is None:
            alive_timeout = SESSION_DEFAULT_ALIVE_TIMEOUT
        session_id = str(uuid.uuid4())
        proc = await executor.create_session(command, cwd, env, alive_timeout)
        session = ProcessSession(session_id=session_id, proc=proc, alive_timeout=alive_timeout)
        async with self._lock:
            self._sessions[session_id] = session
        session.start()
        return {
            "session_id": session_id,
            "stdout": "",
            "stderr": "",
            "exit_code": session.exit_code,
            "is_running": session.exit_code is None,
            "alive_timeout": alive_timeout,
        }

    def send(self, session_id, data):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        if session.exit_code is not None:
            raise ValueError(f"Session {session_id} already exited")
        session.stdin_queue.put_nowait(data)
        session._reset_watchdog()

    def read(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session._reset_watchdog()
        return {
            "stdout": "".join(session.stdout_ring),
            "stderr": "".join(session.stderr_ring),
            "exit_code": session.exit_code,
            "is_running": session.exit_code is None,
        }

    def kill(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session._cleanup()
        async def _remove():
            async with self._lock:
                self._sessions.pop(session_id, None)
        asyncio.ensure_future(_remove())
        return {"killed": True, "session_id": session_id}

    def _cleanup(self):
        for session_id in list(self._sessions.keys()):
            session = self._sessions.get(session_id)
            if session:
                session._cleanup()
        self._sessions.clear()


class ProcessSession:
    def __init__(self, session_id, proc, alive_timeout):
        self.session_id = session_id
        self.proc = proc
        self.alive_timeout = alive_timeout
        self.stdout_ring = []
        self.stderr_ring = []
        self.stdin_queue = asyncio.Queue()
        self.exit_code = None
        self._reader_task = None
        self._writer_task = None
        self._watchdog_task = None
        self._lock = asyncio.Lock()
        self._total_bytes = 0

    def start(self):
        loop = asyncio.get_running_loop()
        self._reader_task = asyncio.ensure_future(self._read_loop(loop))
        self._writer_task = asyncio.ensure_future(self._write_loop())
        if self.alive_timeout > 0:
            self._watchdog_task = asyncio.ensure_future(self._watchdog_loop())

    async def _read_loop(self, loop):
        try:
            while True:
                if self.proc.stdout:
                    line = await loop.run_in_executor(None, self.proc.stdout.readline)
                    if not line:
                        break
                    self._append_stdout(line)
                if self.proc.stderr:
                    line = await loop.run_in_executor(None, self.proc.stderr.readline)
                    if not line:
                        break
                    self._append_stderr(line)
        except Exception:
            pass
        finally:
            self.exit_code = self.proc.poll() if hasattr(self.proc, 'poll') else None

    async def _write_loop(self):
        try:
            while True:
                data = await self.stdin_queue.get()
                if self.proc.stdin:
                    self.proc.stdin.write(data)
                    self.proc.stdin.flush()
        except Exception:
            pass

    async def _watchdog_loop(self):
        await asyncio.sleep(self.alive_timeout)
        self._cleanup()

    def _reset_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if self.alive_timeout > 0:
            self._watchdog_task = asyncio.ensure_future(self._watchdog_loop())

    def _append_stdout(self, line):
        encoded = line if isinstance(line, str) else line.decode(errors="replace")
        self._total_bytes += len(encoded)
        if len(self.stdout_ring) >= SESSION_MAX_OUTPUT_LINES or self._total_bytes > SESSION_MAX_OUTPUT_BYTES:
            self.stdout_ring.pop(0)
        self.stdout_ring.append(encoded)

    def _append_stderr(self, line):
        encoded = line if isinstance(line, str) else line.decode(errors="replace")
        self._total_bytes += len(encoded)
        if len(self.stderr_ring) >= SESSION_MAX_OUTPUT_LINES or self._total_bytes > SESSION_MAX_OUTPUT_BYTES:
            self.stderr_ring.pop(0)
        self.stderr_ring.append(encoded)

    def _cleanup(self):
        if self.exit_code is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.exit_code = self.proc.poll() if hasattr(self.proc, 'poll') else -1
        for task in [self._reader_task, self._writer_task, self._watchdog_task]:
            if task and not task.done():
                task.cancel()