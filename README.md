# cmd-exec-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Server-orange.svg)](https://modelcontextprotocol.io/)
[![GitHub](https://img.shields.io/badge/github-YC--CLT%2Fcmd--exec--mcp-blue?logo=github)](https://github.com/YC-CLT/cmd-exec-mcp)

[English](#english) | [中文](#中文)

## English

A simple command execution MCP server supporting local execution, Docker/OpenSandbox sandbox isolation, and SSH remote execution.

### Features

- **Local** (`execute_local`): Execute commands on the host machine, `cwd` required
- **Sandbox** (`execute_sandbox`): Isolated execution in Docker containers or OpenSandbox, ephemeral
- **Remote** (`execute_remote`): Execute commands via SSH on remote servers, supports standard/custom dual-mode config

- Security mode: restricted (whitelist + blacklist) / full mode
- Sequential / parallel execution
- Timeout control
- Session detach: background long-running processes with read/send/kill
- Agent Skill: `skills/cmd-exec-mcp/SKILL.md` — quick reference for AI agents
- Logging

### Installation

```bash
git clone https://github.com/YC-CLT/cmd-exec-mcp.git
cd cmd-exec-mcp
uv sync
```

### MCP Client Configuration

```json
{
  "mcpServers": {
    "cmd-exec-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\your_path\\cmd-exec-mcp", "main.py"]
    }
  }
}
```

### Configuration

Edit `config.py`:

| Config | Default | Description |
|---|---|---|
| `SECURITY_MODE` | `"restricted"` | Security mode: `"restricted"` \| `"full"` |
| `COMMAND_LIST_MODE` | `"blacklist"` | List mode: `"whitelist"` \| `"blacklist"` |
| `COMMAND_WHITELIST` | `["ls","dir","git",...]` | Whitelist commands |
| `COMMAND_BLACKLIST` | `["rm","del","shutdown",...]` | Blacklist commands |
| `FORCE_SHELL` | `None` | Force shell: `"pwsh"`\|`"cmd"`\|`"bash"`\|`"wsl"` |
| `WSL_DISTRO` | `"kali-linux"` | WSL distro name (when `shell="wsl"`) |
| `WSL_USER` | `"kali"` | WSL username (when `shell="wsl"`) |
| `SANDBOX_BACKEND` | `"opensandbox"` | Sandbox backend: `"docker"` \| `"opensandbox"` |
| `SANDBOX_SECURITY_MODE` | `"full"` | Docker sandbox security mode |
| `SANDBOX_COMMAND_LIST_MODE` | `"blacklist"` | Docker sandbox list mode |
| `SANDBOX_COMMAND_BLACKLIST` | `["docker","mount","fdisk"]` | Docker sandbox blacklist |
| `SANDBOX_COMMAND_WHITELIST` | `[]` | Docker sandbox whitelist |
| `SANDBOX_DEFAULT_IMAGE` | `"opensandbox/code-interpreter:v1.1.0"` | Docker sandbox default image |
| `SANDBOX_DEFAULT_MOUNT` | `None` | Mount directory (`"host:container"`) |
| `SANDBOX_DOCKER_PREFIX` | `"export PIP_INDEX_URL=..."` | Docker sandbox startup prefix (mirrors, etc.) |
| `SANDBOX_OPEN_TEMPLATE` | `"opensandbox/code-interpreter:v1.1.0"` | OpenSandbox template image |
| `SANDBOX_OPEN_ENTRYPOINT` | `["/opt/code-interpreter/code-interpreter.sh"]` | OpenSandbox entrypoint script |
| `SANDBOX_OPEN_RUNTIME_ENV` | `{"PYTHON_VERSION":"3.11",...}` | OpenSandbox runtime versions + mirrors |
| `SANDBOX_OPEN_SERVER_HOST` | `"localhost"` | OpenSandbox Server host |
| `SANDBOX_OPEN_SERVER_PORT` | `8080` | OpenSandbox Server port |
| `SANDBOX_OPEN_API_KEY` | `"cmd-exec-mcp-dev"` | OpenSandbox API Key (required for production) |
| `SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT` | `15` | Max seconds to wait for server ready |
| `SANDBOX_OPEN_SERVER_IDLE_TIMEOUT` | `600` | Idle seconds before auto-shutdown, -1 never |
| `DEFAULT_TIMEOUT` | `30` | Timeout in seconds (-1 for unlimited) |
| `OUTPUT_TRUNCATE_LENGTH` | `8000` | stdout truncation length when using `output_file` |
| `SESSION_DEFAULT_ALIVE_TIMEOUT` | `300` | Session alive timeout in seconds, -1 for unlimited |
| `SESSION_MAX_OUTPUT_LINES` | `10000` | Max lines buffered per session |
| `SESSION_MAX_OUTPUT_BYTES` | `10485760` | Max bytes buffered per session (10 MB) |
| `RESULT_FIELDS` | `{"stdout":True,...}` | Return field toggles |
| `SSH_CONFIG_MODE` | `"standard"` | SSH config mode: `"standard"` \| `"custom"` |
| `SSH_HOST_NAME` | — | SSH Host alias for standard mode |
| `SSH_PERSISTENT` | `True` | Persistent SSH connection |
| `SSH_CONNECTION_TIMEOUT` | `10` | SSH connection timeout in seconds |
| `LOG_FILE` | `"log.txt"` | Log file path |
| `LOG_LEVEL` | `"INFO"` | Log level |

#### OpenSandbox Prerequisites

To use the OpenSandbox backend (`SANDBOX_BACKEND = "opensandbox"`):

1. Prerequisite: Docker Desktop installed and running
2. Install the server (global):

   ```bash
   uv tool install opensandbox-server
   ```

3. Deploy config:

   ```bash
   copy .sandbox.toml %USERPROFILE%\.sandbox.toml
   ```

4. Switch backend: `config.py` → `SANDBOX_BACKEND = "opensandbox"`
5. API Key: can be arbitrary for local dev, but don't leave it empty or it will block for manual confirmation; set `SANDBOX_OPEN_API_KEY` in production

> `opensandbox-server` is started automatically on first `execute_sandbox` call and auto-shuts down after `SANDBOX_OPEN_SERVER_IDLE_TIMEOUT` seconds of inactivity (default 600).

#### SSH Remote Execution Prerequisites

1. Standard mode: configure `~/.ssh/config` and set `SSH_HOST_NAME` to the Host alias
2. Custom mode: create `.env` in the project root, referencing `.env.example`:

   ```env
   SSH_HOST=192.168.1.100
   SSH_PORT=22
   SSH_USER=root
   SSH_KEY_PATH=~/.ssh/id_rsa
   SSH_PASSWORD=
   SSH_KNOWN_HOSTS=true
   ```

### Tools

#### execute_local

Execute a command on the host machine.

```json
{
  "command": "echo hello",
  "parallel": false,
  "timeout": 30,
  "cwd": "/tmp",
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| Param | Type | Default | Description |
|---|---|---|---|
| `command` | str | required | Command, use `&&` for parallel mode |
| `cwd` | str | required | Working directory |
| `parallel` | bool | false | Run commands in parallel |
| `timeout` | int | 30 | Timeout in seconds, -1 for unlimited |
| `env` | dict | null | Environment variables |
| `fields` | dict | null | Return field filter |
| `shell` | str | null | Override shell: `"pwsh"`\|`"cmd"`\|`"bash"`\|`"wsl"` |
| `output_file` | str | "" | Write full stdout to disk, return truncated preview |
| `detach` | bool | false | Run as background session |
| `session_id` | str | null | Session ID for read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | Session alive timeout in seconds |

#### execute_sandbox

Execute a command in a sandbox (Docker/OpenSandbox, determined by `SANDBOX_BACKEND`).

```json
{
  "command": "echo hello",
  "parallel": false,
  "timeout": 30,
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| Param | Type | Default | Description |
|---|---|---|---|
| `command` | str | required | Command |
| `parallel` | bool | false | Run in parallel |
| `timeout` | int | 30 | Timeout in seconds |
| `env` | dict | null | Environment variables |
| `fields` | dict | null | Return field filter |
| `output_file` | str | "" | Write full stdout to disk, return truncated preview |
| `detach` | bool | false | Run as background session |
| `session_id` | str | null | Session ID for read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | Session alive timeout in seconds |

#### execute_remote

Execute a command on a remote server via SSH. See SSH prerequisites above.

```json
{
  "command": "ls -la",
  "parallel": false,
  "timeout": 30,
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| Param | Type | Default | Description |
|---|---|---|---|
| `command` | str | required | Command |
| `parallel` | bool | false | Run in parallel |
| `timeout` | int | 30 | Timeout in seconds |
| `env` | dict | null | Environment variables |
| `fields` | dict | null | Return field filter |
| `output_file` | str | "" | Write full stdout to disk, return truncated preview |
| `detach` | bool | false | Run as background session |
| `session_id` | str | null | Session ID for read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | Session alive timeout in seconds |

### Session Detach

Run long-lived background processes (e.g., dev servers, REPLs) as sessions:

```json
// Start a background session
{
  "command": "python -m http.server 8080",
  "cwd": "/tmp",
  "detach": true
}
// Returns: {"session_id": "abc123"}

// Read output
{
  "session_id": "abc123",
  "action": "read"
}

// Send input
{
  "session_id": "abc123",
  "action": "send",
  "command": "some input\n"
}

// Kill session
{
  "session_id": "abc123",
  "action": "kill"
}
```

Sessions auto-terminate after `alive_timeout` seconds of inactivity (default 300, -1 for unlimited). Output is buffered up to `SESSION_MAX_OUTPUT_BYTES`.

### Testing

```bash
uv run pytest tests/ -v
```

### Non-Interactive Execution

For non-session commands, `stdin` is set to `/dev/null` — interactive commands will fail or timeout. Use **session detach** (see above) for interactive workflows (REPLs, shells, etc.). For one-shot commands, add flags to skip prompts:

| Command | Flag | Notes |
|---|---|---|
| `apt install` | `-y` | Auto-confirm |
| `apt remove` | `-y` | Use with caution |
| `sudo` | `-n` | Non-interactive, fail if password needed |
| `pip install` | — | Non-interactive by default |
| `rm` | — | Blacklisted by default |

### Logging

Logs are written to `log.txt` in the project root, format:

```bash
2026-07-30 12:00:00 [INFO] local: execute: echo hello
2026-07-30 12:00:00 [INFO] local: exit_code=0 duration=0.012
```

### License

MIT

---

## 中文

一个简单的命令执行 MCP，支持本地执行、纯 Docker/OpenSandbox 沙箱隔离执行和 SSH 远程执行。

### 功能

- **本地执行** (`execute_local`): 在宿主机执行命令，cwd 必填
- **沙箱执行** (`execute_sandbox`): 在 Docker 容器或 OpenSandbox 沙箱中隔离执行，用完即焚
- **远程执行** (`execute_remote`): 通过 SSH 在远程服务器执行命令，支持 standard/custom 双模式配置

- 安全模式: 受限模式（白名单+黑名单）/ 完全模式
- 单步/并行执行
- 超时控制
- 会话分离：后台长时进程，支持 read/send/kill
- Agent Skill：`skills/cmd-exec-mcp/SKILL.md` — AI Agent 快速参考指南
- 日志记录

### 安装

```bash
git clone https://github.com/YC-CLT/cmd-exec-mcp.git
cd cmd-exec-mcp
uv sync
```

### MCP 客户端配置

```json
{
  "mcpServers": {
    "cmd-exec-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\your_path\\cmd-exec-mcp", "main.py"]
    }
  }
}
```

### 配置

编辑 `config.py`:

| 配置 | 默认值 | 说明 |
|---|---|---|
| `SECURITY_MODE` | `"restricted"` | 安全模式 |
| `COMMAND_LIST_MODE` | `"blacklist"` | 列表模式: `"whitelist"` \| `"blacklist"` |
| `COMMAND_WHITELIST` | `["ls","dir","git",...]` | 白名单 |
| `COMMAND_BLACKLIST` | `["rm","del","shutdown",...]` | 黑名单 |
| `FORCE_SHELL` | `None` | 强制指定 Shell: `"pwsh"`\|`"cmd"`\|`"bash"`\|`"wsl"` |
| `WSL_DISTRO` | `"kali-linux"` | WSL 发行版名（`shell="wsl"` 时生效） |
| `WSL_USER` | `"kali"` | WSL 用户名（`shell="wsl"` 时生效） |
| `SANDBOX_BACKEND` | `"opensandbox"` | 沙箱后端: `"docker"` \| `"opensandbox"` |
| `SANDBOX_SECURITY_MODE` | `"full"` | 纯docker沙箱安全模式 |
| `SANDBOX_COMMAND_LIST_MODE` | `"blacklist"` | 纯docker沙箱列表模式 |
| `SANDBOX_COMMAND_BLACKLIST` | `["docker","mount","fdisk"]` | 纯docker沙箱黑名单 |
| `SANDBOX_COMMAND_WHITELIST` | `[]` | 纯docker沙箱白名单 |
| `SANDBOX_DEFAULT_IMAGE` | `"opensandbox/code-interpreter:v1.1.0"` | 纯docker沙箱默认镜像 |
| `SANDBOX_DEFAULT_MOUNT` | `None` | 挂载目录（`"host:container"`） |
| `SANDBOX_DOCKER_PREFIX` | `"export PIP_INDEX_URL=..."` | 纯docker启动命令前缀（换源等） |
| `SANDBOX_OPEN_TEMPLATE` | `"opensandbox/code-interpreter:v1.1.0"` | OpenSandbox 模板镜像 |
| `SANDBOX_OPEN_ENTRYPOINT` | `["/opt/code-interpreter/code-interpreter.sh"]` | OpenSandbox 入口脚本 |
| `SANDBOX_OPEN_RUNTIME_ENV` | `{"PYTHON_VERSION":"3.11",...}` | OpenSandbox 运行时版本+镜像源 |
| `SANDBOX_OPEN_SERVER_HOST` | `"localhost"` | OpenSandbox Server 地址 |
| `SANDBOX_OPEN_SERVER_PORT` | `8080` | OpenSandbox Server 端口 |
| `SANDBOX_OPEN_API_KEY` | `"cmd-exec-mcp-dev"` | OpenSandbox API Key（生产必填） |
| `SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT` | `15` | 等待 Server 就绪的最长秒数 |
| `SANDBOX_OPEN_SERVER_IDLE_TIMEOUT` | `600` | 空闲超时自动关闭秒数，-1 永不关闭 |
| `DEFAULT_TIMEOUT` | `30` | 超时秒数（-1 无限制） |
| `OUTPUT_TRUNCATE_LENGTH` | `8000` | 输出落盘时 stdout 截断长度 |
| `SESSION_DEFAULT_ALIVE_TIMEOUT` | `300` | 会话默认存活超时秒数，-1 无限 |
| `SESSION_MAX_OUTPUT_LINES` | `10000` | 会话最大缓冲行数 |
| `SESSION_MAX_OUTPUT_BYTES` | `10485760` | 会话最大缓冲字节（10 MB） |
| `RESULT_FIELDS` | `{"stdout":True,...}` | 返回字段开关 |
| `SSH_CONFIG_MODE` | `"standard"` | SSH 配置模式: `"standard"` \| `"custom"` |
| `SSH_HOST_NAME` | — | standard 模式 SSH Host 别名 |
| `SSH_PERSISTENT` | `True` | SSH 长连接复用 |
| `SSH_CONNECTION_TIMEOUT` | `10` | SSH 连接超时秒数 |
| `LOG_FILE` | `"log.txt"` | 日志文件路径 |
| `LOG_LEVEL` | `"INFO"` | 日志级别 |

#### OpenSandbox 前置条件

如需使用 OpenSandbox 后端 (`SANDBOX_BACKEND = "opensandbox"`)：

1. 前置依赖：Docker Desktop 已安装运行

2. 安装 Server（全局）：

   ```bash
   uv tool install opensandbox-server
   ```

3. 部署配置：

   ```bash
   copy .sandbox.toml %USERPROFILE%\.sandbox.toml
   ```

4. 切换后端：`config.py` → `SANDBOX_BACKEND = "opensandbox"`
5. API Key：本地开发随意，但不建议留空，否则会阻塞让你手动确认；生产环境设 `SANDBOX_OPEN_API_KEY`

> 首次调用 `execute_sandbox` 时自动拉起 `opensandbox-server`，空闲 `SANDBOX_OPEN_SERVER_IDLE_TIMEOUT` 秒（默认 600）后自动关闭。

#### SSH 远程执行前置条件

1. standard 模式：已配置 `~/.ssh/config`，设置 `SSH_HOST_NAME` 为 Host 别名
2. custom 模式：项目根目录创建 `.env`，参考 `.env.example`:

   ```env
   SSH_HOST=192.168.1.100
   SSH_PORT=22
   SSH_USER=root
   SSH_KEY_PATH=~/.ssh/id_rsa
   SSH_PASSWORD=
   SSH_KNOWN_HOSTS=true
   ```

### 工具

#### execute_local

在宿主机执行命令。

```json
{
  "command": "echo hello",
  "parallel": false,
  "timeout": 30,
  "cwd": "/tmp",
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | str | 必填 | 命令，并行模式用 `&&` 分隔 |
| `cwd` | str | 必填 | 工作目录 |
| `parallel` | bool | false | 是否并行执行 |
| `timeout` | int | 30 | 超时秒数，-1 无限制 |
| `env` | dict | null | 环境变量 |
| `fields` | dict | null | 返回字段过滤 |
| `shell` | str | null | 指定 Shell: `"pwsh"`\|`"cmd"`\|`"bash"`\|`"wsl"` |
| `output_file` | str | "" | 输出过长时落盘，返回截断预览 |
| `detach` | bool | false | 后台会话模式 |
| `session_id` | str | null | 会话 ID，用于 read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | 会话存活超时秒数 |

#### execute_sandbox

在沙箱中执行命令（Docker/OpenSandbox，由 `SANDBOX_BACKEND` 决定）。

```json
{
  "command": "echo hello",
  "parallel": false,
  "timeout": 30,
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | str | 必填 | 命令 |
| `parallel` | bool | false | 是否并行 |
| `timeout` | int | 30 | 超时秒数 |
| `env` | dict | null | 环境变量 |
| `fields` | dict | null | 返回字段过滤 |
| `output_file` | str | "" | 输出过长时落盘，返回截断预览 |
| `detach` | bool | false | 后台会话模式 |
| `session_id` | str | null | 会话 ID，用于 read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | 会话存活超时秒数 |

#### execute_remote

通过 SSH 在远程服务器执行命令，配置见 SSH 前置条件。

```json
{
  "command": "ls -la",
  "parallel": false,
  "timeout": 30,
  "env": { "KEY": "value" },
  "fields": { "stdout": true, "stderr": false }
}
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | str | 必填 | 命令 |
| `parallel` | bool | false | 是否并行 |
| `timeout` | int | 30 | 超时秒数 |
| `env` | dict | null | 环境变量 |
| `fields` | dict | null | 返回字段过滤 |
| `output_file` | str | "" | 输出过长时落盘，返回截断预览 |
| `detach` | bool | false | 后台会话模式 |
| `session_id` | str | null | 会话 ID，用于 read/send/kill |
| `action` | str | "send" | `"read"`\|`"send"`\|`"kill"` |
| `alive_timeout` | int | 300 | 会话存活超时秒数 |

### 会话分离

运行后台长时进程（如开发服务器、REPL）作为会话:

```json
// 启动后台会话
{
  "command": "python -m http.server 8080",
  "cwd": "/tmp",
  "detach": true
}
// 返回: {"session_id": "abc123"}

// 读取输出
{
  "session_id": "abc123",
  "action": "read"
}

// 发送输入
{
  "session_id": "abc123",
  "action": "send",
  "command": "一些输入\n"
}

// 关闭会话
{
  "session_id": "abc123",
  "action": "kill"
}
```

会话在 `alive_timeout` 秒无活动后自动终止（默认 300，-1 无限）。输出缓冲上限为 `SESSION_MAX_OUTPUT_BYTES`。

### 测试

```bash
uv run pytest tests/ -v
```

### 非交互执行

非会话模式下 `stdin` 设为 `/dev/null`，交互式命令会失败或超时。需要交互式工作流（REPL、Shell 等）用**会话分离**（见上）。一次性命令请添加对应 flag 跳过提示：

| 命令 | 参数 | 说明 |
|---|---|---|
| `apt install` | `-y` | 自动确认 |
| `apt remove` | `-y` | 谨慎使用 |
| `sudo` | `-n` | 非交互模式，需要密码则失败 |
| `pip install` | — | 默认非交互 |
| `rm` | — | 默认黑名单拦截 |

### 日志

日志写入项目根目录 `log.txt`，格式:

```bash
2026-07-30 12:00:00 [INFO] local: execute: echo hello
2026-07-30 12:00:00 [INFO] local: exit_code=0 duration=0.012
```

### 协议

MIT