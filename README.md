# cmd-exec-mcp

一个简单的命令执行MCP，支持本地执行、纯Docker/OpenSandbox沙箱隔离执行和SSH远程执行。

## 功能

- **本地执行** (`execute_local`): 在宿主机执行命令，cwd 必填
- **沙箱执行** (`execute_sandbox`): 在 Docker 容器或 OpenSandbox 沙箱中隔离执行，用完即焚
- **远程执行** (`execute_remote`): 通过 SSH 在远程服务器执行命令，支持 standard/custom 双模式配置

- 安全模式: 受限模式（白名单+黑名单）/ 完全模式
- 单步/并行执行
- 超时控制
- 日志记录

## 安装

```bash
git clone https://github.com/<user>/cmd-exec-mcp.git
cd cmd-exec-mcp
uv sync
```

## MCP 客户端配置

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

## 配置

编辑 `config.py`:

| 配置 | 默认值 | 说明 |
|---|---|---|
| `SECURITY_MODE` | `"restricted"` | 安全模式 |
| `COMMAND_LIST_MODE` | `"blacklist"` | 列表模式: `"whitelist"` \| `"blacklist"` |
| `COMMAND_WHITELIST` | `["ls","dir","git",...]` | 白名单 |
| `COMMAND_BLACKLIST` | `["rm","del","shutdown",...]` | 黑名单 |
| `FORCE_SHELL` | `None` | 强制指定 Shell: `"pwsh"`\|`"cmd"`\|`"bash"` |
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
| `DEFAULT_TIMEOUT` | `30` | 超时秒数（-1 无限制） |
| `OUTPUT_TRUNCATE_LENGTH` | `2000` | 输出落盘时 stdout 截断长度 |
| `RESULT_FIELDS` | `{"stdout":True,...}` | 返回字段开关 |
| `SSH_CONFIG_MODE` | `"standard"` | SSH 配置模式: `"standard"` \| `"custom"` |
| `SSH_HOST_NAME` | — | standard 模式 SSH Host 别名 |
| `SSH_PERSISTENT` | `True` | SSH 长连接复用 |
| `SSH_CONNECTION_TIMEOUT` | `10` | SSH 连接超时秒数 |
| `LOG_FILE` | `"log.txt"` | 日志文件路径 |
| `LOG_LEVEL` | `"INFO"` | 日志级别 |

### OpenSandbox 前置条件

如需使用 OpenSandbox 后端 (`SANDBOX_BACKEND = "opensandbox"`)：

1. 前置依赖：Docker Desktop 已安装运行

2. 安装 Server（全局）：

   ```bash
   uv tool install opensandbox-server
   ```

3. 部署配置：

   ```bash
   copy docs\opensandbox\.sandbox.toml %USERPROFILE%\.sandbox.toml
   ```

4. 切换后端：`config.py` → `SANDBOX_BACKEND = "opensandbox"`
5. API Key：本地开发随意，但不建议留空，否则会阻塞让你手动确认，生产环境设 `SANDBOX_OPEN_API_KEY`

> 首次调用 `execute_sandbox` 时自动拉起 `opensandbox-server`，`atexit` 自动清理。

### SSH 远程执行前置条件

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

## 工具

### execute_local

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
| `shell` | str | null | 指定 Shell: `"pwsh"`\|`"cmd"`\|`"bash"` |
| `output_file` | str | "" | 输出过长时落盘路径 |

### execute_sandbox

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
| `output_file` | str | "" | 输出过长时落盘路径 |

### execute_remote

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
| `output_file` | str | "" | 输出过长时落盘路径 |

## 测试

```bash
uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

## 日志

日志写入项目根目录 `log.txt`，格式:

```bash
2026-07-30 12:00:00 [INFO] local: execute: echo hello
2026-07-30 12:00:00 [INFO] local: exit_code=0 duration=0.012
```

## 协议

MIT