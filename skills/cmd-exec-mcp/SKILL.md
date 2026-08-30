---
name: cmd-exec-mcp
description: Use when you need to execute shell commands locally, in a sandbox, or on a remote SSH host. 
---

# cmd-exec-mcp

## Overview

通过 `run_mcp` 调用，支持本机/沙箱/SSH 远端。返回 `{stdout, stderr, exit_code, ...}`。

## When to Use

- 本地 / 沙箱 / SSH 远端执行 shell 命令
- 并行执行多条独立命令
- 后台常驻会话（REPL 交互）

**When NOT to use:**
- 文件查找/列表/搜索：用 `Glob`/`Grep`/`LS`/`SearchCodebase`
- 简单文件读写：用 `Read`/`Write`
- 需要 GUI：MCP 无图形界面

## Quick Reference

| 工具 | 场景 | 必填 | 重要可选 | 会话 |
|---|---|---|---|---|
| `execute_local` | 本机 | `command`, `cwd` | `timeout`, `shell`, `detach` | `detach=True` → `execute_session` |
| `execute_sandbox` | 沙箱 | `command` | `timeout`, `detach` | 同上 |
| `execute_remote` | SSH | `command` | `target`, `cwd`, `timeout`, `key`, `no_known_hosts` | — |
| `execute_remote_file` | SSH 传文件 | `action`, `path`, `local_path` | `target`, `key`, `no_known_hosts` | `upload`/`download` |
| `execute_sandbox_file` | 沙箱传文件 | `action`, `path`, `local_path` | `session_id` | `upload`/`download` |
| `execute_session` | 会话管理 | `action`, `session_id` | `command`, `timeout`, `alive_timeout` | `read`/`send`/`kill`/`status`/`list` |

## 参数

| 参数  | 默认值 | 说明 |
|---|---|---|
| `command` | — | 用 `&&` 串联多条命令 |
| `cwd` | — | local 必填，remote 可选，sandbox 不支持 |
| `timeout` | 30 | 秒，`-1` 无限；慢命令适当延长 |
| `env` | `None` | `{"KEY": "val"}` |
| `shell` | 自动 | 仅 local：`cmd`/`pwsh`/`bash`/`wsl`（Win→cmd, 其他→bash） |
| `parallel` | `False` | `True` 时 `&&` 串联的命令并行执行，返回 `list[dict]` |
| `fields` | 全部 | 过滤返回字段，如 `{"stdout": True, "exit_code": True}` |
| `output_file` | — | 绝对路径，超 8k 截断存盘 |
| `detach` | `False` | 后台会话，返回 `session_id` |
| `target` | — | SSH 目标：`[user@]host[:port]`，IPv6 用 `[::1]:8022` |
| `key` | — | SSH 密钥路径或密码 |
| `no_known_hosts` | `False` | `True` 跳过 known_hosts 校验 |
| `alive_timeout` | 300 | 空闲超时秒，`-1` 永不超时（仅 `detach=True` 生效） |
| `action` | — | `read`/`send`/`kill`/`status`/`list`/`upload`/`download` |
| `path` | — | 远程/沙箱内绝对路径 |
| `local_path` | — | 本地绝对路径 |
| `session_id` | — | 复用已有 session |

## 示例

```python
# 基本形式
run_mcp("cmd-exec-mcp", "execute_local", {"command": "git status", "cwd": "D:/project"})

# 长超时
{"command": "npm install", "cwd": "D:/project", "timeout": 120}
# 并行
{"command": "go build && go test", "cwd": "D:/project", "parallel": True}
# 指定 Shell
{"command": "ls -la", "cwd": "D:/project", "shell": "bash"}
# 环境变量
{"command": "node -e \"console.log(process.env.FOO)\"", "cwd": "D:/project", "env": {"FOO": "bar"}}
# 字段过滤
{"command": "git status", "cwd": "D:/project", "fields": {"stdout": True, "exit_code": True}}
# 输出落盘
{"command": "dir /s", "cwd": "D:/project", "output_file": "D:/project/filelist.txt"}

# 沙箱（无 cwd/shell）
{"command": "pip install numpy", "timeout": 120}

# 远端（可选 target/cwd）
{"command": "docker ps", "timeout": 10}
{"command": "ls -la", "target": "pi@rpig:8022"}
{"command": "cat file.txt", "cwd": "/home/user"}

# 文件传输
{"action": "upload", "path": "/tmp/out.txt", "local_path": "D:/project/out.txt"}
{"action": "download", "path": "/var/log/syslog", "local_path": "D:/logs/syslog"}

# 会话分离：detach → 拿 session_id 用 execute_session
{"command": "python repl.py", "cwd": "D:/project", "detach": True}
# → {"session_id": "uuid", ...}
{"action": "read", "session_id": "uuid", "timeout": 60}
{"action": "send", "session_id": "uuid", "command": "print(1+1)", "timeout": 30}
{"action": "kill", "session_id": "uuid"}
{"action": "status", "session_id": "uuid"}
{"action": "list"}
```

## 执行前自检

- `execute_local`？→ 带 `cwd`
- 命令可能慢？→ 加 `timeout`
- 多条独立命令？→ `&&` + `parallel: true`
- 输出可能很长？→ 加 `output_file`
- 后台常驻？→ `detach: True`，后续用 `execute_session`

## 常见错误

| 错误 | 正确 |
|---|---|
| sandbox 带了 `cwd`/`shell` | sandbox 无这两个参数，去掉 |
| `execute_session` 忘传 `session_id` | 除 `list` 外必须带 |
| session 超时断开 | 延长 `alive_timeout` 或设 `-1` |
| 用 `execute_local` 传 `session_id`/`action` | 改用 `execute_session` |
| IPv6 解析失败 | 用 `[::1]` 或 `[::1]:8022` |