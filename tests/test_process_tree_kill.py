import os
import signal
import subprocess
import sys
import pytest
from executors import local as local_module
from executors import sandbox as sandbox_module


class TestKillProcessTreeLinux:
    def test_linux_calls_killpg(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        killpg_calls = []
        getpgid_calls = []

        def fake_killpg(pgid, sig):
            killpg_calls.append((pgid, sig))

        def fake_getpgid(pid):
            getpgid_calls.append(pid)
            return pid

        monkeypatch.setattr(os, "killpg", fake_killpg)
        monkeypatch.setattr(os, "getpgid", fake_getpgid)

        local_module.LocalExecutor._kill_process_tree(12345)

        assert getpgid_calls == [12345]
        assert killpg_calls == [(12345, signal.SIGKILL)]

    def test_linux_killpg_process_lookup_error_is_silent(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        def fake_killpg(pgid, sig):
            raise ProcessLookupError()

        monkeypatch.setattr(os, "killpg", fake_killpg)
        monkeypatch.setattr(os, "getpgid", lambda pid: pid)

        local_module.LocalExecutor._kill_process_tree(12345)

    def test_linux_killpg_os_error_is_silent(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        def fake_killpg(pgid, sig):
            raise OSError()

        monkeypatch.setattr(os, "killpg", fake_killpg)
        monkeypatch.setattr(os, "getpgid", lambda pid: pid)

        local_module.LocalExecutor._kill_process_tree(12345)


class TestKillProcessTreeWindows:
    def test_windows_calls_taskkill(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        run_calls = []

        def fake_run(args, **kwargs):
            run_calls.append(args)

        monkeypatch.setattr(subprocess, "run", fake_run)

        local_module.LocalExecutor._kill_process_tree(12345)

        assert run_calls == [["taskkill", "/F", "/T", "/PID", "12345"]]


class TestKillProcessTreeSandbox:
    def test_sandbox_linux_calls_killpg(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        killpg_calls = []

        def fake_killpg(pgid, sig):
            killpg_calls.append((pgid, sig))

        monkeypatch.setattr(os, "killpg", fake_killpg)
        monkeypatch.setattr(os, "getpgid", lambda pid: pid)

        sandbox_module.SandboxExecutor._kill_process_tree(12345)

        assert killpg_calls == [(12345, signal.SIGKILL)]