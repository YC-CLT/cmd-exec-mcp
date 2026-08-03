# main.py
import atexit
import os
import platform
import config
from config import (
    RESULT_FIELDS,
    SINGLETON_LOCK_FILE,
    SANDBOX_SECURITY_MODE,
    SANDBOX_COMMAND_WHITELIST,
    SANDBOX_COMMAND_BLACKLIST,
    SANDBOX_DEFAULT_IMAGE,
    SANDBOX_DEFAULT_MOUNT,
)
from executors.local import LocalExecutor
from executors.sandbox import SandboxExecutor
from fastmcp import FastMCP


def acquire_lock():
    """创建锁文件，防止多实例启动。若锁文件已存在则抛出 RuntimeError。"""
    lock_path = os.path.join(os.path.dirname(__file__), SINGLETON_LOCK_FILE)
    if os.path.exists(lock_path):
        raise RuntimeError(
            f"Another instance is already running. Lock file: {lock_path}"
        )
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))


def release_lock():
    """清理锁文件。"""
    lock_path = os.path.join(os.path.dirname(__file__), SINGLETON_LOCK_FILE)
    if os.path.exists(lock_path):
        os.remove(lock_path)


def validate_command(command: str):
    """校验命令是否允许执行。受限模式下检查白名单/黑名单，完全模式放行。"""
    if config.SECURITY_MODE == "full":
        return

    cmd_name = command.strip().split()[0] if command.strip() else ""
    if cmd_name in config.COMMAND_BLACKLIST:
        raise ValueError(f"Command '{cmd_name}' is in blacklist, execution denied")

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
            f"Command '{cmd_name}' is in sandbox blacklist, execution denied"
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
    """在本地执行命令。

    Args:
        command: 命令字符串，并行模式下用 && 分隔多个命令
        cwd: 工作目录，受限模式下忽略
        timeout: 超时秒数，None 使用默认值，-1 无限制
        env: 环境变量字典
        parallel: 是否并行执行，True 时按 && 拆分并发执行
        fields: 返回字段过滤，None 使用全局 RESULT_FIELDS 配置
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
    """在 Docker 沙箱中执行命令。

    Args:
        command: 命令字符串，并行模式下用 && 分隔
        image: Docker 镜像，None 使用 SANDBOX_DEFAULT_IMAGE
        cwd: 容器内工作目录
        mount: 挂载路径 "host:container"，None 不挂载
        timeout: 超时秒数
        env: 环境变量（容器内）
        parallel: 是否并行执行
        fields: 返回字段过滤
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
    acquire_lock()
    atexit.register(release_lock)
    mcp.run()


if __name__ == "__main__":
    main()