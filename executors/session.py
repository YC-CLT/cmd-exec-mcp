import asyncio
import atexit
import logging
import os
import signal
import subprocess
import sys
import uuid
from config import SESSION_DEFAULT_ALIVE_TIMEOUT, SESSION_MAX_OUTPUT_LINES, SESSION_MAX_OUTPUT_BYTES

logger = logging.getLogger("session")


class SessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = asyncio.Lock()
        atexit.register(self._cleanup)

    async def create(self, command, cwd, env, alive_timeout, executor, **kwargs):
        if alive_timeout is None:
            alive_timeout = SESSION_DEFAULT_ALIVE_TIMEOUT
        session_id = str(uuid.uuid4())
        logger.info("session %s: creating, command=%r, timeout=%d", session_id, command, alive_timeout)
        proc = await executor.create_session(command, cwd, env, alive_timeout, **kwargs)
        session = ProcessSession(session_id=session_id, proc=proc, alive_timeout=alive_timeout)
        async with self._lock:
            self._sessions[session_id] = session
        session.start()
        logger.info("session %s: started, pid=%s", session_id, getattr(proc, 'pid', '?'))
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
        logger.info("session %s: send %d bytes", session_id, len(data))
        session.stdin_queue.put_nowait(data)
        session._reset_watchdog()

    def read(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session._reset_watchdog()
        result = {
            "stdout": "".join(session.stdout_ring),
            "stderr": "".join(session.stderr_ring),
            "exit_code": session.exit_code,
            "is_running": session.exit_code is None,
        }
        logger.info("session %s: read, stdout=%d bytes, stderr=%d bytes, running=%s",
                     session_id, len(result["stdout"]), len(result["stderr"]), result["is_running"])
        return result

    def kill(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        logger.info("session %s: killing", session_id)
        session._cleanup()
        async def _remove():
            async with self._lock:
                self._sessions.pop(session_id, None)
        asyncio.ensure_future(_remove())
        return {"killed": True, "session_id": session_id}

    def status(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        return {
            "session_id": session_id,
            "is_running": session.exit_code is None,
            "alive_timeout": session.alive_timeout,
        }

    def list_all(self):
        return [
            {
                "session_id": sid,
                "is_running": s.exit_code is None,
                "alive_timeout": s.alive_timeout,
            }
            for sid, s in self._sessions.items()
        ]

    def _cleanup(self):
        for session_id in list(self._sessions.keys()):
            session = self._sessions.get(session_id)
            if session:
                session._cleanup()
        self._sessions.clear()


def _kill_process_tree(pid):
    if pid is None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass


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
        logger.info("session %s: _read_loop started, stdout=%s, stderr=%s",
                     self.session_id,
                     "pipe" if self.proc.stdout else "none",
                     "pipe" if self.proc.stderr else "none")

        async def _read_stream(stream, name, append_fn):
            line_count = 0
            try:
                while True:
                    line = await loop.run_in_executor(None, stream.readline)
                    if not line:
                        logger.info("session %s: _read_loop %s EOF after %d lines",
                                     self.session_id, name, line_count)
                        break
                    line_count += 1
                    append_fn(line)
            except Exception as e:
                logger.warning("session %s: _read_loop %s exception: %s",
                               self.session_id, name, e)

        tasks = []
        if self.proc.stdout:
            tasks.append(asyncio.create_task(_read_stream(self.proc.stdout, "stdout", self._append_stdout)))
        if self.proc.stderr:
            tasks.append(asyncio.create_task(_read_stream(self.proc.stderr, "stderr", self._append_stderr)))

        logger.info("session %s: _read_loop waiting for %d tasks", self.session_id, len(tasks))
        try:
            await asyncio.gather(*tasks)
            logger.info("session %s: _read_loop all tasks completed", self.session_id)
        except Exception as e:
            logger.warning("session %s: _read_loop gather exception: %s", self.session_id, e)
        finally:
            self.exit_code = self.proc.poll() if hasattr(self.proc, 'poll') else None
            if self.exit_code is None:
                await asyncio.sleep(0.1)
                self.exit_code = self.proc.poll() if hasattr(self.proc, 'poll') else None
            logger.info("session %s: _read_loop exit_code=%s", self.session_id, self.exit_code)

    async def _write_loop(self):
        loop = asyncio.get_running_loop()
        logger.info("session %s: _write_loop started, stdin=%s", self.session_id,
                     "open" if self.proc.stdin and not getattr(self.proc.stdin, 'closed', False) else "closed/missing")
        try:
            while True:
                data = await self.stdin_queue.get()
                logger.info("session %s: _write_loop dequeued %d bytes", self.session_id, len(data))
                if not self.proc.stdin:
                    logger.warning("session %s: proc.stdin is None, dropping %d bytes", self.session_id, len(data))
                    continue
                if getattr(self.proc.stdin, 'closed', False):
                    logger.warning("session %s: proc.stdin is closed, dropping %d bytes", self.session_id, len(data))
                    continue
                try:
                    logger.info("session %s: writing %d bytes to stdin pipe...", self.session_id, len(data))
                    encoded = data.encode() if isinstance(data, str) else data
                    written = await loop.run_in_executor(None, self.proc.stdin.write, encoded)
                    logger.info("session %s: write() returned %s", self.session_id, written)
                    logger.info("session %s: flushing stdin pipe...", self.session_id)
                    await loop.run_in_executor(None, self.proc.stdin.flush)
                    logger.info("session %s: flush() done, data pushed to pipe", self.session_id)
                except (BrokenPipeError, OSError, ValueError) as e:
                    logger.warning("session %s: write/flush failed (%s: %s), closing stdin", self.session_id, type(e).__name__, e)
                    try:
                        self.proc.stdin.close()
                    except Exception:
                        pass
                    break
        except asyncio.CancelledError:
            logger.info("session %s: _write_loop cancelled", self.session_id)
        except Exception:
            logger.exception("session %s: _write_loop crashed", self.session_id)

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
        logger.info("session %s: cleanup, exit_code=%s", self.session_id, self.exit_code)
        if self.exit_code is None:
            _kill_process_tree(self.proc.pid)
            poll_result = self.proc.poll() if hasattr(self.proc, 'poll') else None
            self.exit_code = poll_result if poll_result is not None else -1
        for task in [self._reader_task, self._writer_task, self._watchdog_task]:
            if task and not task.done():
                task.cancel()