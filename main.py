# main.py
import atexit
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
)
from executors.local import LocalExecutor
from executors.sandbox import SandboxExecutor
from executors.opensandbox import OpenSandboxExecutor
from executors.remote import RemoteExecutor
from fastmcp import FastMCP


def _handle_output_file(result, output_file: str):
    """将完整 stdout 写入指定路径，stdout 截断为预览。

    output_file 应为绝对路径，如 D:/myproject/result.txt。
    文件名会经过 basename 消毒防止路径穿越。
    """
    if not output_file:
        return result
    safe_name = os.path.basename(output_file) or "output.txt"
    if os.path.isabs(output_file):
        filepath = os.path.join(os.path.dirname(output_file), safe_name)
    else:
        filepath = os.path.join(os.getcwd(), safe_name)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result.stdout)
    truncate_len = config.OUTPUT_TRUNCATE_LENGTH
    if len(result.stdout) > truncate_len:
        result.stdout = result.stdout[:truncate_len] + f"\n... (truncated, full output at {safe_name})"
    result.output_file = safe_name
    return result


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
    """校验命令是否允许执行。受限模式下检查，完全模式放行。"""
    if config.SECURITY_MODE == "full":
        return

    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name in config.COMMAND_BLACKLIST:
        raise ValueError(
            f"Command '{cmd_name}' is in blacklist, execution denied. "
            f"Show the command to user for manual copy-paste instead."
        )

    if config.COMMAND_LIST_MODE == "whitelist" and cmd_name not in config.COMMAND_WHITELIST:
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
    if config.SANDBOX_COMMAND_LIST_MODE == "whitelist" and config.SANDBOX_COMMAND_WHITELIST and cmd_name not in config.SANDBOX_COMMAND_WHITELIST:
        raise ValueError(
            f"Command '{cmd_name}' is not in sandbox whitelist, execution denied"
        )


def detect_shell() -> str:
    """返回当前系统应使用的 Shell 类型。"""
    if config.FORCE_SHELL:
        return config.FORCE_SHELL
    system = platform.system()
    if system == "Windows":
        return "cmd"
    return "bash"


def wrap_command(command: str, shell: str = None) -> str:
    """根据检测到的 Shell 包装命令。shell 参数可覆盖自动检测。"""
    shell = shell or detect_shell()
    if shell == "powershell" or shell == "pwsh":
        escaped = command.replace('"', '\\"')
        return f'pwsh -Command "{escaped}"'
    elif shell == "cmd":
        # shell=True 已使用 cmd.exe，无需再包装 cmd /c，避免双层转义
        return command
    else:
        escaped = command.replace("'", "'\\''")
        return f"bash -c '{escaped}'"


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
opensandbox = OpenSandboxExecutor()
_remote_executor = RemoteExecutor()
_opensandbox_server_started = False


def start_opensandbox_server():
    """启动 opensandbox-server 子进程。"""
    config_path = os.path.join(os.path.dirname(__file__), "docs", "opensandbox", ".sandbox.toml")
    proc = subprocess.Popen(
        ["opensandbox-server", "--config", config_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(lambda: proc.terminate())
    return proc


@mcp.tool()
async def execute_local(
    command: str,
    cwd: str,
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    shell: str = None,
    output_file: str = "",
) -> dict | list[dict]:
    """在本地执行命令（受限模式黑白名单校验，完全模式放行）。

    command: 要执行的命令, 并行用 && 分隔 + parallel=True
    cwd: 工作目录（必填）, timeout: 超时秒数(-1无限), env: 环境变量
    parallel: 并行执行, fields: 返回字段过滤如 {"stdout": True}
    shell: 指定 Shell，可选 "pwsh"|"cmd"|"bash"，默认自动检测
    output_file: 输出过长时指定绝对路径如 D:/project/out.txt，完整 stdout 落盘，返回截断预览
    返回: {stdout, stderr, exit_code, duration, is_timeout, command_echo, output_file}

    Example:
        execute_local("echo hello", cwd="D:/project")
        execute_local("echo one && echo two", cwd="D:/project", parallel=True)
        execute_local("git status", cwd="D:/project", timeout=10)
        execute_local("echo hello", cwd="D:/project", shell="cmd")
        execute_local("cat huge.log", cwd="D:/project", output_file="D:/project/huge_log.txt")
    """
    timeout = resolve_timeout(timeout)

    if parallel:
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]
        for cmd in commands:
            validate_command(cmd)
        commands = [wrap_command(cmd, shell) for cmd in commands]
        results = await executor.execute_batch(commands, cwd=cwd, timeout=timeout, env=env)
        return [r.to_dict(fields) for r in results]

    validate_command(command)
    command = wrap_command(command, shell)
    result = await executor.execute(command, cwd=cwd, timeout=timeout, env=env)
    return _handle_output_file(result, output_file).to_dict(fields)


@mcp.tool()
async def execute_sandbox(
    command: str,
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    output_file: str = "",
) -> dict | list[dict]:
    """在沙箱中执行命令。

    无 cwd/shell 参数；并行时每个命令独立容器，其余参数和返回格式同 execute_local

    Example:
        execute_sandbox("echo hello")
        execute_sandbox("whoami && uname -a")
        execute_sandbox("pip install numpy && python -c 'import numpy'", timeout=120)
    """
    global _opensandbox_server_started
    timeout = resolve_timeout(timeout)

    if config.SANDBOX_BACKEND == "opensandbox" and not _opensandbox_server_started:
        start_opensandbox_server()
        _opensandbox_server_started = True

    if parallel:
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]
        if config.SANDBOX_BACKEND == "docker":
            for cmd in commands:
                validate_sandbox_command(cmd)
            results = await sandbox.execute_batch(
                commands, timeout=timeout, env=env
            )
        else:
            results = await opensandbox.execute_batch(
                commands, timeout=timeout, env=env
            )
        return [r.to_dict(fields) for r in results]

    if config.SANDBOX_BACKEND == "docker":
        validate_sandbox_command(command)
        result = await sandbox.execute(
            command, timeout=timeout, env=env
        )
    else:
        result = await opensandbox.execute(
            command, timeout=timeout, env=env
        )
    return _handle_output_file(result, output_file).to_dict(fields)


@mcp.tool()
async def execute_remote(
    command: str,
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    output_file: str = "",
) -> dict | list[dict]:
    """在远程服务器执行命令（SSH，受限模式黑白名单同 execute_local）。

    无 cwd/shell 参数，其余参数和返回格式同 execute_local

    Example:
        execute_remote("ls -la")
        execute_remote("whoami && uname -a", parallel=True)
        execute_remote("docker ps", timeout=10)
    """
    global _remote_executor
    timeout = resolve_timeout(timeout)

    if parallel:
        commands = [cmd.strip() for cmd in command.split("&&") if cmd.strip()]
        for cmd in commands:
            validate_command(cmd)
        results = await _remote_executor.execute_batch(commands, timeout=timeout, env=env)
        return [r.to_dict(fields) for r in results]

    validate_command(command)
    result = await _remote_executor.execute(command, timeout=timeout, env=env)
    return _handle_output_file(result, output_file).to_dict(fields)


def main():
    ensure_single_instance()
    mcp.run()


if __name__ == "__main__":
    main()