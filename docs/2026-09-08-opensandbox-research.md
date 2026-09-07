# OpenSandbox 调研报告

> 调研时间：2026-09-08 | 来源：GitHub 仓库

---

## 一、概况

OpenSandbox 是阿里巴巴开源的通用 AI Agent 沙箱基础设施，Apache 2.0 协议。

| 项目 | 内容 |
|---|---|
| 仓库 | [opensandbox-group/OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) |
| 定位 | AI Agent 通用沙箱平台（Coding Agent / GUI Agent / Agent 评测 / RL 训练） |
| 运行时 | Docker（本地）、Kubernetes（分布式调度） |
| 多语言 SDK | Python / Java/Kotlin / TypeScript / C#/.NET / Go |
| 配套工具 | CLI（osb）、MCP Server（opensandbox-mcp）、Code Interpreter SDK |
| 镜像 Registry | Docker Hub / GHCR / 阿里云 ACR（Cosign 无密钥签名） |

---

## 二、架构

```
┌─────────────────────────────────────────────────┐
│  SDKs (Python/Java/TS/C#/Go) + CLI + MCP Server │
├─────────────────────────────────────────────────┤
│  Lifecycle API (:8080/v1)  — 沙箱创建/暂停/恢复/销毁 │
├─────────────────────────────────────────────────┤
│  Server (FastAPI)  — Docker / Kubernetes 运行时   │
├──────────────┬──────────────────────────────────┤
│  execd       │  沙箱内执行守护进程（命令/文件）      │
│  ingress     │  入口流量代理（多路由策略）           │
│  egress      │  出口网络控制（DNS/nftables）        │
├──────────────┴──────────────────────────────────┤
│  Sandbox 镜像 (code-interpreter / ubuntu / 自定义) │
└─────────────────────────────────────────────────┘
```

### 仓库目录

| 目录 | 内容 |
|---|---|
| `sdks/` | 多语言 SDK |
| `specs/` | OpenAPI 规范 |
| `server/` | FastAPI 生命周期服务 |
| `cli/` | osb 命令行工具 |
| `kubernetes/` | K8s 部署和 CRD |
| `components/execd/` | 沙箱内执行守护进程 |
| `components/ingress/` | 入口流量代理 |
| `components/egress/` | 出口网络控制 |
| `sandboxes/` | 沙箱镜像（code-interpreter 等） |
| `examples/` | 示例代码（Coding Agent / Chrome / Playwright / VNC / VS Code） |
| `oseps/` | OpenSandbox Enhancement Proposals |

---

## 三、Lifecycle API

Base URL: `http://localhost:8080/v1`，认证头 `OPEN-SANDBOX-API-KEY`（`server.api_key` 为空时跳过）。

### 端点

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/sandboxes` | 创建沙箱（image/timeout/resource/env/metadata/entrypoint） |
| `GET` | `/sandboxes` | 列出沙箱（按状态/metadata 过滤，分页） |
| `GET` | `/sandboxes/{id}` | 查询沙箱详情 |
| `DELETE` | `/sandboxes/{id}` | 销毁沙箱 |
| `POST` | `/sandboxes/{id}/pause` | 暂停 |
| `POST` | `/sandboxes/{id}/resume` | 恢复 |
| `POST` | `/sandboxes/{id}/renew-expiration` | 续期 TTL |
| `PATCH` | `/sandboxes/{id}/metadata` | 更新元数据（JSON Merge Patch） |
| `GET` | `/sandboxes/{id}/endpoints/{port}` | 获取服务端口访问端点 |
| `POST` | `/sandboxes/{id}/snapshots` | 创建快照 |
| `GET` | `/snapshots` | 列出快照 |
| `DELETE` | `/snapshots/{id}` | 删除快照 |
| `GET` | `/sandboxes/{id}/diagnostics/logs` | 诊断日志 |
| `GET` | `/sandboxes/{id}/diagnostics/events` | 诊断事件 |

### 状态机

```
Pending → Running → Paused → Resuming → Stopping → Terminated/Failed
```

### 创建请求示例

```json
{
  "image": { "uri": "python:3.11-slim" },
  "entrypoint": ["python", "-m", "http.server", "8000"],
  "timeout": 3600,
  "resourceLimits": { "cpu": "500m", "memory": "512Mi" },
  "env": { "PYTHONUNBUFFERED": "1" },
  "metadata": { "team": "backend" }
}
```

---

## 四、execd API（沙箱内执行）

Base URL: `http://localhost:44772`，认证头 `X-EXECD-ACCESS-TOKEN`。**注意：execd 端口由 server 动态分配，通过 SDK 访问无需手动指定。**

