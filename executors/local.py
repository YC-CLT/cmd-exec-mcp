# executors/local.py
import asyncio
import logging
import os
import re
import signal
import subprocess
import sys
import time
import config
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


def _env_from_registry():
    _env = {}
    import winreg
    def _read_key(key):
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                _env[name.upper()] = str(value)
                i += 1
            except OSError:
                break
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
            _read_key(key)
    except OSError:
        pass
    # 2. 读 HKCU：用户级环境（覆盖同名的机器段）
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            _read_key(key)
    except OSError:
        pass
    # 3. 补全系统变量（注册表中可能不含 SystemRoot，ExpandEnvironmentStrings 需要）
    _sysvars = {
        "SYSTEMROOT": os.environ.get("SystemRoot", os.path.join(
            os.environ.get("SystemDrive", "C:"), "Windows")),
        "SYSTEMDRIVE": os.environ.get("SystemDrive", "C:"),
        "WINDIR": os.environ.get("windir", os.path.join(
            os.environ.get("SystemDrive", "C:"), "Windows")),
    }
    for k, v in _sysvars.items():
        _env.setdefault(k, v)
    # 4. 展开 %VAR% 引用
    def _expand(m):
        var = m.group(1)
        return _env.get(var.upper(), os.environ.get(var, m.group(0)))
    for k in list(_env.keys()):
        expanded = re.sub(r"%([^%]+)%", _expand, _env[k])
        if expanded != _env[k]:
            _env[k] = expanded
    return _env


def _env_from_inherit():
    return os.environ.copy()


def _build_base_env():
    if os.name == "nt" and config.ENV_SOURCE == "registry":
        try:
            base = _env_from_registry()
        except Exception:
            logger.warning("registry env rebuild failed, falling back to inherit")
            base = _env_from_inherit()
    else:
        base = _env_from_inherit()
    return base


def _apply_strip_and_defaults(env):
    for name in config.ENV_STRIP_NAMES:
        env.pop(name, None)
    if "PATH" in env:
        parts = env["PATH"].split(os.pathsep)
        parts = [p for p in parts
                 if not any(keyword in p.lower()
                           for keyword in ("\\test_host\\", "\\.test_host\\"))]
        env["PATH"] = os.pathsep.join(parts)
    for k, v in config.ENV_DEFAULTS.items():
        env.setdefault(k, v)


class LocalExecutor(BaseExecutor):
    @staticmethod
    def _kill_process_tree(pid):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
            )
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

    def _run_with_timeout(self, command, cwd, env, timeout):
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
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

        merged_env = _build_base_env()
        _apply_strip_and_defaults(merged_env)
        merged_env.pop("VIRTUAL_ENV", None)
        if sys.prefix != sys.base_prefix:
            path_parts = merged_env.get("PATH", "").split(os.pathsep)
            path_parts = [
                p for p in path_parts
                if not os.path.normpath(p).lower().startswith(os.path.normpath(sys.prefix).lower())
            ]
            merged_env["PATH"] = os.pathsep.join(path_parts)
        if env:
            for k, v in env.items():
                if v is None:
                    merged_env.pop(k, None)
                else:
                    merged_env[k] = v

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
        merged_env = _build_base_env()
        _apply_strip_and_defaults(merged_env)
        merged_env.pop("VIRTUAL_ENV", None)
        if sys.prefix != sys.base_prefix:
            path_parts = merged_env.get("PATH", "").split(os.pathsep)
            path_parts = [
                p for p in path_parts
                if not os.path.normpath(p).lower().startswith(os.path.normpath(sys.prefix).lower())
            ]
            merged_env["PATH"] = os.pathsep.join(path_parts)
        if env:
            for k, v in env.items():
                if v is None:
                    merged_env.pop(k, None)
                else:
                    merged_env[k] = v

        def _start():
            return subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env=merged_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

        return await loop.run_in_executor(None, _start)