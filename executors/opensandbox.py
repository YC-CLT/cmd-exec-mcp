import asyncio
import subprocess
import time
from datetime import timedelta
from opensandbox.config import ConnectionConfig
from opensandbox.sandbox import Sandbox
import config
from executors.base import BaseExecutor
from models import ExecResult


class OpenSandboxExecutor(BaseExecutor):
    def __init__(self):
        self.conn = ConnectionConfig(
            domain=f"{config.SANDBOX_OPEN_SERVER_HOST}:{config.SANDBOX_OPEN_SERVER_PORT}",
            api_key=config.SANDBOX_OPEN_API_KEY or None,
        )

    async def execute(self, command, timeout=None, env=None):
        start = time.time()
        runtime_env = getattr(config, "SANDBOX_OPEN_RUNTIME_ENV", {})
        merged_env = {**runtime_env, **(env or {})}
        sandbox = await Sandbox.create(
            config.SANDBOX_OPEN_TEMPLATE,
            connection_config=self.conn,
            timeout=timedelta(seconds=timeout) if timeout and timeout > 0 else None,
            entrypoint=getattr(config, "SANDBOX_OPEN_ENTRYPOINT", None),
            env=merged_env,
        )
        try:
            prefix = getattr(config, "SANDBOX_OPEN_PREFIX", "")
            execution = await sandbox.commands.run(f"{prefix}{command}")
            stdout = "".join(msg.text for msg in execution.logs.stdout)
            stderr = "".join(msg.text for msg in execution.logs.stderr)
            return ExecResult(
                command_echo=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=execution.exit_code,
                duration=round(time.time() - start, 3),
            )
        finally:
            await sandbox.destroy()

    async def execute_batch(self, commands, timeout=None, env=None):
        tasks = [self.execute(cmd, timeout=timeout, env=env) for cmd in commands]
        return await asyncio.gather(*tasks)

    async def create_session(self, command, cwd=None, env=None, alive_timeout=None):
        loop = asyncio.get_running_loop()

        def _start():
            return subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        return await loop.run_in_executor(None, _start)