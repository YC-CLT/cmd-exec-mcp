import os
import signal
import sys
import pytest
from executors import session as session_module


class FakeProcForCleanup:
    def __init__(self, pid=12345, returncode=None):
        self.pid = pid
        self.returncode = returncode
        self.stdin = None

    def poll(self):
        return self.returncode


@pytest.mark.asyncio
async def test_cleanup_calls_kill_process_tree_on_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", lambda pid: pid)

    proc = FakeProcForCleanup(pid=12345)
    ps = session_module.ProcessSession("test-id", proc, alive_timeout=0)
    ps._reader_task = None
    ps._writer_task = None
    ps._watchdog_task = None

    ps._cleanup()

    assert killpg_calls == [(12345, signal.SIGKILL)]
    assert ps.exit_code == -1


@pytest.mark.asyncio
async def test_cleanup_handles_none_pid(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", lambda pid: pid)

    proc = FakeProcForCleanup(pid=None)
    ps = session_module.ProcessSession("test-id", proc, alive_timeout=0)
    ps._reader_task = None
    ps._writer_task = None
    ps._watchdog_task = None

    ps._cleanup()

    assert killpg_calls == []


@pytest.mark.asyncio
async def test_cleanup_process_lookup_error_silent(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    def fake_killpg(pgid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", lambda pid: pid)

    proc = FakeProcForCleanup(pid=12345)
    ps = session_module.ProcessSession("test-id", proc, alive_timeout=0)
    ps._reader_task = None
    ps._writer_task = None
    ps._watchdog_task = None

    ps._cleanup()


@pytest.mark.asyncio
async def test_cleanup_already_exited_process(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    killpg_calls = []

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))

    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(os, "getpgid", lambda pid: pid)

    proc = FakeProcForCleanup(pid=12345, returncode=0)
    ps = session_module.ProcessSession("test-id", proc, alive_timeout=0)
    ps._reader_task = None
    ps._writer_task = None
    ps._watchdog_task = None
    ps.exit_code = 0

    ps._cleanup()

    assert killpg_calls == []