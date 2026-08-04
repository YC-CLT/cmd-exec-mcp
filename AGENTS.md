# AGENTS.md

## 环境

- uv环境，py3.11
- 本地命令执行走 `cmd-exec-mcp` 的 `execute_local`，不手动跑命令
- Docker 沙箱模式需要本地 Docker 环境，走 `execute_sandbox`

## 关键文件

| 文件 | 作用 |
|------|------|
| `config.py` | 所有配置常量（安全、沙箱、日志） |
| `main.py` | MCP 服务入口，工具注册和安全校验 |
| `executors/base.py` | 执行器抽象基类 |
| `executors/local.py` | 本地命令执行器 |
| `executors/sandbox.py` | Docker 沙箱执行器 |
| `models.py` | ExecResult 数据模型 |
| `tests/` | 测试目录 |

## 关键常量

| 常量 | 位置 | 说明 |
|------|------|------|
| `SECURITY_MODE` | config.py | 本地安全模式 restricted/full |
| `COMMAND_WHITELIST` | config.py | 本地白名单 |
| `COMMAND_BLACKLIST` | config.py | 本地黑名单 |
| `SANDBOX_SECURITY_MODE` | config.py | 沙箱安全模式（独立配置） |
| `SANDBOX_COMMAND_WHITELIST` | config.py | 沙箱白名单 |
| `SANDBOX_COMMAND_BLACKLIST` | config.py | 沙箱黑名单 |
| `SANDBOX_DEFAULT_IMAGE` | config.py | 沙箱默认镜像 ubuntu |
| `SANDBOX_DEFAULT_MOUNT` | config.py | 沙箱默认挂载 None |
| `SINGLETON_LOCK_FILE` | config.py | 单例锁文件名 |
| `DEFAULT_TIMEOUT` | config.py | 默认超时 -1 无限制 |
| `FORCE_SHELL` | config.py | 强制指定 Shell None 自动检测 |
| `RESULT_FIELDS` | config.py | 返回字段开关 |
| `LOG_FILE` | config.py | 日志文件 log.txt |
| `LOG_FORMAT` | config.py | 日志格式 |
| `LOG_DATE_FORMAT` | config.py | 日志时间格式 |

## 规则

- **禁止使用 RunCommand**：命令行工具故障，AI 无法看到返回。本地命令用 `cmd-exec-mcp` 的 `execute_local`，沙箱命令用 `execute_sandbox`
- 所有命令执行走 MCP，不输出代码块让用户手动跑
- 文本替换用 pwsh 正则：`(Get-Content file) -replace 'a','b' | Set-Content file`
- WebFetch 只能搜索不能提取正文，提取网页用 `wet-mcp extract`
- MCP 输出过长时：`; Copy-Item` 到根目录再 `\\n`→`\n` 还原换行
- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 会创建本地副本，monkeypatch 无法穿透
- **logging.basicConfig 只生效一次**：local.py 和 sandbox.py 各自调用，但 Python logging 的 basicConfig 只在首次调用生效，后续是 no-op

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

- **WebSearch 污染**：同名库易被无关结果淹没，优先用 `wet-mcp search`
- **wet-mcp 提取 GitHub**：直接抓 GitHub 页面可能只拿到 license，应提取 raw 原始文件路径
- **GitHub raw 文件下载**：WebFetch 对 raw.githubusercontent.com 返回失败，用 `Invoke-WebRequest` 或 `wet-mcp extract`
- **Temp 目录不可读**：Read 工具无法访问 `D:\Temp`，MCP 长输出需 Copy-Item 到项目根目录
- **Subagent-Driven Development 与无提交约束**：当用户明确要求不提交时，subagent-driven-development 的 commit-based 工作流无法完全适用，应退化为直接实施 + 记录，跳过 commit 和 review-package 步骤
- **uv pip install 环境差异**：实际安装的 fastmcp 版本可能不同于 plan 中写的版本，plan 中的 `>=` 约束是正确的，实际安装以最新兼容版本为准
- **cross-plan CHANGELOG 共享**：多个 plan 共用同一个 CHANGELOG.md，追加时注意不要覆盖之前的内容，用 `##` 日期分隔
- **uv pip install 污染宿主 venv**：`uv pip install` 装到当前激活的 venv 而非项目自己的 `.venv`。有 `.python-version` 的项目必须用 `uv sync` 创建隔离环境
- **monkeypatch 与模块级 import**：`from config import SECURITY_MODE` 会在函数模块创建值的本地副本，`monkeypatch.setattr(config, "SECURITY_MODE", ...)` 无法穿透。必须用 `import config` + `config.SECURITY_MODE`
- **Windows shell 单引号陷阱**：`asyncio.create_subprocess_shell` 在 Windows 默认走 cmd.exe，单引号 `'...'` 被当作字面字符。跨平台测试命令一律用双引号 `"..."`
- **Python 3.11 asyncio proactor warning**：`PytestUnraisableExceptionWarning` 是 Windows 已知 bug，不影响测试结果，可安全忽略
- **跨 Task 依赖检查**：并行派发时，Task N 可能依赖 Task N-1 的产物。执行前先检查依赖文件/配置是否存在，缺则补上
- **fastmcp 3.x API 内部属性不可用**：`mcp._tool_manager._tools` 不存在，验证工具列表用 `await mcp.list_tools()`（async 方法，需 `asyncio.run` 包裹）
- **Docker sh -c 命令引号**：`" ".join(parts)` 拼接 docker 命令时 `sh -c` 后的命令必须用双引号包裹，否则只有第一个词被当作命令执行。`shlex.quote()` 输出单引号，Windows cmd.exe 不认，需手动双引号 + 转义内部双引号
- **Windows 管道句柄继承**：`asyncio.create_subprocess_shell` 在 Windows 上创建的管道句柄可被孙子进程继承，导致 `communicate()` 读不到 EOF 永久阻塞。改用 `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`，`subprocess.Popen` 默认 `close_fds=True` 用 `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` 防句柄泄漏