### 命令执行

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/command` | 执行 shell 命令（SSE 流式输出） |
| `DELETE` | `/command` | 中断命令执行 |
| `GET` | `/command/status/{id}` | 查询前后台命令状态 |
| `GET` | `/command/{id}/logs` | 获取后台命令累积输出 |

### Bash Session

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/session` | 创建 bash session |
| `POST` | `/session/{id}/run` | 在 session 中执行命令（SSE 流式） |
| `DELETE` | `/session/{id}` | 删除 session |

### 代码执行（Code Interpreter）

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/code/context` | 创建执行上下文 |
| `POST` | `/code` | 执行代码（SSE 流式，支持多语言） |
| `GET` | `/code/contexts` | 列出活跃上下文 |
| `DELETE` | `/code/contexts/{id}` | 删除指定上下文 |
| `DELETE` | `/code` | 中断代码执行 |

### 文件操作

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/files/info` | 获取文件元数据 |
| `DELETE` | `/files` | 删除文件（非目录） |
| `POST` | `/files/permissions` | 修改文件权限 |
| `POST` | `/files/mv` | 移动/重命名 |
| `GET` | `/files/search` | 搜索文件（支持 glob） |
| `POST` | `/files/replace` | 批量替换文件内容 |
| `POST` | `/files/upload` | 上传文件（multipart） |
| `GET` | `/files/download` | 下载文件（支持 Range） |
| `GET` | `/directories/list` | 列出目录（支持深度控制） |
| `POST` | `/directories` | 创建目录（mkdir -p 语义） |
| `DELETE` | `/directories` | 递归删除目录 |

### 系统监控

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/metrics` | 获取 CPU/内存指标 |
| `GET` | `/metrics/watch` | 实时监控 SSE 流 |

### 隔离执行（Isolated Execution）

Base: `/v1/isolated`，提供带文件系统快照的隔离会话，核心端点：

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/session` | 创建隔离 session |
| `POST` | `/{id}/run` | 在隔离 session 中执行代码（SSE） |
| `GET` | `/{id}/diff` | 下载上层目录 diff |
| `POST` | `/{id}/commit` | 提交上层变更到工作区 |
| `GET` | `/{id}/files/*` | 文件操作（同 files API） |
| `GET` | `/{id}/directories/*` | 目录操作（同 directories API） |

### SSE 事件类型

所有执行类接口通过 SSE 流式输出，事件类型：
- `init` — 初始化
- `status` — 状态更新
- `stdout` / `stderr` — 标准输出/错误
- `result` — 执行结果
- `execution_complete` — 执行完成
- `error` — 错误信息

---

## 五、Python SDK

### 安装

```bash
pip install opensandbox          # 异步 SDK
# 可选组件
pip install opensandbox-code-interpreter  # Code Interpreter 高级封装
pip install opensandbox-cli      # osb CLI 工具
pip install opensandbox-mcp      # MCP Server
```

### 连接配置

```python
from opensandbox.config import ConnectionConfig

config = ConnectionConfig(
    domain="localhost:8080",       # 或环境变量 OPEN_SANDBOX_DOMAIN
    api_key="your-api-key",        # 或环境变量 OPEN_SANDBOX_API_KEY
    request_timeout=timedelta(seconds=30),
)
```

`ConnectionConfig` 参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `domain` | 必填 | Server 地址 |
| `api_key` | 必填 | API Key |
| `protocol` | `"http"` | http/https |
| `request_timeout` | 30s | HTTP 请求超时 |
| `debug` | `False` | 调试日志 |
| `headers` | `{}` | 自定义 HTTP 头 |
| `transport` | SDK 自建 | 共享 httpx transport（连接池） |
| `use_server_proxy` | `False` | 通过 server 代理访问 execd（客户端无法直连沙箱时） |

### 沙箱生命周期

