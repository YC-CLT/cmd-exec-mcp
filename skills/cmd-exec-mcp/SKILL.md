---
name: cmd-exec-mcp
description: Use when the agent needs to execute shell commands. 
---

# cmd-exec-mcp

## Overview

通过 `run_mcp` 调用 cmd-exec-mcp 服务器执行 shell 命令。支持本机、沙箱、SSH 远端三种执行环境。返回 `{"stdout": str, "stderr": str, "exit_code": int, "duration": float, "is_timeout": bool, "command_echo": str, "output_file": str|None}`。

## When to Use

- 需要在本地 / 沙箱 / SSH 远端执行任意 shell 命令
- 需要并行执行多条独立命令
- 需要后台常驻会话（REPL 交互）

**When NOT to use：**
- 文件查找/列表/搜索：用 `Glob`/`Grep`/`LS`/`SearchCodebase`，比 shell 更快
- 简单文件读写：用 `Read`/`Write` 工具
- 需要 GUI 的命令：MCP 无图形界面

## 执行器选择

| 场景 | 执行器 | 会话管理 |
|------|--------|----------|
| 本机一次性命令 | `execute_local` | — |
| 本机后台进程 | `execute_local` + `detach=True` | 返回 `session_id`，后续用 `execute_session` |
| 沙箱隔离执行 | `execute_sandbox` | — |
| 沙箱后台进程 | `execute_sandbox` + `detach=True` | 同上 |
| SSH 远端执行 | `execute_remote` | — |
| SSH 文件传输 | `execute_remote_file` | `upload` / `download` |
| 沙箱文件传输 | `execute_sandbox_file` | `upload` / `download`（后端可能不支持，失败回退到 `execute_sandbox`） |
| 会话操作（读/写/关/查） | `execute_session` | **统一入口**，跨本地/远程/沙箱三种 backend |

## Quick Reference

| 工具 | 场景 | 必填 | 重要可选 |
|---|---|---|---|
| `execute_local` | 本机执行 | `command`, `cwd` | `timeout`, `shell`, `detach` |
| `execute_sandbox` | 沙箱隔离执行 | `command` | `timeout`, `detach` |
| `execute_remote` | SSH 远端 | `command` | `target`, `cwd`, `timeout` |
| `execute_remote_file` | SSH 文件传输 | `action`, `path`, `local_path` | `target` |
| `execute_session` | 跨后端统一会话管理 | `action` (`read`/`send`/`kill`/`status`/`list`), `session_id` | `command`, `timeout`, `alive_timeout` |
| `execute_sandbox_file` | 沙箱文件传输 | `action`, `path`, `local_path` | `session_id` |

## 参数

| 参数  | 默认值 | 说明 |
|---|---|---|
| `command` | — | 用 `&&` 串联多条命令 |
| `cwd` | — | 工作目录，local 必填，remote 可选，sandbox 不支持 |
| `timeout` | 30 | 秒，`-1` 无限；慢命令可延长。execute / execute_session 通用 |
| `env` | `None` | `{"KEY": "val"}` |
| `shell` | 自动 | `"cmd"` / `"pwsh"` / `"bash"` / `"wsl"`（仅 local，Win→cmd, 其他→bash） |
| `parallel` | `False` | `&&` + `True` → 并行执行，返回 `list[dict]` |
| `fields` | 全部 | 过滤返回字段，如 `{"stdout": True, "exit_code": True}` |
| `output_file` | — | 绝对路径，超出 8k 截断存到磁盘（文件名 basename 会被清理） |
| `detach` | `False` | 后台会话，返回 `session_id` |
| `target` | — | SSH 目标，格式 `[user@]host[:port]` 或 `[user@][ipv6][:port]`，否则回退默认 |
| `alive_timeout` | 300 | 空闲超时秒数，`-1` 永不超时。**仅 `detach=True` 时生效** |

## 示例

```python
# 基本形式
run_mcp("cmd-exec-mcp", "execute_local", {"command": "git status", "cwd": "D:/project"})
```

变体：

