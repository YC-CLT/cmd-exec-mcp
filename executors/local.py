# executors/local.py
import asyncio
import logging
import os
import subprocess
import sys
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
    @staticmethod
    def _kill_process_tree(pid):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
            )

    def _run_with_timeout(self, command, cwd, env, timeout):
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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

    async def execute(self, command, cwd=None, timeout=None, env=None):
        logger.info("execute: %s", command)
        start = time.time()

        loop = asyncio.get_running_loop()
        subprocess_timeout = timeout if timeout is not None and timeout > 0 else None

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

        try:
            stdout, stderr, returncode = await loop.run_in_executor(
                None,
                lambda: self._run_with_timeout(
                    command, cwd, merged_env, subprocess_timeout
                ),
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

    async def execute_batch(self, commands, cwd=None, timeout=None, env=None):
        logger.info("execute_batch: %d commands", len(commands))
        tasks = [self.execute(cmd, cwd, timeout, env) for cmd in commands]
        return await asyncio.gather(*tasks)

    async def create_session(self, command, cwd=None, env=None, alive_timeout=None):
        loop = asyncio.get_running_loop()
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

        def _start():
            return subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env=merged_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        return await loop.run_in_executor(None, _start)