```python
from opensandbox.sandbox import Sandbox
from datetime import timedelta

# 创建
sandbox = await Sandbox.create(
    "opensandbox/code-interpreter:v1.1.0",
    connection_config=config,
    timeout=timedelta(minutes=10),       # 自动销毁，None 不自动过期
    entrypoint=["/opt/code-interpreter/code-interpreter.sh"],
    env={"PYTHON_VERSION": "3.11"},
    resource={"cpu": "1", "memory": "2Gi"},
    metadata={"project": "demo"},
)

# 续期
await sandbox.renew(timedelta(minutes=30))

# 暂停 / 恢复
await sandbox.pause()
sandbox = await Sandbox.resume(sandbox_id=sandbox.id, connection_config=config)

# 查询状态
info = await sandbox.get_info()
print(info.status.state)   # "Running"
print(info.expires_at)     # 过期时间

# 销毁（kill + close，服务端关闭，本地资源释放）
await sandbox.destroy()
```

`Sandbox.create()` 参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `image` | 必填 | 镜像名或 URI |
| `timeout` | 10 min | 自动销毁超时 |
| `entrypoint` | `["tail", "-f", "/dev/null"]` | 容器入口 |
| `resource` | `{"cpu": "1", "memory": "2Gi"}` | 资源限制 |
| `env` | `{}` | 环境变量 |
| `metadata` | `{}` | 自定义标签（`opensandbox.io/` 前缀为系统保留） |
| `network_policy` | — | 出口网络策略 |
| `ready_timeout` | 30s | 等待就绪超时 |

### 命令执行

```python
# 同步执行
execution = await sandbox.commands.run("echo hello")
print(execution.logs.stdout[0].text)   # stdout 文本列表
print(execution.exit_code)

# 流式输出
from opensandbox.models.execd import ExecutionHandlers

async def on_stdout(msg): print(f"out: {msg.text}")
async def on_stderr(msg): print(f"err: {msg.text}")

handlers = ExecutionHandlers(on_stdout=on_stdout, on_stderr=on_stderr)
result = await sandbox.commands.run("for i in 1 2 3; do echo $i; sleep 1; done", handlers=handlers)
```

### Bash Session

```python
# 创建 session
session_id = await sandbox.commands.create_session(working_directory="/workspace")

# 执行命令
execution = await sandbox.commands.run_in_session(session_id, "ls -la")
execution = await sandbox.commands.run_in_session(session_id, "python script.py")

# 删除 session
await sandbox.commands.delete_session(session_id)
```

### 文件操作

```python
# 写入
await sandbox.files.write_file("/tmp/hello.txt", "Hello World")

# 读取
content = await sandbox.files.read_file("/tmp/hello.txt")

# 搜索
from opensandbox.models.filesystem import SearchEntry
files = await sandbox.files.search(SearchEntry(path="/tmp", pattern="*.txt"))

# 上传（支持 str | bytes | io.IOBase）
with open("local.py", "rb") as f:
    await sandbox.files.write_file("/sandbox/script.py", f)

# 下载
data = await sandbox.files.read_file("/sandbox/out.txt")
with open("local_out.txt", "w") as f:
    f.write(data)
```

### 沙箱池（Sandbox Pool）

预创建沙箱缓冲池，减少 acquire 延迟：

```python
from opensandbox import SandboxPoolSync, AcquirePolicy, InMemoryPoolStateStore, PoolCreationSpec

pool = SandboxPoolSync(
    pool_name="demo",
    owner_id="worker-1",
    max_idle=2,
    state_store=InMemoryPoolStateStore(),
    connection_config=config,
    creation_spec=PoolCreationSpec(image="ubuntu:22.04"),
)
pool.start()
sandbox = pool.acquire(sandbox_timeout=timedelta(minutes=30), policy=AcquirePolicy.FAIL_FAST)
# ... use sandbox ...
sandbox.destroy()
pool.shutdown(graceful=True)
```

生产环境多进程/多 Pod 场景使用 Redis 后端：`pip install "opensandbox[pool-redis]"` + `RedisPoolStateStore`。

### 同步 API

```python
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync

config = ConnectionConfigSync(domain="localhost:8080", api_key="key")
sandbox = SandboxSync.create("ubuntu", connection_config=config)
execution = sandbox.commands.run("echo hello")
sandbox.destroy()
```

---

## 六、Code Interpreter 镜像

预构建镜像 `opensandbox/code-interpreter:v1.1.0`，基于 Ubuntu 24.04。

### 预装语言及版本

| 语言 | 版本 | 安装路径 |
|---|---|---|
| Python | 3.10 / 3.11 / 3.12 / 3.13 / 3.14 | `/opt/python/versions` |
| Java | 8 / 11 / 17 / 21 | `/usr/lib/jvm` |
| Node.js | v18 / v20 / v22 | `/opt/node` |
| Go | 1.23 / 1.24 / 1.25 | `/opt/go` |