```python
# 长超时：+ timeout
{"command": "npm install", "cwd": "D:/project", "timeout": 120}

# 并行：+ parallel
{"command": "go build && go test", "cwd": "D:/project", "parallel": True}

# 指定 Shell：+ shell
{"command": "ls -la", "cwd": "D:/project", "shell": "bash"}

# 环境变量：+ env
{"command": "node -e \"console.log(process.env.FOO)\"", "cwd": "D:/project", "env": {"FOO": "bar"}}

# 字段过滤：+ fields
{"command": "git status", "cwd": "D:/project", "fields": {"stdout": True, "exit_code": True}}

# 输出落盘：+ output_file
{"command": "dir /s", "cwd": "D:/project", "output_file": "D:/project/filelist.txt"}

# 沙箱：execute_sandbox，无 cwd
{"command": "pip install numpy", "timeout": 120}

# 远端：execute_remote，支持 target 和 cwd
{"command": "docker ps", "timeout": 10}
{"command": "ls -la", "target": "pi@rpig:8022"}
{"command": "cat file.txt", "cwd": "/home/user"}

# 远端文件传输：execute_remote_file
{"action": "upload", "path": "/tmp/out.txt", "local_path": "D:/project/out.txt"}
{"action": "download", "path": "/var/log/syslog", "local_path": "D:/logs/syslog"}
{"action": "upload", "path": "/tmp/out.txt", "local_path": "D:/project/out.txt", "target": "pi@rpig:8022"}

# 沙箱文件传输：execute_sandbox_file（后端可能不支持，失败回退 execute_sandbox）
{"action": "upload", "path": "/tmp/out.txt", "local_path": "D:/project/out.txt"}
{"action": "download", "path": "/var/log/syslog", "local_path": "D:/logs/syslog"}
{"action": "upload", "path": "/tmp/out.txt", "local_path": "D:/project/out.txt", "session_id": "uuid"}

# 会话分离：+ detach → 拿 session_id 后续用 execute_session 操作
# 本机
{"command": "python repl.py", "cwd": "D:/project", "detach": True}
# 沙箱
{"command": "python", "detach": True}
# → {"session_id": "uuid", ...}
{"action": "read", "session_id": "uuid"}
{"action": "read", "session_id": "uuid", "timeout": 60}
{"action": "send", "session_id": "uuid", "command": "print(1+1)"}
{"action": "send", "session_id": "uuid", "command": "print(1+1)", "timeout": 30}
{"action": "kill", "session_id": "uuid"}
{"action": "status", "session_id": "uuid"}
{"action": "list"}
```

## 常见错误

| 错误 | 原因 | 正确 |
|---|---|---|
| 试图用原生终端打开 MCP | 误以为 MCP 是独立 CLI 工具 | 服务器已运行，始终用 `run_mcp` 调用 |
| 忘了 `cwd` | `execute_local` 是唯一需要工作目录的 | `execute_local` 必须带 `cwd` |
| 慢命令不设超时 | 默认 30s 超时，`npm install` 等必然超时 | 适当延长 `timeout`，如 `120` |
| sandbox 带 `cwd` | sandbox 无 `cwd` 参数 | sandbox 去掉 `cwd` |
| sandbox 带 `shell` | sandbox 无 `shell` 参数 | sandbox 去掉 `shell` |
| 独立命令分三次调 | 串行等待浪费时间 | `&&` 串联 + `parallel: true` 一次搞定 |
| 输出被截断 | 返回结果超 8k 自动截断 | 加 `output_file` 参数存磁盘 |
| `execute_sandbox_file` 报错 | 后端不支持文件传输 | 改用 `execute_sandbox` 内联命令完成 |
| `execute_session` 忘传 `session_id` | 除 `list` 外所有 action 都需要 | `"send"`/`"read"`/`"kill"`/`"status"` 必须带 `session_id` |
| session 超时断开 | 默认 300s 空闲超时 | 延长 `alive_timeout` 或设为 `-1` |
| 用 `execute_local` 传 `session_id`/`action` | 会话管理已统一到 `execute_session` | 改用 `execute_session`，`execute_local` 只接受 `detach=True` 创建会话 |
| IPv6 地址解析失败 | 未用 `[]` 包裹 | 用 `[::1]` 或 `[::1]:8022` 格式 |
| `execute_sandbox_file` 不传 `session_id` 后忘了销毁 | 自动创建临时 sandbox，操作完自动销毁 | 无需手动管理，`finally` 自动清理 |