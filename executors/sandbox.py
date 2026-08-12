import asyncio
import logging
import os
import subprocess
import sys
import time
import config
from config import (
    LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT,
    SANDBOX_DEFAULT_IMAGE, SANDBOX_DEFAULT_MOUNT,
)
from executors.base import BaseExecutor
from models import ExecResult

_log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_log_path = os.path.join(_log_dir, LOG_FILE)

logging.basicConfig(
    filename=_log_path,
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
)

logger = logging.getLogger("sandbox")


class SandboxExecutor(BaseExecutor):
    def _build_docker_cmd(self, command, image, mount=None, cwd=None):
        parts = ["docker", "run", "--rm", "-i", "--entrypoint", "bash"]
        if mount:
            parts.extend(["-v", mount])
        if cwd:
            parts.extend(["-w", cwd])
        parts.append(image)
        prefix = getattr(config, "SANDBOX_DOCKER_PREFIX", "")
        parts.append(f'-lc "{prefix}{command}"')
        return " ".join(parts)

    @staticmethod
    def _kill_process_tree(pid):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
            )

    def _run_with_timeout(self, docker_cmd, timeout, env=None):
        merged_env = os.environ.copy()
        merged_env.pop("VIRTUAL_ENV", None)
        if sys.prefix != sys.base_prefix:
            path_parts = merged_env.get("PATH", "").split(os.pathsep)
            path_parts = [
                p for p in path_parts
                if not os.path.normpath(p).lower().startswith(os.path.normpath(sys.prefix).lower())
            ]
            merged_env["PATH"] = os.pathsep.join(path_parts)
        if env:
            merged_env.update(env)
        proc = subprocess.Popen(
            docker_cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return (
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
                proc.returncode or 0,
            )
        except subprocess.TimeoutExpired:
            self._kill_process_tree(proc.pid)
            proc.kill()
            proc.wait()
            raise

    async def execute(self, command, timeout=None, env=None):
        image = SANDBOX_DEFAULT_IMAGE
        docker_cmd = self._build_docker_cmd(command, image, SANDBOX_DEFAULT_MOUNT)
        logger.info("execute: image=%s cmd=%s", image, command)

        start = time.time()
        loop = asyncio.get_running_loop()
        subprocess_timeout = timeout if timeout is not None and timeout > 0 else None

        try:
            stdout, stderr, returncode = await loop.run_in_executor(
                None,
                lambda: self._run_with_timeout(docker_cmd, subprocess_timeout, env),
            )
            result = ExecResult(
                command_echo=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=returncode,
                duration=round(time.time() - start, 3),
            )
            level = logging.WARNING if result.exit_code != 0 else logging.INFO
            logger.log(level, "exit_code=%s duration=%.3f", result.exit_code, result.duration)
            return result
        except subprocess.TimeoutExpired:
            logger.error("timeout: %s", command)
            return ExecResult(
                command_echo=command,
                duration=round(time.time() - start, 3),
                is_timeout=True,
                exit_code=-1,
            )

    async def execute_batch(self, commands, timeout=None, env=None):
        logger.info("execute_batch: %d commands image=%s", len(commands), SANDBOX_DEFAULT_IMAGE)
        tasks = [self.execute(cmd, timeout, env) for cmd in commands]
        return await asyncio.gather(*tasks)