默认版本：Python 3.14 / Java 21 / Node.js 22 / Go 1.25。

### 版本切换

```bash
source /opt/code-interpreter/code-interpreter-env.sh <language> <version>
# 例：source /opt/code-interpreter/code-interpreter-env.sh python 3.11
```

不指定版本号则列出可用版本。

### entrypoint 注意

默认 entrypoint 是 `["tail", "-f", "/dev/null"]`，此状态下 Python 等运行时不在 PATH。要使用预装语言需显式传入：

```python
Sandbox.create(
    "opensandbox/code-interpreter:v1.1.0",
    entrypoint=["/opt/code-interpreter/code-interpreter.sh"],
    env={"PYTHON_VERSION": "3.11"},
)
```

> `code-interpreter.sh` 根据 env 变量加载对应运行时版本到 PATH，并启动 Jupyter。

### 其他特性

- 内置 Jupyter Notebook（多语言内核：Python/Java/TypeScript/Go/Bash）
- 支持 amd64 + arm64 多架构
- `clone3-workaround`（amd64）：极旧 Docker 宿主机可用 `clone3-workaround <command>` 包裹命令
- 环境变量：`JUPYTER_HOST`/`JUPYTER_PORT`/`JUPYTER_TOKEN` 配置 Jupyter
- `EXECD_CLONE3_COMPAT`：设为 `1`/`true` 时入口脚本自动用 clone3-workaround 重新 exec 自身

---

## 七、Server 配置

### 安装与启动

```bash
pip install opensandbox-server
# 生成示例配置
opensandbox-server init-config ~/.sandbox.toml --example docker
# 启动
opensandbox-server
# 指定配置
opensandbox-server --config /path/to/sandbox.toml
# 环境变量覆盖
SANDBOX_CONFIG_PATH=/path/to/sandbox.toml
```

### 配置结构（TOML）

```toml
[server]
host = "127.0.0.1"
port = 8080
api_key = "your-secret-key"          # 为空则跳过认证，但需 OPENSANDBOX_INSECURE_SERVER=YES
max_sandbox_timeout_seconds = 86400  # 沙箱 TTL 上限，≥ 60

[runtime]
type = "docker"                      # docker | kubernetes
execd_image = "opensandbox/execd:v1.0.21"

[docker]
network_mode = "bridge"              # host | bridge | 自定义网络
port_range_min = 40000
port_range_max = 60000
drop_capabilities = ["NET_ADMIN", "SYS_ADMIN", ...]
no_new_privileges = true
pids_limit = 4096

[ingress]
mode = "direct"                      # direct | gateway

[egress]
image = "opensandbox/egress:v1.1.5"
mode = "dns"                         # dns | dns+nft

[storage]
allowed_host_paths = []              # 空则拒绝所有 host 挂载

[store]
type = "sqlite"
path = "~/.opensandbox/opensandbox.db"

[secure_runtime]                     # 可选强隔离
type = ""                            # "" | gvisor | kata | firecracker
docker_runtime = "runsc"             # gVisor 时：runsc
k8s_runtime_class = "gvisor"         # K8s 时：RuntimeClass 名

[renew_intent]                       # 按访问自动续期
enabled = false
min_interval_seconds = 60
```

### 关键环境变量

| 变量 | 说明 |
|---|---|
| `SANDBOX_CONFIG_PATH` | 配置文件路径 |
| `OPENSANDBOX_SERVER_API_KEY` | 覆盖 TOML 中的 api_key |
| `OPENSANDBOX_INSECURE_SERVER` | 无 api_key 时设为 `YES` 跳过确认 |
| `DOCKER_HOST` | Docker daemon 地址 |

---

## 八、安全隔离

| 层 | 技术 | 强度 | 可用范围 |
|---|---|---|---|
| 默认 | runc (OCI) | 基础 | Docker + K8s |
| gVisor | 系统调用拦截 | 中 | Docker + K8s |
| Kata Containers | 轻量 VM | 高 | Docker + K8s |
| Firecracker | 硬件虚拟化 microVM | 最高 | 仅 K8s |

通过 `[secure_runtime]` 配置切换。gVisor 需安装 `runsc`，Kata 需安装 `kata-runtime`。

---

## 九、其他工具

### osb CLI

