import asyncio
import logging
import os
import time
import asyncssh
from config import SSH_DEFAULT_TARGET, SSH_DEFAULT_USER, SSH_DEFAULT_PORT, SSH_PERSISTENT, SSH_CONNECTION_TIMEOUT, DEFAULT_TIMEOUT
from executors.base import BaseExecutor
from models import ExecResult

logger = logging.getLogger("remote_executor")
logger.setLevel(logging.INFO)


class RemoteExecutor(BaseExecutor):
    def __init__(self):
        self._conns = {}

    @staticmethod
    def _parse_target(target: str):
        if "@" in target:
            user_part, host_part = target.rsplit("@", 1)
            if host_part.startswith("["):
                bracket_end = host_part.index("]")
                host = host_part[1:bracket_end]
                port = SSH_DEFAULT_PORT
                if bracket_end + 1 < len(host_part) and host_part[bracket_end + 1] == ":":
                    port = int(host_part[bracket_end + 2:])
            elif ":" in host_part:
                host, port_str = host_part.rsplit(":", 1)
                port = int(port_str)
            else:
                host = host_part
                port = SSH_DEFAULT_PORT
            return host, user_part, port
        else:
            if ":" in target:
                host, port_str = target.rsplit(":", 1)
                return host, SSH_DEFAULT_USER, int(port_str)
            return target, None, SSH_DEFAULT_PORT

    async def _connect(self, target: str):
        host, user, port = self._parse_target(target)
        config_paths = [os.path.expanduser("~/.ssh/config")]
        if user is None:
            return await asyncssh.connect(
                host=host, config=config_paths,
                connect_timeout=SSH_CONNECTION_TIMEOUT,
            )
        return await asyncssh.connect(
            host=host, port=port, username=user,
            config=config_paths,
            connect_timeout=SSH_CONNECTION_TIMEOUT,
        )

    async def _get_connection(self, target: str):
        if SSH_PERSISTENT and target in self._conns:
            conn = self._conns[target]
            if not conn.is_closed():
                return conn
        conn = await self._connect(target)
        if SSH_PERSISTENT:
            self._conns[target] = conn
        return conn

    async def execute(self, command, target=None, timeout=None, env=None, cwd=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if timeout == -1:
            timeout = None

        if cwd:
            command = f'cd "{cwd}" && {command}'

        start = time.time()
        logger.info("[remote] executing: %s", command)
        try:
            conn = await self._get_connection(target)
            result = await conn.run(command, timeout=timeout, env=env)
            duration = time.time() - start
            ec = result.exit_status if result.exit_status is not None else 0
            if ec != 0:
                logger.warning("[remote] exit_code=%s, duration=%.2fs", ec, duration)
            else:
                logger.info("[remote] success, duration=%.2fs", duration)
            return ExecResult(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_code=ec,
                duration=duration,
                command_echo=command,
            )
        except (asyncio.TimeoutError, TimeoutError):
            duration = time.time() - start
            logger.error("[remote] timeout after %.2fs", duration)
            try:
                await conn.run(
                    "kill -- -$(ps -o pgid= -p $$) 2>/dev/null; kill -9 $$ 2>/dev/null",
                    timeout=5,
                )
            except Exception:
                logger.warning("[remote] failed to kill remote process tree", exc_info=True)
            return ExecResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration=duration,
                is_timeout=True,
                command_echo=command,
            )
        finally:
            if not SSH_PERSISTENT:
                conn.close()

    async def execute_batch(self, commands, target=None, timeout=None, env=None):
        async def _run(cmd):
            return await self.execute(cmd, target=target, timeout=timeout, env=env)
        return await asyncio.gather(*[_run(c) for c in commands])

    async def create_session(self, command, target=None, cwd=None, env=None, alive_timeout=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if cwd:
            command = f'cd "{cwd}" && {command}'
        conn = await self._get_connection(target)
        proc = await conn.create_process(command, env=env)
        return proc

    async def upload_file(self, local_path, remote_path, target=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        conn = await self._get_connection(target)
        async with conn.start_sftp_client() as sftp:
            await sftp.put(local_path, remote_path)

    async def download_file(self, remote_path, local_path, target=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        conn = await self._get_connection(target)
        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote_path, local_path)