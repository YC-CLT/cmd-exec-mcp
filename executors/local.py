# executors/local.py
import asyncio
import logging
import os
import subprocess
import time
from config import LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT
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

logger = logging.getLogger("local")


class LocalExecutor(BaseExecutor):
    async def execute(self, command, cwd=None, timeout=None, env=None):
        logger.info("execute: %s", command)
        start = time.time()

        loop = asyncio.get_running_loop()
        subprocess_timeout = timeout if timeout is not None and timeout > 0 else None

        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=subprocess_timeout,
                ),
            )
            result = ExecResult(
                command_echo=command,
                stdout=result.stdout.decode(errors="replace"),
                stderr=result.stderr.decode(errors="replace"),
                exit_code=result.returncode,
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

    async def execute_batch(self, commands, cwd=None, timeout=None, env=None):
        logger.info("execute_batch: %d commands", len(commands))
        tasks = [self.execute(cmd, cwd, timeout, env) for cmd in commands]
        return await asyncio.gather(*tasks)