# main.py
import asyncio
import atexit
import os
import platform
import subprocess
import sys
import time
import uuid
import urllib.request
from datetime import timedelta
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
from executors.session import SessionManager
from models import ExecResult
from opensandbox.sandbox import Sandbox
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
    if shell == "wsl":
        distro = config.WSL_DISTRO
        user = config.WSL_USER
        distro_arg = f"-d {distro} " if distro else ""
        escaped = command.replace('"', '\\"')
        return f'wsl {distro_arg}-u {user} --shell-type standard -- bash -c "{escaped}"'
    elif shell == "powershell" or shell == "pwsh":
        escaped = command.replace('"', '\\"')
        preamble = (
            "[console]::InputEncoding = [console]::OutputEncoding = "
            "New-Object System.Text.UTF8Encoding; "
            "$PSStyle.OutputRendering = 'PlainText'"
        )
        return f'pwsh -NoProfile -NonInteractive -Command "{preamble}; {escaped}"'
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
session_manager = SessionManager()
_opensandbox_server_started = False
_opensandbox_server_proc = None
_opensandbox_last_used = 0.0
_opensandbox_idle_task = None
_opensandbox_sessions = {}
_opensandbox_sessions_lock = asyncio.Lock()


def start_opensandbox_server():
    """启动 opensandbox-server 子进程，等待就绪后返回。"""
    global _opensandbox_server_proc, _opensandbox_idle_task
    config_path = os.path.join(os.path.dirname(__file__), "docs", "opensandbox", ".sandbox.toml")
    proc = subprocess.Popen(
        ["opensandbox-server", "--config", config_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _opensandbox_server_proc = proc
    atexit.register(_opensandbox_shutdown)

    _wait_for_server_ready()
    _opensandbox_last_used = time.time()
    _schedule_idle_watchdog()


def _wait_for_server_ready():
    """轮询 health 端点直到 server 就绪或超时。"""
    host = config.SANDBOX_OPEN_SERVER_HOST or "localhost"
    port = config.SANDBOX_OPEN_SERVER_PORT or 8080
    url = f"http://{host}:{port}/health"
    deadline = time.time() + config.SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(
        f"OpenSandbox server did not become ready within {config.SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT}s"
    )


def _ensure_opensandbox_server():
    """确保 server 在运行，崩了则重启。"""
    global _opensandbox_server_started, _opensandbox_server_proc
    if _opensandbox_server_proc is not None and _opensandbox_server_proc.poll() is not None:
        _opensandbox_server_started = False
        _opensandbox_server_proc = None
    if not _opensandbox_server_started:
        start_opensandbox_server()
        _opensandbox_server_started = True


def _opensandbox_shutdown():
    """关闭 server 子进程 + 取消 idle watchdog。"""
    global _opensandbox_server_proc, _opensandbox_idle_task, _opensandbox_server_started
    if _opensandbox_idle_task and not _opensandbox_idle_task.done():
        _opensandbox_idle_task.cancel()
    if _opensandbox_server_proc and _opensandbox_server_proc.poll() is None:
        _opensandbox_server_proc.terminate()
    _opensandbox_server_started = False


def _schedule_idle_watchdog():
    """启动后台 idle 超时监控。"""
    global _opensandbox_idle_task
    if config.SANDBOX_OPEN_SERVER_IDLE_TIMEOUT <= 0:
        return
    if _opensandbox_idle_task and not _opensandbox_idle_task.done():
        _opensandbox_idle_task.cancel()
    _opensandbox_idle_task = asyncio.ensure_future(_idle_watchdog_loop())


async def _idle_watchdog_loop():
    """每 30 秒检查，空闲超时则关闭 server。"""
    try:
        while True:
            await asyncio.sleep(30)
            elapsed = time.time() - _opensandbox_last_used
            if elapsed >= config.SANDBOX_OPEN_SERVER_IDLE_TIMEOUT:
                _opensandbox_shutdown()
                break
    except asyncio.CancelledError:
        pass


async def _watchdog_loop(session_id, alive_timeout):
    try:
        await asyncio.sleep(alive_timeout)
    except asyncio.CancelledError:
        return
    await _opensandbox_session_cleanup(session_id)


async def _reset_watchdog(session_id):
    async with _opensandbox_sessions_lock:
        session = _opensandbox_sessions.get(session_id)
        if session is None:
            return
        old_task = session.get("watchdog_task")
        if old_task and not old_task.done():
            old_task.cancel()
        session["watchdog_task"] = asyncio.ensure_future(
            _watchdog_loop(session_id, session["alive_timeout"])
        )


async def _opensandbox_session_cleanup(session_id):
    async with _opensandbox_sessions_lock:
        session = _opensandbox_sessions.pop(session_id, None)
    if session is None:
        return
    task = session.get("watchdog_task")
    if task and not task.done():
        task.cancel()
    try:
        await opensandbox.delete_session(session["sandbox"], session["os_session_id"])
    except (Exception, asyncio.CancelledError):
        pass


async def _opensandbox_session_create(command, env, alive_timeout):
    _ensure_opensandbox_server()
    sandbox, os_session_id = await opensandbox.create_session(
        command, cwd=None, env=env, alive_timeout=alive_timeout
    )
    session_id = str(uuid.uuid4())
    last_result = None
    if command:
        try:
            last_result = await opensandbox.run_in_session(
                sandbox, os_session_id, command
            )
        except Exception as e:
            last_result = ExecResult(
                command_echo=command, stdout="", stderr=str(e),
                exit_code=-1, duration=0,
            )

    session = {
        "sandbox": sandbox,
        "os_session_id": os_session_id,
        "last_result": last_result,
        "cwd": None,
        "alive_timeout": alive_timeout,
        "last_used": time.time(),
        "watchdog_task": None,
    }
    async with _opensandbox_sessions_lock:
        _opensandbox_sessions[session_id] = session

    await _reset_watchdog(session_id)
    _opensandbox_last_used = time.time()
    return {"session_id": session_id}


async def _opensandbox_session_dispatch(session_id, action, command, timeout):
    async with _opensandbox_sessions_lock:
        session = _opensandbox_sessions.get(session_id)
        if session is None:
            return {"success": False, "error": f"session {session_id} not found or expired"}
        sandbox = session["sandbox"]
        os_session_id = session["os_session_id"]

    if action == "read":
        last_result = session["last_result"]
        if last_result is None:
            return {"stdout": "", "stderr": "", "exit_code": None, "is_running": True}
        await _reset_watchdog(session_id)
        _opensandbox_last_used = time.time()
        return {
            "stdout": last_result.stdout,
            "stderr": last_result.stderr,
            "exit_code": last_result.exit_code,
            "is_running": False,
        }

    if action == "kill":
        await _opensandbox_session_cleanup(session_id)
        return {"killed": True, "session_id": session_id}

    if action == "send":
        try:
            result = await opensandbox.run_in_session(
                sandbox, os_session_id, command, timeout=timeout
            )
        except Exception as e:
            await _opensandbox_session_cleanup(session_id)
            return {"success": False, "error": f"sandbox error: {e}"}
        async with _opensandbox_sessions_lock:
            s = _opensandbox_sessions.get(session_id)
            if s is not None:
                s["last_result"] = result
                s["last_used"] = time.time()
        await _reset_watchdog(session_id)
        _opensandbox_last_used = time.time()
        return result.to_dict()

    return {"success": False, "error": f"unknown action: {action}"}


async def _cleanup_all_opensandbox_sessions():
    async with _opensandbox_sessions_lock:
        sessions = dict(_opensandbox_sessions)
        _opensandbox_sessions.clear()
    for sid, session in sessions.items():
        task = session.get("watchdog_task")
        if task and not task.done():
            task.cancel()
        try:
            await opensandbox.delete_session(session["sandbox"], session["os_session_id"])
        except (Exception, asyncio.CancelledError):
            pass


def _atexit_cleanup_opensandbox():
    try:
        asyncio.run(_cleanup_all_opensandbox_sessions())
    except RuntimeError:
        pass


atexit.register(_atexit_cleanup_opensandbox)


@mcp.tool()
async def execute_local(
    command: str = "",
    cwd: str = "",
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    shell: str = None,
    output_file: str = "",
    detach: bool = False,
    session_id: str = None,
    action: str = "send",
    alive_timeout: int = None,
) -> dict | list[dict]:
    """在本地执行 Shell 命令，支持黑白名单校验、并行执行、会话管理。

    command: 命令字符串，并行使 && 分隔 + parallel=True
    cwd: 工作目录（必填）
    timeout: 超时秒数，-1 无限，默认 30
    env: 环境变量 dict，如 {"NODE_ENV": "production"}
    parallel: True 时按 && 拆分并行执行
    fields: 返回字段过滤，如 {"stdout": True, "exit_code": True}
    shell: 指定解释器 "cmd"|"pwsh"|"bash"|"wsl"，默认自动检测
    output_file: 输出过长时指定绝对路径落盘，返回截断预览
    detach: True 后台运行，返回 session_id 供后续 read/send/kill
    session_id: 已有会话 ID，与 action 配合
    action: "read" 读输出 | "send" 发 stdin | "kill" 终止
    alive_timeout: 会话保活超时秒数，默认 300

    返回: {stdout, stderr, exit_code, duration, is_timeout, command_echo, output_file}

    示例:
        execute_local("git status", cwd="D:/project")
        execute_local("npm install", cwd="D:/project", timeout=120)
        execute_local("go build && go test", cwd="D:/project", parallel=True)
        execute_local("python -c 'print(input())'", cwd="D:/project", detach=True)
        execute_local(session_id="xxx", action="read")
        execute_local(session_id="xxx", action="kill")
    """
    if session_id:
        if action == "read":
            return session_manager.read(session_id)
        elif action == "kill":
            return session_manager.kill(session_id)
        elif action == "send":
            session_manager.send(session_id, command)
            return {"sent": True, "session_id": session_id}
        else:
            raise ValueError(f"Unknown action: {action}")

    if not cwd:
        raise ValueError("cwd is required for command execution")

    if detach:
        if alive_timeout is None:
            alive_timeout = config.SESSION_DEFAULT_ALIVE_TIMEOUT
        validate_command(command)
        command = wrap_command(command, shell)
        return await session_manager.create(command, cwd, env, alive_timeout, executor)

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
    command: str = "",
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    output_file: str = "",
    detach: bool = False,
    session_id: str = None,
    action: str = "send",
    alive_timeout: int = None,
) -> dict | list[dict]:
    """在隔离容器中执行命令（Docker/OpenSandbox），独立黑白名单。

    无 cwd/shell 参数。其余参数和返回格式同上 execute_local。

    示例:
        execute_sandbox("pip install numpy && python -c 'import numpy; print(numpy.__version__)'", timeout=120)
        execute_sandbox("node -e 'console.log(process.env)'", env={"DEBUG": "1"})
        execute_sandbox("python -c 'print(input())'", detach=True)
        execute_sandbox(session_id="xxx", action="read")
        execute_sandbox(session_id="xxx", action="kill")
    """
    global _opensandbox_server_started

    timeout = resolve_timeout(timeout)

    if session_id:
        if config.SANDBOX_BACKEND == "opensandbox":
            return await _opensandbox_session_dispatch(session_id, action, command, timeout)
        if action == "read":
            return session_manager.read(session_id)
        elif action == "kill":
            return session_manager.kill(session_id)
        elif action == "send":
            session_manager.send(session_id, command)
            return {"sent": True, "session_id": session_id}
        else:
            raise ValueError(f"Unknown action: {action}")

    if detach:
        if alive_timeout is None:
            alive_timeout = config.SESSION_DEFAULT_ALIVE_TIMEOUT
        if config.SANDBOX_BACKEND == "opensandbox":
            return await _opensandbox_session_create(command, env, alive_timeout)
        if config.SANDBOX_BACKEND == "docker":
            validate_sandbox_command(command)
            return await session_manager.create(command, None, env, alive_timeout, sandbox)
        else:
            return await session_manager.create(command, None, env, alive_timeout, opensandbox)

    if config.SANDBOX_BACKEND == "opensandbox":
        _ensure_opensandbox_server()

    try:
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
    finally:
        if config.SANDBOX_BACKEND == "opensandbox":
            _opensandbox_last_used = time.time()


@mcp.tool()
async def execute_sandbox_file(
    action: str,
    path: str,
    session_id: str = None,
    content: str = "",
) -> dict:
    """OpenSandbox 沙箱文件操作（仅 opensandbox 后端）。

    action: "read" | "write" | "list" | "delete" | "exists"
    path: 沙箱内绝对路径，如 /home/user/result.txt
    session_id: 复用已有 session 的 sandbox（可选，无则创建临时 sandbox）
    content: action="write" 时写入的内容

    返回: {success: True, data: ...} 或 {success: False, error: "..."}

    示例:
        execute_sandbox_file("read", "/home/user/output.txt")
        execute_sandbox_file("write", "/home/user/script.py", content="print(1)")
        execute_sandbox_file("list", "/home/user")
        execute_sandbox_file("exists", "/home/user/output.txt", session_id="xxx")
    """
    if config.SANDBOX_BACKEND != "opensandbox":
        return {"success": False, "error": "execute_sandbox_file 仅支持 opensandbox 后端"}

    if not path.startswith("/"):
        return {"success": False, "error": "path must be absolute"}

    _ensure_opensandbox_server()

    sandbox = None
    if session_id:
        await _reset_watchdog(session_id)
        async with _opensandbox_sessions_lock:
            session = _opensandbox_sessions.get(session_id)
            if session is None:
                return {"success": False, "error": f"session {session_id} not found or expired"}
            sandbox = session["sandbox"]
    else:
        try:
            sandbox = await Sandbox.create(
                config.SANDBOX_OPEN_TEMPLATE,
                connection_config=opensandbox.conn,
                timeout=timedelta(seconds=30),
                entrypoint=getattr(config, "SANDBOX_OPEN_ENTRYPOINT", None),
            )
        except Exception as e:
            return {"success": False, "error": f"failed to create sandbox: {e}"}

    try:
        _opensandbox_last_used = time.time()
        if action == "read":
            data = await sandbox.files.read_file(path)
            return {"success": True, "data": data}
        elif action == "write":
            await sandbox.files.write_file(path, content)
            return {"success": True, "data": None}
        elif action == "list":
            from opensandbox.models import DirectoryListEntry
            entries = await sandbox.files.list_directory(DirectoryListEntry(path=path))
            return {"success": True, "data": [e.model_dump() for e in entries]}
        elif action == "delete":
            await sandbox.files.delete_files([path])
            return {"success": True, "data": None}
        elif action == "exists":
            try:
                await sandbox.files.get_file_info([path])
                return {"success": True, "data": True}
            except Exception:
                return {"success": True, "data": False}
        else:
            return {"success": False, "error": f"unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if not session_id and sandbox is not None:
            try:
                await sandbox.destroy()
            except Exception:
                pass


@mcp.tool()
async def execute_remote(
    command: str = "",
    timeout: int = None,
    env: dict = None,
    parallel: bool = False,
    fields: dict = None,
    output_file: str = "",
    detach: bool = False,
    session_id: str = None,
    action: str = "send",
    alive_timeout: int = None,
) -> dict | list[dict]:
    """在远程服务器执行命令（SSH），黑白名单同 execute_local。

    无 cwd/shell 参数。其余参数和返回格式同上 execute_local。

    示例:
        execute_remote("docker ps --format '{{.Names}}'", timeout=10)
        execute_remote("systemctl status nginx")
        execute_remote("df -h && free -m", parallel=True)
        execute_remote("python -c 'print(input())'", detach=True)
        execute_remote(session_id="xxx", action="read")
        execute_remote(session_id="xxx", action="kill")
    """
    global _remote_executor

    if session_id:
        if action == "read":
            return session_manager.read(session_id)
        elif action == "kill":
            return session_manager.kill(session_id)
        elif action == "send":
            session_manager.send(session_id, command)
            return {"sent": True, "session_id": session_id}
        else:
            raise ValueError(f"Unknown action: {action}")

    if detach:
        if alive_timeout is None:
            alive_timeout = config.SESSION_DEFAULT_ALIVE_TIMEOUT
        validate_command(command)
        return await session_manager.create(command, None, env, alive_timeout, _remote_executor)

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