# executors/local.py
import asyncio
import time
from executors.base import BaseExecutor
from models import ExecResult


class LocalExecutor(BaseExecutor):
    async def execute(self, command, cwd=None, timeout=None, env=None):
        start = time.time()
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        try:
            if timeout is not None and timeout > 0:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            else:
                stdout, stderr = await proc.communicate()
            return ExecResult(
                command_echo=command,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                exit_code=proc.returncode or 0,
                duration=round(time.time() - start, 3),
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecResult(
                command_echo=command,
                duration=round(time.time() - start, 3),
                is_timeout=True,
                exit_code=-1,
            )

    async def execute_batch(self, commands, cwd=None, timeout=None, env=None):
        tasks = [self.execute(cmd, cwd, timeout, env) for cmd in commands]
        return await asyncio.gather(*tasks)