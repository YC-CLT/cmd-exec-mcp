import asyncio
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
        sandbox = await Sandbox.create(
            config.SANDBOX_OPEN_TEMPLATE,
            connection_config=self.conn,
            timeout=timedelta(seconds=timeout) if timeout and timeout > 0 else None,
            env=env or {},
        )
        try:
            execution = await sandbox.commands.run(command)
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