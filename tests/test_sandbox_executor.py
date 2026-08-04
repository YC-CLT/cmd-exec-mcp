import pytest
import config
from executors.sandbox import SandboxExecutor


class TestBuildDockerCmd:
    def test_basic_command(self):
        executor = SandboxExecutor()
        cmd = executor._build_docker_cmd("echo hello", "ubuntu")
        prefix = getattr(config, "SANDBOX_DOCKER_PREFIX", "")
        assert cmd == f'docker run --rm -i --entrypoint bash ubuntu -lc "{prefix}echo hello"'

    def test_custom_image(self):
        executor = SandboxExecutor()
        cmd = executor._build_docker_cmd("ls", "alpine")
        assert "alpine" in cmd

    def test_with_mount(self):
        executor = SandboxExecutor()
        cmd = executor._build_docker_cmd("ls", "ubuntu", mount="/host:/container")
        assert "-v /host:/container" in cmd

    def test_with_cwd(self):
        executor = SandboxExecutor()
        cmd = executor._build_docker_cmd("ls", "ubuntu", cwd="/workspace")
        assert "-w /workspace" in cmd

    def test_with_mount_and_cwd(self):
        executor = SandboxExecutor()
        cmd = executor._build_docker_cmd(
            "ls", "ubuntu", mount="/host:/container", cwd="/workspace"
        )
        assert "-v /host:/container" in cmd
        assert "-w /workspace" in cmd
        assert cmd.index("-v") < cmd.index("-w") < cmd.index("ubuntu")