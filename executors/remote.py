import asyncio
import logging
import os
import time
import asyncssh
from config import SSH_DEFAULT_TARGET, SSH_DEFAULT_USER, SSH_DEFAULT_PORT, SSH_PERSISTENT, SSH_CONNECTION_TIMEOUT, DEFAULT_TIMEOUT, SSH_DEFAULT_KEY, SSH_DEFAULT_NO_KNOWN_HOSTS
from executors.base import BaseExecutor
from models import ExecResult

logger = logging.getLogger("remote_executor")
logger.setLevel(logging.INFO)

# Windows: 确保 SSH_AUTH_SOCK 指向 OpenSSH agent 命名管道
if os.name == "nt" and "SSH_AUTH_SOCK" not in os.environ:
    os.environ["SSH_AUTH_SOCK"] = r"\\.\pipe\openssh-ssh-agent"


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

    @staticmethod
    def _is_key_path(key: str) -> bool:
        if key.startswith("/") or key.startswith("~") or "/" in key or "\\" in key:
            return True
        if os.path.isfile(key):
            return True
        return False

    @staticmethod
    def _is_encrypted_key(key_path: str) -> bool:
        try:
            with open(key_path, "r") as f:
                for _ in range(3):
                    if "ENCRYPTED" in f.readline():
                        return True
            return False
        except (OSError, UnicodeDecodeError):
            return False

    async def _connect(self, target: str, key: str = None, no_known_hosts: bool = False):
        host, user, port = self._parse_target(target)
        config_paths = [os.path.expanduser("~/.ssh/config")]
        client_keys = None
        password = None
        if key:
            if self._is_key_path(key):
                key_path = os.path.expanduser(key)
                if self._is_encrypted_key(key_path):
                    logger.info("密钥 %s 已加密，回退到 SSH agent 认证", key_path)
                else:
                    client_keys = [key_path]
            else:
                password = key
        known_hosts = None if no_known_hosts else ()
        if user is None:
            return await asyncssh.connect(
                host=host, config=config_paths, client_keys=client_keys,
                password=password, known_hosts=known_hosts,
                connect_timeout=SSH_CONNECTION_TIMEOUT,
            )
        return await asyncssh.connect(
            host=host, port=port, username=user, config=config_paths,
            client_keys=client_keys, password=password, known_hosts=known_hosts,
            connect_timeout=SSH_CONNECTION_TIMEOUT,
        )

    async def _get_connection(self, target: str, key: str = None, no_known_hosts: bool = False):
        pool_key = (target, key, no_known_hosts)
        if SSH_PERSISTENT and pool_key in self._conns:
            conn = self._conns[pool_key]
            if not conn.is_closed():
                return conn
        conn = await self._connect(target, key=key, no_known_hosts=no_known_hosts)
        if SSH_PERSISTENT:
            self._conns[pool_key] = conn
        return conn

    async def execute(self, command, target=None, key=None, no_known_hosts=None, timeout=None, env=None, cwd=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if key is None:
            key = SSH_DEFAULT_KEY
        if no_known_hosts is None:
            no_known_hosts = SSH_DEFAULT_NO_KNOWN_HOSTS
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if timeout == -1:
            timeout = None

        if cwd:
            command = f'cd "{cwd}" && {command}'

        start = time.time()
        logger.info("[remote] executing: %s", command)
        try:
            conn = await self._get_connection(target, key=key, no_known_hosts=no_known_hosts)
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

    async def execute_batch(self, commands, target=None, key=None, no_known_hosts=None, timeout=None, env=None, cwd=None):
        async def _run(cmd):
            return await self.execute(cmd, target=target, key=key, no_known_hosts=no_known_hosts, timeout=timeout, env=env, cwd=cwd)
        return await asyncio.gather(*[_run(c) for c in commands])

    async def create_session(self, command, target=None, key=None, no_known_hosts=None, cwd=None, env=None, alive_timeout=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if key is None:
            key = SSH_DEFAULT_KEY
        if no_known_hosts is None:
            no_known_hosts = SSH_DEFAULT_NO_KNOWN_HOSTS
        if cwd:
            command = f'cd "{cwd}" && {command}'
        conn = await self._get_connection(target, key=key, no_known_hosts=no_known_hosts)
        proc = await conn.create_process(command, env=env)
        return proc

    async def upload_file(self, local_path, remote_path, target=None, key=None, no_known_hosts=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if key is None:
            key = SSH_DEFAULT_KEY
        if no_known_hosts is None:
            no_known_hosts = SSH_DEFAULT_NO_KNOWN_HOSTS
        conn = await self._get_connection(target, key=key, no_known_hosts=no_known_hosts)
        async with conn.start_sftp_client() as sftp:
            await sftp.put(local_path, remote_path)

    async def download_file(self, remote_path, local_path, target=None, key=None, no_known_hosts=None):
        if target is None:
            target = SSH_DEFAULT_TARGET
        if key is None:
            key = SSH_DEFAULT_KEY
        if no_known_hosts is None:
            no_known_hosts = SSH_DEFAULT_NO_KNOWN_HOSTS
        conn = await self._get_connection(target, key=key, no_known_hosts=no_known_hosts)
        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote_path, local_path)