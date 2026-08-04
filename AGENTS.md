# AGENTS.md

## 环境

- uv环境，py3.11
- 本地命令执行走 `cmd-exec-mcp` 的 `execute_local`，不手动跑命令
- Docker 沙箱模式需要本地 Docker 环境，走 `execute_sandbox`
- OpenSandbox 沙箱模式按需懒启动，首次调用 `execute_sandbox` 时自动启动 `opensandbox-server`

## 关键文件

| 文件 | 作用 |
|------|------|
| `config.py` | 所有配置常量（安全、沙箱、日志、后端切换） |
| `main.py` | MCP 服务入口，工具注册、安全校验、进程检测单例 |
| `executors/base.py` | 执行器抽象基类 |
| `executors/local.py` | 本地命令执行器 |
| `executors/sandbox.py` | Docker 沙箱执行器 |
| `executors/opensandbox.py` | OpenSandbox 沙箱执行器（封装 opensandbox SDK） |
| `models.py` | ExecResult 数据模型 |
| `tests/` | 测试目录 |

## 关键常量

| 常量 | 位置 | 说明 |
|------|------|------|
| `SECURITY_MODE` | config.py | 本地安全模式 restricted/full |
| `COMMAND_WHITELIST` | config.py | 本地白名单 |
| `COMMAND_BLACKLIST` | config.py | 本地黑名单 |
| `SANDBOX_BACKEND` | config.py | 沙箱后端 docker/opensandbox |
| `SANDBOX_SECURITY_MODE` | config.py | 沙箱安全模式（仅 Docker 后端生效） |
| `SANDBOX_COMMAND_WHITELIST` | config.py | 沙箱白名单 |
| `SANDBOX_COMMAND_BLACKLIST` | config.py | 沙箱黑名单 |
| `SANDBOX_DEFAULT_IMAGE` | config.py | 沙箱默认镜像 ubuntu |
| `SANDBOX_DEFAULT_MOUNT` | config.py | 沙箱默认挂载 None |
| `SANDBOX_OPEN_TEMPLATE` | config.py | OpenSandbox 模板镜像 |
| `SANDBOX_OPEN_SERVER_HOST` | config.py | OpenSandbox Server 地址 |
| `SANDBOX_OPEN_SERVER_PORT` | config.py | OpenSandbox Server 端口 |
| `SANDBOX_OPEN_API_KEY` | config.py | OpenSandbox API Key（生产必填） |
| `DEFAULT_TIMEOUT` | config.py | 默认超时 -1 无限制 |
| `FORCE_SHELL` | config.py | 强制指定 Shell None 自动检测 |
| `RESULT_FIELDS` | config.py | 返回字段开关 |
| `LOG_FILE` | config.py | 日志文件 log.txt |
| `LOG_FORMAT` | config.py | 日志格式 |
| `LOG_DATE_FORMAT` | config.py | 日志时间格式 |

## 规则

- **禁止使用 RunCommand 执行命令**：用 `cmd-exec-mcp` 的 `execute_local` / `execute_sandbox`
- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 创建本地副本，monkeypatch 无法穿透
- **executor 签名变更影响链**：方法签名变动时，main.py 工具、测试、同接口的其他 executor 都要同步适配
- **config 重命名需全量搜索**：常量改名/移除后，grep 全量引用，确保测试、main.py、executor 等所有引用点同步更新
- **跨 Task 依赖等待**：并行派发时，先检查上游 Task 产物是否存在，确认就绪后再动自己的代码

## 查文献指南

| 资源 | 路径 | 说明 |
|------|------|------|
| 项目设计文档 | `docs/superpowers/specs/` | 各模块设计 spec |
| 项目实现计划 | `docs/superpowers/plans/` | 各模块实现 plan |
| OpenSandbox SDK API | `docs/opensandbox/api.md` | OpenSandbox API 端点 |
| OpenSandbox SDK 配置 | `docs/opensandbox/configuration.md` | 配置项说明 |
| OpenSandbox Python SDK | `docs/opensandbox/pysdk.md` | SDK 用法速查 |
| OpenSandbox Server | `docs/opensandbox/server.md` | Server 部署 |
| OpenSandbox 调查报告 | `docs/opensandbox/opensandbox调查报告.md` | 调研总结、对比分析 |

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
- **Temp 目录不可读**：Read 工具无法访问 `D:\Temp`，MCP 长输出需 Copy-Item 到项目根目录，然后正则替换`\n`为`\\n`，否则将输出超长行
- **uv pip install 污染宿主 venv**：有 `.python-version` 的项目必须用 `uv sync` 创建隔离环境
- **Windows shell 单引号陷阱**：cmd.exe 不认单引号，跨平台测试命令一律用双引号
- **OpenSandbox entrypoint 陷阱**：`Sandbox.create()` 默认 entrypoint 是 `["tail", "-f", "/dev/null"]`，不执行 `code-interpreter.sh` 会导致 Python 等运行时不在 PATH。必须显式传 `entrypoint=["/opt/code-interpreter/code-interpreter.sh"]` + `env` 版本变量
- **OpenSandbox env 注入优于命令前缀**：镜像源等环境变量通过 `Sandbox.create(env=...)` 注入，pip/npm/go 自动识别，比 Docker 后端 `--entrypoint bash -lc "export...; cmd"` 更干净
- **官方文档优先于猜测**：OpenSandbox 的正确用法在 `open-sandbox.ai/sdks/code-interpreter/python`，不在本地 docs/ 里。
- **Python 3.11 asyncio proactor warning**：Windows 已知 bug，不影响测试结果
- **fastmcp 3.x API 内部属性不可用**：`mcp._tool_manager._tools` 不存在，用 `await mcp.list_tools()`
- **Docker sh -c 命令引号**：`sh -c` 后的命令必须双引号包裹，`shlex.quote()` 输出单引号不兼容 Windows
- **Windows 管道句柄继承**：`asyncio.create_subprocess_shell` 管道可被孙子进程继承，改用 `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`
- **pwsh 冷启动 ~2s**：Windows 默认 Shell 用 `cmd`（~0.15s），需要 `&&` 时传 `shell="pwsh"`
- **sys.modules mock 对已导入模块无效**：已在内存的模块不重载，用 `monkeypatch.setattr(executor_module, "SDKClass", mock_cls)` 直接打补丁
- **logging.basicConfig 只生效一次**：Python logging 的 basicConfig 只在首次调用生效，后续调用是 no-op
- **opensandbox SDK 超时**：`Sandbox.create()` 的 timeout 接受 `timedelta` 或 `None`，`-1` 需转为 `None`
- **cmd /c 双层包装**：`subprocess.run(shell=True)` 在 Windows 上已走 `cmd.exe /c`，`wrap_command` 不应再包一层 `cmd /c`，否则引号双层转义导致命令断裂
- **env 全覆盖陷阱**：`subprocess.run(env=user_env)` 替换整个环境变量，PATH 丢失致 `chcp` 等命令找不到，应先 `os.environ.copy()` 再 `.update()`
- **Windows 超时进程树残留**：`subprocess.run(timeout=N)` 只杀 `cmd.exe`，子进程残留导致 `run()` 迟迟不返回，改用 `Popen` + `communicate(timeout=...)` + `taskkill /F /T /PID` 杀进程树