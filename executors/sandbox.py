import asyncio
import logging
import os
import time
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
        parts = ["docker", "run", "--rm", "-i"]
        if mount:
            parts.extend(["-v", mount])
        if cwd:
            parts.extend(["-w", cwd])
        parts.append(image)
        parts.extend(["sh", "-c", command])
        return " ".join(parts)

    async def execute(self, command, timeout=None, env=None):
        image = SANDBOX_DEFAULT_IMAGE
        docker_cmd = self._build_docker_cmd(command, image, SANDBOX_DEFAULT_MOUNT)
        logger.info("execute: image=%s cmd=%s", image, command)

        start = time.time()
        proc = await asyncio.create_subprocess_shell(
            docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            if timeout is not None and timeout > 0:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            else:
                stdout, stderr = await proc.communicate()
            result = ExecResult(
                command_echo=command,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                exit_code=proc.returncode or 0,
                duration=round(time.time() - start, 3),
            )
            level = logging.WARNING if result.exit_code != 0 else logging.INFO
            logger.log(level, "exit_code=%s duration=%.3f", result.exit_code, result.duration)
            return result
        except asyncio.TimeoutError:
            proc.kill()
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