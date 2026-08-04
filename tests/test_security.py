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
        monkeypatch.setattr(config, "COMMAND_LIST_MODE", "whitelist")
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
    def test_ensure_single_instance_does_not_exit_on_first_run(self, monkeypatch):
        from main import ensure_single_instance

        def _count_instances(): return 1
        monkeypatch.setattr("main._count_instances", _count_instances)

        ensure_single_instance()  # should not exit

    def test_ensure_single_instance_exits_on_second_run(self, monkeypatch):
        from main import ensure_single_instance

        def _count_instances(): return 2
        monkeypatch.setattr("main._count_instances", _count_instances)

        with pytest.raises(SystemExit):
            ensure_single_instance()


class TestSandboxBackendRouting:
    @pytest.mark.asyncio
    async def test_docker_backend_calls_sandbox_executor(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "docker")
        monkeypatch.setattr(config, "SANDBOX_SECURITY_MODE", "full")

        called_with = None
        async def mock_execute(command, timeout=None, env=None):
            nonlocal called_with
            called_with = command
            from models import ExecResult
            return ExecResult(command_echo=command)

        import main
        monkeypatch.setattr(main.sandbox, "execute", mock_execute)

        await main.execute_sandbox("echo docker")
        assert called_with == "echo docker"

    @pytest.mark.asyncio
    async def test_opensandbox_backend_calls_opensandbox_executor(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_BACKEND", "opensandbox")

        called_with = None
        async def mock_execute(command, timeout=None, env=None):
            nonlocal called_with
            called_with = command
            from models import ExecResult
            return ExecResult(command_echo=command)

        import main
        monkeypatch.setattr(main, "start_opensandbox_server", lambda: None)
        monkeypatch.setattr(main, "_opensandbox_server_started", False)
        monkeypatch.setattr(main.opensandbox, "execute", mock_execute)

        await main.execute_sandbox("echo opensandbox")
        assert called_with == "echo opensandbox"