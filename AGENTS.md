# AGENTS.md

## 环境

- Python 3.11，uv 管理依赖
- config.py 集中配置所有常量，pyproject.toml 管理依赖

## 关键文件

| 文件 | 作用 |
|------|------|
| `config.py` | 所有配置常量（安全、沙箱、SSH、后端切换） |
| `main.py` | MCP 服务入口，工具注册、安全校验、进程检测单例 |
| `executors/base.py` | 执行器抽象基类 |
| `executors/local.py` | 本地命令执行器 |
| `executors/sandbox.py` | Docker 沙箱执行器 |
| `executors/opensandbox.py` | OpenSandbox 沙箱执行器 |
| `executors/remote.py` | SSH 远程执行器（asyncssh） |
| `models.py` | ExecResult 数据模型 |
| `tests/` | 测试目录 |

## 关键常量

| 常量 | 位置 | 说明 |
|------|------|------|
| `SECURITY_MODE` | config.py | 本地/远程安全模式 restricted/full |
| `COMMAND_WHITELIST` / `BLACKLIST` | config.py | 本地/远程黑白名单 |
| `SANDBOX_BACKEND` | config.py | 沙箱后端 docker/opensandbox |
| `SANDBOX_SECURITY_MODE` | config.py | 沙箱安全模式（仅 Docker 后端生效） |
| `SANDBOX_COMMAND_WHITELIST` / `BLACKLIST` | config.py | 沙箱黑白名单 |
| `SANDBOX_DEFAULT_IMAGE` | config.py | Docker 沙箱默认镜像 |
| `SANDBOX_OPEN_*` | config.py | OpenSandbox 连接配置组（TEMPLATE/HOST/PORT/API_KEY） |
| `DEFAULT_TIMEOUT` | config.py | 默认超时 -1 无限制 |
| `FORCE_SHELL` | config.py | 强制指定 Shell |
| `SSH_CONFIG_MODE` | config.py | SSH 配置模式 standard/custom |
| `SSH_HOST_NAME` | config.py | standard 模式 SSH Host 别名 |
| `SSH_PERSISTENT` | config.py | 长连接复用开关 |

## 规则

- **禁止使用 RunCommand 执行命令**：用 `cmd-exec-mcp` 的 `execute_local` / `execute_sandbox` / `execute_remote`
- **execute_local cwd 必填**：`cwd` 无默认值，调用方必须显式传入工作目录
- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 创建本地副本，monkeypatch 无法穿透；executor 同理，需 patch `executors.模块名.X`
- **executor 签名变更全链适配**：方法签名变动时，main.py 工具、测试、同接口的其他 executor 都要同步
- **config 重命名全量 grep**：常量改名/移除后，搜索所有引用点确保同步更新
- **跨 Task 依赖等待**：并行派发时，先检查上游 Task 产物是否存在，确认就绪后再动自己的代码

## 查文献指南

| 资源 | 路径 |
|------|------|
| 项目设计文档 | `docs/superpowers/specs/` |
| 项目实现计划 | `docs/superpowers/plans/` |
| OpenSandbox 文档 | `docs/opensandbox/`（api/configuration/pysdk/server/调查报告） |
| OpenSandbox 官方 | `open-sandbox.ai/sdks/code-interpreter/python` |

## 工具/MCP

- **wet-mcp**：`search`/`extract`/`media`/`help`/`config`，`extract` 参数名是 `urls`（数组），详见 `mcp_tools_summary.csv`

## 工作流

```
构想 → 计划 → 实施 → 验收 → 记录（写CHANGELOG + 经验教训写入本文）→ 提交
  │      │       │       │
  │      │       │       └── 人工验收（3号机）
  │      │       └── dispatching-parallel-agents 并行派发
  │      └── writing-plans 生成实现计划
  └── brainstorming 需求澄清 + 设计方案
```

### 详细步骤

1. **brainstorming**：需求澄清 → 多方案对比 → 逐节确认设计 → 写入 `docs/superpowers/specs/<date>-design.md`
2. **writing-plans**：从 spec 生成 TDD 实现计划，按模块拆分 Task，每步 2-5 分钟粒度 → 写入 `docs/superpowers/plans/<date>-plan.md`
3. **dispatching-parallel-agents**：三机并行派发
   - **1号机**：基础层（config + models + 依赖）
   - **2号机**：业务层（executors + main + 安全校验）
   - **3号机**：验收层（跑全量测试 + 手工验证）
   - 提示词只写 Task 编号和关键约束，让 agent 自己读 plan
4. **记录**：更新 CHANGELOG + 本文经验教训 → 提交

## 经验/坑点

- **WebFetch 无法使用**：用 `Invoke-WebRequest` 或 `wet-mcp extract`
- **Temp 目录不可读**：Read 工具无法访问 `D:\Temp`，MCP 长输出需 Copy-Item 到项目根目录
- **uv sync 会清 dev 依赖**：`uv sync` 只同步 `[project.dependencies]`，依赖变更后使用 `uv pip install -e ".[dev]"` 保留 dev 依赖
- **Windows shell 单引号陷阱**：cmd.exe 不认单引号，跨平台测试命令一律用双引号
- **pwsh 冷启动 ~2s**：Windows 默认 Shell 用 `cmd`（~0.15s），需要 `&&` 时传 `shell="pwsh"`
- **subprocess 三大坑**：① `env=` 替换整个环境变量导致 PATH 丢失，先 `os.environ.copy()` 再 `.update()`；② `shell=True` + `cmd /c` 双层包装导致引号转义断裂；③ `timeout=` 只杀父进程，子进程残留，用 `Popen` + `communicate` + `taskkill /F /T /PID`
- **Windows 管道句柄继承**：`asyncio.create_subprocess_shell` 管道可被孙子进程继承，改用 `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`
- **OpenSandbox entrypoint 陷阱**：默认 entrypoint 不执行 `code-interpreter.sh`，Python 等运行时不在 PATH。必须显式传 `entrypoint=["/opt/code-interpreter/code-interpreter.sh"]` + env 版本变量
- **OpenSandbox env 注入优于命令前缀**：镜像源等环境变量通过 `Sandbox.create(env=...)` 注入，比 Docker 后端 `--entrypoint` 方案更干净
- **OpenSandbox 超时**：`Sandbox.create()` 的 timeout 接受 `timedelta` 或 `None`，`-1` 需转为 `None`
- **sys.modules mock 对已导入模块无效**：用 `monkeypatch.setattr(executor_module, "ClassName", mock_cls)` 直接打补丁
- **logging.basicConfig 只生效一次**：后续调用是 no-op
- **fastmcp 3.x API 内部属性不可用**：`mcp._tool_manager._tools` 不存在，用 `await mcp.list_tools()`
- **plan 中的 API 可能不存在**：plan 引用的 API 在实际库中可能不同名，实现时以实际库文档为准
- **asyncssh.connect 原生支持 ssh_config**：`asyncssh.connect(host=alias, config=[~/.ssh/config])` 直接读取 Host 别名
- **RemoteExecutor 长连接模式**：`SSH_PERSISTENT=True` 时检查 `is_closed()` 决定复用/重连，非持久模式 `finally` 中 close
- **Python 3.11 asyncio proactor warning**：Windows 已知 bug，不影响测试结果