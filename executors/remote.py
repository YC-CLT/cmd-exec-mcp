import asyncio
import logging
import os
import time
import asyncssh
from dotenv import load_dotenv
from config import SSH_CONFIG_MODE, SSH_HOST_NAME, SSH_PERSISTENT, SSH_CONNECTION_TIMEOUT, DEFAULT_TIMEOUT
from executors.base import BaseExecutor
from models import ExecResult

logger = logging.getLogger("remote_executor")
logger.setLevel(logging.INFO)


class RemoteExecutor(BaseExecutor):
    def __init__(self):
        self._conn = None

    async def _connect(self):
        if SSH_CONFIG_MODE == "standard":
            conn = await asyncssh.connect(
                host=SSH_HOST_NAME,
                config=[os.path.expanduser("~/.ssh/config")],
                connect_timeout=SSH_CONNECTION_TIMEOUT,
            )
        else:
            load_dotenv()
            host = os.getenv("SSH_HOST")
            if not host:
                raise RuntimeError("SSH_HOST not set in .env")
            port = int(os.getenv("SSH_PORT", "22"))
            username = os.getenv("SSH_USER", "root")
            key_path = os.getenv("SSH_KEY_PATH")
            password = os.getenv("SSH_PASSWORD")
            known_hosts = os.getenv("SSH_KNOWN_HOSTS", "true").lower() == "true"
            conn = await asyncssh.connect(
                host=host,
                port=port,
                username=username,
                client_keys=[os.path.expanduser(key_path)] if key_path else None,
                password=password or None,
                known_hosts=None if known_hosts else None,
                connect_timeout=SSH_CONNECTION_TIMEOUT,
            )
        return conn

    async def _get_connection(self):
        if SSH_PERSISTENT and self._conn and not self._conn.is_closed():
            return self._conn
        conn = await self._connect()
        if SSH_PERSISTENT:
            self._conn = conn
        return conn

    async def execute(self, command, timeout=None, env=None):
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if timeout == -1:
            timeout = None

        start = time.time()
        logger.info("[remote] executing: %s", command)
        try:
            conn = await self._get_connection()
            result = await conn.run(command, timeout=timeout)
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
        except asyncio.TimeoutError:
            duration = time.time() - start
            logger.error("[remote] timeout after %.2fs", duration)
            if not SSH_PERSISTENT:
                conn.close()
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

    async def execute_batch(self, commands, timeout=None, env=None):
        async def _run(cmd):
            return await self.execute(cmd, timeout=timeout, env=env)
        return await asyncio.gather(*[_run(c) for c in commands])