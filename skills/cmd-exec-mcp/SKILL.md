---
name: cmd-exec-mcp
description: Use when you need to execute shell commands locally, in a sandbox, or on a remote host via the cmd-exec-mcp server
---

# cmd-exec-mcp

## Overview

通过 `run_mcp` 调用 cmd-exec-mcp 服务器执行 shell 命令。支持本机、Docker 沙箱、SSH 远端三种执行环境，返回 `{"stdout", "stderr", "exit_code", "duration", "is_timeout", "command_echo", "output_file"}`。

## When to Use

- 需要在本地 / Docker 容器 / SSH 远端执行任意 shell 命令
- 需要并行执行多条独立命令
- 需要后台常驻会话（REPL 交互）
- 输出可能超过 8k 需要落盘

不要用原生终端直接调 MCP 服务端

| 工具 | 场景 | 必填 |
|---|---|---|
| `execute_local` | 本机执行 | `command`, `cwd` |
| `execute_sandbox` | Docker/OpenSandbox 容器 | `command` |
| `execute_remote` | SSH 远端 | `command` |

## 参数

| 参数  | 默认值 | 说明 |
|---|---|---|
| `command` | — | 用 `&&` 串联多条命令 |
| `cwd` | — | 工作目录，sandbox/remote 无此参数 |
| `timeout` | 30 | 秒，`-1` 无限；慢命令可延长 |
| `env` | `None` | `{"KEY": "val"}` |
| `shell` | 自动 | `"cmd"` / `"pwsh"` / `"bash"` / `"wsl"`（仅 local，Win→cmd, 其他→bash） |
| `parallel` | `False` | `&&` + `True` → 并行执行，返回 `list[dict]` |
| `fields` | 全部 | 过滤返回字段，如 `{"stdout": True, "exit_code": True}` |
| `output_file` | — | 绝对路径，超出 8k 截断存到磁盘（文件名 basename 消毒） |
| `detach` | `False` | 后台会话，返回 `session_id` |
| `session_id` | — | 配合 `action` 操作已有会话 |
| `action` | | `"send"` | `"send"` / `"read"` / `"kill"` |
| `alive_timeout` | | 300 | 空闲超时秒数，`-1` 永不超时 |

## 示例

```python
# 基本形式
run_mcp("cmd-exec-mcp", "execute_local", {"command": "git status", "cwd": "D:/project"})
```

变体（只列出差异参数）：

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
run_mcp("cmd-exec-mcp", "execute_sandbox", {"command": "pip install numpy", "timeout": 120})

# 远端：execute_remote，无 cwd
run_mcp("cmd-exec-mcp", "execute_remote", {"command": "docker ps", "timeout": 10})

# 会话分离：+ detach → 拿 session_id 后续操作
run_mcp("cmd-exec-mcp", "execute_local", {"command": "python repl.py", "cwd": "D:/project", "detach": True})
# → {"session_id": "uuid", ...}
run_mcp("cmd-exec-mcp", "execute_local", {"session_id": "uuid", "action": "read"})
run_mcp("cmd-exec-mcp", "execute_local", {"session_id": "uuid", "command": "print(1+1)", "action": "send"})
run_mcp("cmd-exec-mcp", "execute_local", {"session_id": "uuid", "action": "kill"})
```

## 常见错误

| 错误 | 原因 | 正确 |
|---|---|---|
| 试图用原生终端打开 MCP | 误以为 MCP 是独立 CLI 工具 | 服务器已运行，始终用 `run_mcp` 调用 |
| 忘了 `cwd` | `execute_local` 是唯一需要工作目录的 | `execute_local` 必须带 `cwd` |
| 慢命令不设超时 | 默认 30s 超时，`npm install` 等必然超时 | 适当延长 `timeout`，如 `120` |
| sandbox/remote 带 `cwd` | 容器/远端有自己的工作目录概念 | sandbox/remote 无 `cwd` 参数，去掉即可 |
| 独立命令分三次调 | 串行等待浪费时间 | `&&` 串联 + `parallel: true` 一次搞定 |
| 输出被截断 | 返回结果超 8k 自动截断 | 加 `output_file` 参数存磁盘 |