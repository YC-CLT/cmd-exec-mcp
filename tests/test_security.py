# tests/test_security.py
import pytest
import config
from main import validate_command, detect_shell


class TestValidateCommand:
    def test_whitelisted_command_passes(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "restricted")
        validate_command("echo hello")

    def test_blacklisted_command_raises(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "restricted")
        with pytest.raises(ValueError, match="blacklist"):
            validate_command("rm -rf /")

    def test_not_whitelisted_command_raises(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "restricted")
        with pytest.raises(ValueError, match="whitelist"):
            validate_command("unknown_command arg")

    def test_full_mode_allows_any_command(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "full")
        validate_command("rm -rf /")

    def test_blacklist_takes_priority(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "restricted")
        monkeypatch.setattr(config, "COMMAND_WHITELIST", ["rm"])
        with pytest.raises(ValueError, match="blacklist"):
            validate_command("rm file.txt")

    def test_command_with_extra_spaces(self, monkeypatch):
        monkeypatch.setattr(config, "SECURITY_MODE", "restricted")
        validate_command("  echo   hello  ")


class TestDetectShell:
    def test_force_shell_takes_priority(self, monkeypatch):
        monkeypatch.setattr(config, "FORCE_SHELL", "bash")
        assert detect_shell() == "bash"

    def test_auto_detect_returns_string(self, monkeypatch):
        monkeypatch.setattr(config, "FORCE_SHELL", None)
        shell = detect_shell()
        assert shell in ("powershell", "bash", "cmd")


class TestSingleton:
    def test_lock_file_path_is_set(self):
        from main import SINGLETON_LOCK_FILE
        assert SINGLETON_LOCK_FILE.endswith(".lock")

    def test_acquire_and_release_lock(self, tmp_path, monkeypatch):
        from main import acquire_lock, release_lock
        lock_file = tmp_path / "test.lock"
        monkeypatch.setattr("main.SINGLETON_LOCK_FILE", str(lock_file))

        acquire_lock()
        assert lock_file.exists()

        with pytest.raises(RuntimeError, match="already running"):
            acquire_lock()

        release_lock()
        assert not lock_file.exists()

    def test_acquire_lock_after_release(self, tmp_path, monkeypatch):
        from main import acquire_lock, release_lock
        lock_file = tmp_path / "test.lock"
        monkeypatch.setattr("main.SINGLETON_LOCK_FILE", str(lock_file))

        acquire_lock()
        release_lock()
        acquire_lock()  # should succeed after release
        release_lock()