# cmd-exec-mcp

MCP 协议的远程命令执行服务，支持本地执行和 Docker 沙箱隔离执行。

## 功能

- **本地执行** (`execute_local`): 在宿主机执行命令
- **沙箱执行** (`execute_sandbox`): 在 Docker 容器中隔离执行，用完即焚
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
      "args": ["run", "--directory", "D:\\CodeFile\\cmd-exec-mcp", "main.py"]
    }
  }
}
```

## 配置

编辑 `config.py`:

| 配置 | 默认值 | 说明 |
|---|---|---|
| `SECURITY_MODE` | `"restricted"` | 本地安全模式 |
| `COMMAND_WHITELIST` | `["ls","dir","git",...]` | 本地白名单 |
| `COMMAND_BLACKLIST` | `["rm","del","shutdown",...]` | 本地黑名单 |
| `SANDBOX_SECURITY_MODE` | `"full"` | 沙箱安全模式 |
| `SANDBOX_DEFAULT_IMAGE` | `"ubuntu"` | 沙箱默认镜像 |
| `DEFAULT_TIMEOUT` | `-1` | 超时（-1 无限制） |
| `LOG_FILE` | `"log.txt"` | 日志文件路径 |

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
| `parallel` | bool | false | 是否并行执行 |
| `timeout` | int | -1 | 超时秒数，-1 无限制 |
| `cwd` | str | null | 工作目录，受限模式忽略 |
| `env` | dict | null | 环境变量 |
| `fields` | dict | null | 返回字段过滤 |

### execute_sandbox

在 Docker 容器中执行命令，用完即焚。

```json
{
  "command": "echo hello",
  "image": "alpine",
  "mount": "/host:/container",
  "cwd": "/workspace",
  "parallel": false,
  "timeout": 30
}
```

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | str | 必填 | 命令 |
| `image` | str | ubuntu | Docker 镜像 |
| `mount` | str | null | 挂载 `host:container` |
| `cwd` | str | null | 容器内工作目录 |
| `parallel` | bool | false | 是否并行 |
| `timeout` | int | -1 | 超时秒数 |
| `env` | dict | null | 环境变量 |
| `fields` | dict | null | 返回字段过滤 |

## 测试

```bash
uv run pytest tests/ -v
```

## 日志

日志写入项目根目录 `log.txt`，格式:

```
2026-07-30 12:00:00 [INFO] local: execute: echo hello
2026-07-30 12:00:00 [INFO] local: exit_code=0 duration=0.012
```

## 协议

MIT
