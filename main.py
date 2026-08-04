# main.py
import os
import platform
import subprocess
import sys
import config
from config import (
    RESULT_FIELDS,
    SANDBOX_SECURITY_MODE,
    SANDBOX_COMMAND_WHITELIST,
    SANDBOX_COMMAND_BLACKLIST,
    SANDBOX_DEFAULT_IMAGE,
    SANDBOX_DEFAULT_MOUNT,
)
from executors.local import LocalExecutor
from executors.sandbox import SandboxExecutor
from fastmcp import FastMCP


def _count_instances():
    """统计当前脚本的进程数。"""
    script = os.path.abspath(__file__)
    if sys.platform == "win32":
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter \"name='python.exe'\").CommandLine"],
            capture_output=True, text=True,
        )
        return result.stdout.count(script)
    else:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True,
        )
        return result.stdout.count(script)


def ensure_single_instance():
    """确保单实例运行，已有实例则退出复用。"""
    if _count_instances() > 1:
        print("[cmd-exec-mcp] Instance already running, reuse it.")
        sys.exit(0)


def validate_command(command: str):
    """校验命令是否允许执行。受限模式下检查白名单/黑名单，完全模式放行。"""
    if config.SECURITY_MODE == "full":
        return

    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name in config.COMMAND_BLACKLIST:
        raise ValueError(
            f"Command '{cmd_name}' is in blacklist, execution denied. "
            f"Show the command to user for manual copy-paste instead."
        )

    if cmd_name not in config.COMMAND_WHITELIST:
        raise ValueError(
            f"Command '{cmd_name}' is not in whitelist, execution denied. "
            f"Allowed commands: {config.COMMAND_WHITELIST}"
        )


def validate_sandbox_command(command: str):
    """沙箱模式安全校验（独立于本地模式）"""
    if config.SANDBOX_SECURITY_MODE == "full":
        return

    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name in config.SANDBOX_COMMAND_BLACKLIST:
        raise ValueError(
            f"Command '{cmd_name}' is in sandbox blacklist, execution denied. "
            f"Show the command to user for manual copy-paste instead."
        )
    if config.SANDBOX_COMMAND_WHITELIST and cmd_name not in config.SANDBOX_COMMAND_WHITELIST:
        raise ValueError(
            f"Command '{cmd_name}' is not in sandbox whitelist, execution denied"
        )


def detect_shell() -> str:
    """返回当前系统应使用的 Shell 类型。"""
    if config.FORCE_SHELL:
        return config.FORCE_SHELL
    system = platform.system()
    if system == "Windows":
        return "powershell"
    return "bash"


def wrap_command(command: str) -> str:
    """根据检测到的 Shell 包装命令。"""
    shell = detect_shell()
    if shell == "powershell":
        return command
    elif shell == "cmd":
        return command
    else:
        return command


def resolve_cwd(cwd: str) -> str:
    """解析工作目录。受限模式下强制使用默认值。"""
    if config.SECURITY_MODE == "restricted":
        return config.DEFAULT_CWD
    return cwd if cwd is not None else config.DEFAULT_CWD


def resolve_timeout(timeout: int) -> int | None:
    """解析超时值。None 用默认值，-1 表示无限制。"""
    if timeout is None:
        timeout = config.DEFAULT_TIMEOUT
    if timeout == -1:
        return None
    return timeout


mcp = FastMCP("cmd-exec-mcp")
executor = LocalExecutor()
sandbox = SandboxExecutor()


@mcp.tool()
async def execute_local(
    command: str,
    cwd: str = None,
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
) -> dict | list[dict]:
    """在本地执行命令(restricted模式,白名单:ls/dir/git/python/echo/cat/type/pwd/cd)。

    command: 要执行的命令, 并行用 && 分隔 + parallel=True
    cwd: 工作目录, timeout: 超时秒数(-1无限), env: 环境变量
    parallel: 并行执行, fields: 返回字段过滤如 {"stdout": True}
    返回: {stdout, stderr, exit_code, duration, is_timeout, command_echo}

    Example:
        execute_local("echo hello")
        execute_local("echo one && echo two", parallel=True)
        execute_local("git status", timeout=10)
    """
    cwd = resolve_cwd(cwd)
    timeout = resolve_timeout(timeout)

    if parallel:
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]
        for cmd in commands:
            validate_command(cmd)
        results = await executor.execute_batch(commands, cwd=cwd, timeout=timeout, env=env)
        return [r.to_dict(fields) for r in results]

    validate_command(command)
    command = wrap_command(command)
    result = await executor.execute(command, cwd=cwd, timeout=timeout, env=env)
    return result.to_dict(fields)


@mcp.tool()
async def execute_sandbox(
    command: str,
    image: str = None,
    cwd: str = None,
    mount: str = None,
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
) -> dict | list[dict]:
    """在Docker沙箱执行命令(full模式,需本地Docker,默认ubuntu镜像)。

    command: 容器内命令, 并行用 && 分隔 + parallel=True
    image: 镜像(默认ubuntu), cwd: 容器内工作目录, mount: 挂载 host:container
    timeout: 超时秒数(-1无限), env: 容器内环境变量
    parallel: 并行执行(每个命令独立容器), fields: 返回字段过滤
    返回: {stdout, stderr, exit_code, duration, is_timeout, command_echo}

    Example:
        execute_sandbox("echo hello")
        execute_sandbox("whoami && uname -a")
        execute_sandbox("ls /data", mount="d:/data:/data", image="python:3.11")
    """
    image = image or SANDBOX_DEFAULT_IMAGE
    timeout = resolve_timeout(timeout)

    if parallel:
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]
        for cmd in commands:
            validate_sandbox_command(cmd)
        results = await sandbox.execute_batch(
            commands, cwd=cwd, timeout=timeout, env=env,
            image=image, mount=mount
        )
        return [r.to_dict(fields) for r in results]

    validate_sandbox_command(command)
    result = await sandbox.execute(
        command, cwd=cwd, timeout=timeout, env=env,
        image=image, mount=mount
    )
    return result.to_dict(fields)


def main():
    ensure_single_instance()
    mcp.run()


if __name__ == "__main__":
    main()