import pytest
import config
from main import validate_sandbox_command


class TestValidateSandboxCommand:
    def test_full_mode_allows_any_command(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_SECURITY_MODE", "full")
        validate_sandbox_command("docker ps")

    def test_blacklisted_command_raises(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_SECURITY_MODE", "restricted")
        with pytest.raises(ValueError, match="blacklist"):
            validate_sandbox_command("docker ps")

    def test_whitelist_only_allows_listed(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_SECURITY_MODE", "restricted")
        monkeypatch.setattr(config, "SANDBOX_COMMAND_WHITELIST", ["echo"])
        validate_sandbox_command("echo hello")
        with pytest.raises(ValueError, match="whitelist"):
            validate_sandbox_command("ls")

    def test_blacklist_takes_priority(self, monkeypatch):
        monkeypatch.setattr(config, "SANDBOX_SECURITY_MODE", "restricted")
        monkeypatch.setattr(config, "SANDBOX_COMMAND_WHITELIST", ["docker"])
        with pytest.raises(ValueError, match="blacklist"):
            validate_sandbox_command("docker ps")