```bash
pip install opensandbox-cli
osb config init
osb config set connection.domain localhost:8080
osb sandbox create --image python:3.12 --timeout 30m -o json
osb command run <sandbox-id> -o raw -- python -c "print(1 + 1)"
```

### OpenSandbox MCP Server

```bash
pip install opensandbox-mcp
opensandbox-mcp --domain localhost:8080 --protocol http
```

暴露沙箱创建、命令执行、文件操作给 MCP 客户端（Claude Code、Cursor 等）。

### Code Interpreter SDK

```python
pip install opensandbox-code-interpreter
from code_interpreter import CodeInterpreter, SupportedLanguage

interpreter = await CodeInterpreter.create(sandbox)
result = await interpreter.codes.run("print(2+2)", language=SupportedLanguage.PYTHON)
```

---

## 十、与本项目结合点

本项目（cmd-exec-mcp）通过 `SANDBOX_BACKEND = "opensandbox"` 切换为 OpenSandbox 后端，与 Docker 后端共享统一的 `execute_sandbox` MCP 工具签名。

**可用的结合方式：**

1. **配置切换**：`config.py` 中 `SANDBOX_OPEN_*` 系列常量控制连接参数、模板镜像、运行时版本、Server 生命周期
2. **执行器封装**：`executors/opensandbox.py` 已封装 `Sandbox.create()` → `commands.run()` / `commands.run_in_session()` → `Execution.logs` 核心调用链，以及文件上传下载
3. **Server 管理**：`main.py` 中懒加载 + idle watchdog 机制，自动管理 `opensandbox-server` 子进程的启停
4. **Session 模式**：支持 detach 模式，通过 `sandbox.commands.create_session()` 创建持久 bash session

---

## 十一、经验与坑点

1. **Windows 代理陷阱**：`urllib.urlopen()` 和 `httpx` 在 Windows 上自动读系统代理，访问 `localhost` 走代理返回 502。`urllib` 用 `ProxyHandler({})`，`httpx` 用 `proxy=None`，或直接用 SDK 内置 API 避免手搓 HTTP。

2. **SDK 版本 API 变更**：0.1.15 移除 `sandbox._execd_token`，文件操作改用 `sandbox.files.write_file()`/`read_file()`（接受 `str | bytes | io.IOBase`）。

3. **Server 超时下限**：`Sandbox.create(timeout=timedelta(seconds=30))` 会被 server 拒绝，最低 60s。

4. **entrypoint 是常见坑**：默认 entrypoint 不执行 `code-interpreter.sh`，Python 等运行时不在 PATH。必须显式传 `entrypoint=["/opt/code-interpreter/code-interpreter.sh"]` + env 版本变量。

5. **env 注入优于命令前缀**：镜像源等环境变量通过 `Sandbox.create(env=...)` 注入，比 Docker `--entrypoint` 方案更干净。

6. **metadata 保留前缀**：`opensandbox.io/` 开头的 metadata key 为系统保留，用户不可设置。

7. **bridge 网络模式**：eip 和 egress sidecar 需要 `docker.network_mode = "bridge"`。

---

## 十二、结论

1. OpenSandbox 是功能完整的 AI Agent 沙箱平台，提供 Lifecycle API + execd API + 多语言 SDK + CLI + MCP Server 的完整工具链。
2. 核心 SDK 调用链：`Sandbox.create()` → `sandbox.commands.run()` / `sandbox.commands.run_in_session()` → `Execution.logs`，以及 `sandbox.files.write_file()`/`read_file()` 文件操作。
3. 生产环境建议：启用 `api_key` 认证 + gVisor/Kata 安全隔离 + pin 镜像 digest。
4. 本项目已通过 `SANDBOX_BACKEND` 统一路由接入，Docker 和 OpenSandbox 两个后端共享 MCP 工具签名。

---

## 参考来源

- [OpenSandbox GitHub](https://github.com/opensandbox-group/OpenSandbox)
- [OpenSandbox 官方文档](https://open-sandbox.ai/sdks/code-interpreter/python)
- [cmd-exec-mcp config.py](file:///D:/CodeFile/cmd-exec-mcp/config.py)
- [cmd-exec-mcp executors/opensandbox.py](file:///D:/CodeFile/cmd-exec-mcp/executors/opensandbox.py)
- [cmd-exec-mcp main.py](file:///D:/CodeFile/cmd-exec-mcp/main.py)