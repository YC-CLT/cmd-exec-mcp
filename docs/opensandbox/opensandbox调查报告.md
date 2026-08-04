# OpenSandbox 调查报告

> 调研时间：2026-08-04 | 来源：GitHub、InfoQ、项目内 docs/

---

## 一、基本信息

| 项目 | 内容 |
|---|---|
| 名称 | OpenSandbox |
| 组织 | 阿里巴巴（陶宇田） |
| 开源 | 2026.3.1，Apache 2.0 |
| 定位 | AI Agent 沙箱基础设施，协议优先 |
| 热度 | 2天 3.8k+ stars |

---

## 二、核心 API

### 2.1 Lifecycle API（`localhost:8080/v1`），认证头 `OPEN-SANDBOX-API-KEY`

| 端点 | 说明 |
|---|---|
| `POST /sandboxes` | 创建沙箱（image/timeout/resource/env/metadata） |
| `GET /sandboxes/{id}` | 查询状态 |
| `DELETE /sandboxes/{id}` | 销毁 |
| `POST /sandboxes/{id}/pause` | 暂停 |
| `POST /sandboxes/{id}/resume` | 恢复 |
| `POST /sandboxes/{id}/renew-expiration` | 续期 TTL |

状态机：`Pending → Running → Paused → Resuming → Running → Stopping → Terminated/Failed`

### 2.2 Execd API（沙箱内，默认 `localhost:44772`），认证头 `X-EXECD-ACCESS-TOKEN`

| 分类 | 端点 | 说明 |
|---|---|---|
| 命令 | `POST /command` | 执行 shell（SSE 流式） |
| | `DELETE /command` | 中断 |
| | `GET /command/status/{id}` | 查询状态 |
| | `GET /command/{id}/logs` | 获取累积输出 |
| 会话 | `POST /session` | 创建持久 bash 会话 |
| | `POST /session/{id}/run` | 会话中执行（SSE） |
| 代码 | `POST /code/context` | 创建有状态代码上下文 |
| | `POST /code` | 执行代码（SSE） |
| 文件 | `POST /files/upload` | 上传 |
| | `GET /files/download` | 下载 |
| | `GET /files/search` | 搜索（glob） |
| | `POST /files/replace` | 批量替换 |
| | `DELETE /files` | 删除 |
| 目录 | `GET /directories/list` | 列出 |
| | `POST /directories` | 创建 |
| | `DELETE /directories` | 递归删除 |
| 指标 | `GET /metrics` | CPU/内存 |
| | `GET /metrics/watch` | 实时 SSE 流 |

SSE 事件：`stdout` / `stderr` / `result` / `execution_complete` / `error`

---

## 三、Python SDK 速查

```bash
pip install opensandbox   # 异步
```

### 连接配置

```python
from opensandbox.config import ConnectionConfig
config = ConnectionConfig(domain="localhost:8080", api_key="...")
# 环境变量：OPEN_SANDBOX_DOMAIN / OPEN_SANDBOX_API_KEY
```

### 沙箱生命周期

```python
from opensandbox.sandbox import Sandbox
from datetime import timedelta

sandbox = await Sandbox.create("opensandbox/code-interpreter:v1.1.0", connection_config=config, timeout=timedelta(minutes=10))
await sandbox.renew(timedelta(minutes=30))
await sandbox.pause()
sandbox = await Sandbox.resume(sandbox_id=sandbox.id, connection_config=config)
await sandbox.destroy()  # = kill + close
```

### 命令执行

```python
# 同步
execution = await sandbox.commands.run("echo hello")
print(execution.logs.stdout[0].text)

# 流式
from opensandbox.models.execd import ExecutionHandlers
handlers = ExecutionHandlers(
    on_stdout=lambda msg: print(msg.text),
    on_stderr=lambda msg: print(msg.text),
)
result = await sandbox.commands.run("for i in 1 2 3; do echo $i; sleep 1; done", handlers=handlers)
```

### 文件操作

```python
from opensandbox.models.filesystem import WriteEntry, SearchEntry

await sandbox.files.write_files([WriteEntry(path="/tmp/x.txt", data="hello", mode=644)])
content = await sandbox.files.read_file("/tmp/x.txt")
files = await sandbox.files.search(SearchEntry(path="/tmp", pattern="*.txt"))
await sandbox.files.delete_files(["/tmp/x.txt"])
```

### 创建参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `image` | 必填 | 镜像名 |
| `timeout` | 10min | 自动销毁 |
| `entrypoint` | `["tail", "-f", "/dev/null"]` | 容器入口 |
| `resource` | `{"cpu":"1","memory":"2Gi"}` | 资源限制 |
| `env` | `{}` | 环境变量 |
| `metadata` | `{}` | 自定义标签 |

---

## 四、安全隔离

| 层 | 技术 | 强度 | 速度 |
|---|---|---|---|
| 轻 | gVisor | 系统调用拦截 | 快 |
| 中 | Kata Containers | 轻量 VM | 中 |
| 强 | Firecracker microVM | 硬件虚拟化 | 慢 |

通过 `[secure_runtime]` 配置切换。

---

## 五、与 cmd-exec-mcp 对比

| 维度 | OpenSandbox | cmd-exec-mcp |
|---|---|---|
| 定位 | 沙箱基础设施 | MCP 命令通道 |
| 隔离 | gVisor/Kata/Firecracker | Docker `--rm` |
| 生命周期 | 完整（创建/暂停/恢复/续期） | 用完即焚 |
| 文件系统 | 内置 CRUD API | 无 |
| 代码解释器 | 内置 | 无 |
| 网络控制 | Ingress/Egress + sidecar | 无 |
| 认证 | API Key | 无 |
| 部署 | 需独立 Server 进程 | 直接 `uv run` |
| SDK | Python/Java/Go/.NET/TS | MCP 协议 |

---

## 六、cmd-exec-mcp 集成方案（已有设计文档）

设计文档：[docs/superpowers/specs/2026-07-30-execute-opensandbox-design.md](file:///D:/CodeFile/cmd-exec-mcp/docs/superpowers/specs/2026-07-30-execute-opensandbox-design.md)

| 要点 | 说明 |
|---|---|
| 后端切换 | `config.SANDBOX_BACKEND` = `"docker"` \| `"opensandbox"` |
| 新执行器 | `executors/opensandbox.py`，封装 `opensandbox` SDK |
| 自动启动 | `main.py` 启动 `opensandbox-server` 子进程，`atexit` 清理 |
| 安全策略 | 跳过黑白名单，依赖 gVisor/Kata |
| 签名精简 | 移除 `image`/`mount`/`cwd`，走配置常量 |
| 新配置 | `SANDBOX_OPEN_TEMPLATE`、`SANDBOX_OPEN_SERVER_HOST`/`PORT` |

```
main.py
  ├── 启动 opensandbox-server 子进程
  ├── SANDBOX_BACKEND 路由
  │     ├── "docker"      → SandboxExecutor
  │     └── "opensandbox" → OpenSandboxExecutor
  └── execute_sandbox MCP 工具（统一签名）
```

---

## 七、结论

1. OpenSandbox 是 AI Agent 沙箱"基础设施级"方案，功能远超 cmd-exec-mcp 的 Docker 模式
2. 两者定位不同、可互补：cmd-exec-mcp 轻量命令通道，OpenSandbox 完整沙箱平台
3. 集成方案已就绪，通过 `SANDBOX_BACKEND` 一键切换后端
4. 关注点：`opensandbox` SDK API 稳定性、execd 镜像版本匹配、生产环境需配 api_key