# CHANGELOG

## 2026-08-03 - 黑白名单模式 + Shell 包装修复

### 新增: COMMAND_LIST_MODE 黑白名单切换
- `config.py` 新增 `COMMAND_LIST_MODE` / `SANDBOX_COMMAND_LIST_MODE`
- `"whitelist"`: 仅白名单命令可执行（黑名单仍然拦截）
- `"blacklist"`: 仅黑名单拦截，其余放行，默认值
- 影响：`validate_command()`, `validate_sandbox_command()`

### 修复: wrap_command 实际生效
- `wrap_command()` 从 no-op 改为真正包装 Shell 前缀
- Windows 默认 `pwsh -Command "..."`(支持 `&&`)，Linux 默认 `bash -c '...'`
- 并行模式也走 `wrap_command` 包装
- 内部双引号正确转义（pwsh/cmd: `\"`, bash: `'\''`）

### 移除: SINGLETON_LOCK_FILE 废案
- 单例锁机制已废弃，改为 `ensure_single_instance()` 直接检查 PID

## 2026-08-03 - 执行器重构 + 文档优化

### 修复: Windows 管道句柄继承导致子进程挂起
- `asyncio.create_subprocess_shell` 在 Windows 上创建的管道句柄被孙子进程继承，`communicate()` 永远等不到 EOF
- 现象：`git` 任何命令（包括 `git --version`）都卡死超时，`echo`/`python --version` 等无子进程的命令正常
- 修复：`asyncio.create_subprocess_shell` + `proc.communicate()` → `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`
- 影响文件：`executors/local.py`, `executors/sandbox.py`

### 优化: MCP 工具 docstring
- `execute_local` / `execute_sandbox` 的 docstring 从简单 Args 格式改为紧凑摘要 + 参数速查 + 示例
- `list_tools` 返回的第一行包含完整信息（安全模式、参数、返回格式）

### 优化: mcp_tools_summary.csv
- 两个工具的 Description 从一句话扩展为完整参数说明 + 返回值格式

## 2026-07-30 - Task 1-3: 项目基础设施

### Task 1: 项目环境配置
- 更新 `pyproject.toml`，添加 `fastmcp>=0.1.0` 依赖
- 添加 dev 依赖 `pytest>=8.0.0`、`pytest-asyncio>=0.24.0`
- 配置 pytest: `asyncio_mode = "auto"`, `testpaths = ["tests"]`

### Task 2: config.py 配置常量
- 创建 `config.py`: SECURITY_MODE, COMMAND_WHITELIST/BLACKLIST, DEFAULT_TIMEOUT, DEFAULT_CWD, FORCE_SHELL, SINGLETON_LOCK_FILE, RESULT_FIELDS
- 创建 `tests/test_config.py`: 8个测试覆盖所有配置常量

### Task 3: models.py 数据模型
- 创建 `models.py`: ExecResult dataclass，含 to_dict() 字段过滤
- 创建 `tests/test_models.py`: 5个测试覆盖默认值、赋值、to_dict全字段/过滤字段/超时场景

## 2026-07-30 - Task 4-5: 执行器 + 安全校验 + MCP 工具

### Task 4: executors 包和 LocalExecutor
- 创建 `executors/__init__.py`: 空包初始化
- 创建 `executors/base.py`: `BaseExecutor` 抽象基类，定义 `execute()` / `execute_batch()` 接口
- 创建 `executors/local.py`: `LocalExecutor` 实现
  - 基于 `asyncio.create_subprocess_shell` 异步执行
  - 支持 timeout 超时控制（`asyncio.wait_for` + `proc.kill()`）
  - `execute_batch` 通过 `asyncio.gather` 并发执行
- 创建 `tests/test_executor.py`: 5个测试（基本命令、失败命令、超时、批量、duration）

### Task 5: 安全校验 + MCP 工具注册
- 重写 `main.py`:
  - `acquire_lock()` / `release_lock()`: 单例锁文件，防止多实例启动
  - `validate_command(command)`: 受限模式白名单/黑名单校验，完全模式放行
  - `detect_shell()`: FORCE_SHELL 优先，否则 Windows→powershell, 其他→bash
  - `wrap_command()` / `resolve_cwd()` / `resolve_timeout()`: 参数解析辅助
  - `execute_local()`: FastMCP tool，支持单步/并行执行，可配置返回字段
- 创建 `tests/test_security.py`: 11个测试（6 validate + 2 shell + 3 singleton）

### 修复记录
- **monkeypatch 穿透**: `from config import X` 改为 `import config` + `config.X`，让测试 monkeypatch 能动态生效
- **Windows 引号**: 测试命令 `python -c '...'` 改为 `python -c "..."`，适配 Windows cmd.exe 的单引号解析差异

## 2026-07-30 - Task 6: 端到端手动验证

### 验收结果: ✅ 通过

| 步骤 | 描述 | 结果 |
|------|------|------|
| Step 1 | 全部测试 (`uv run pytest tests/ -v`) | ✅ 29/29 passed |
| Step 2 | MCP 服务启动 (`mcp.name`) | ✅ `cmd-exec-mcp` |
| Step 3 | 本地命令执行 (`echo hello from mcp`) | ✅ stdout 含 "hello from mcp", exit_code=0 |
| Step 4 | 受限模式拒绝危险命令 (`rm -rf /`) | ✅ ValueError: blacklist denied |
| Step 5 | 并行执行 (`echo one && echo two && echo three`) | ✅ 三行输出: one, two, three |

### 环境信息
- Python 3.11.9, Windows, fastmcp 3.4.5, pytest 9.1.1
- PytestUnraisableExceptionWarning (ProactorBasePipeTransport) 为 Python 3.13 Windows 已知 bug，不影响结果

## 2026-07-30 - 项目完成总结

### 设计流程
- **brainstorming**：需求澄清（支持本地/沙箱/Docker/远程，先做本地），方案对比选定分层架构（方案B）
- **writing-plans**：生成 6 个 Task 的 TDD 实现计划，29 个测试用例
- **dispatching-parallel-agents**：三机并行派发，1号机（Task 1-3 基础层）、2号机（Task 4-5 业务层）、3号机（Task 6 验收）

### 最终交付
| 文件 | 说明 |
|------|------|
| `config.py` | 安全模式、白名单/黑名单、超时、Shell、单例锁、返回字段 |
| `models.py` | `ExecResult` dataclass，支持 `to_dict()` 字段过滤 |
| `executors/base.py` | `BaseExecutor` 抽象基类 |
| `executors/local.py` | `LocalExecutor`，asyncio.subprocess 实现 |
| `main.py` | FastMCP 服务，`execute_local` 工具，安全校验 + 单例锁 |
| `tests/` | 4 个测试文件，29 个测试用例，全部通过 |
| `docs/superpowers/specs/` | 设计文档 |
| `docs/superpowers/plans/` | 实现计划 |

### 核心能力
- 🔒 受限/完全双模式，白名单+黑名单安全校验
- 🐚 自动检测系统 Shell（Windows→PowerShell，Linux/macOS→bash），可强制指定
- ⏱️ 可配置超时（默认 -1 无限制），调用方可覆盖
- 🔀 单步/并行双模式，并行按 `&&` 拆分 + `asyncio.gather` 并发
- 🔐 单例锁文件防止多实例
- 📦 返回字段可配置（stdout/stderr/exit_code/duration/is_timeout/command_echo）

## 2026-07-30 - Task 1-2: 沙箱日志 + SandboxExecutor

### Task 1: config.py + local.py 日志
- 修改 `config.py`: 追加沙箱安全配置（SANDBOX_SECURITY_MODE, SANDBOX_COMMAND_WHITELIST/BLACKLIST, SANDBOX_DEFAULT_IMAGE, SANDBOX_DEFAULT_MOUNT）+ 日志配置（LOG_FILE, LOG_FORMAT, LOG_DATE_FORMAT）
- 修改 `executors/local.py`: 加入 `logging` 模块，执行前记录 `INFO`、非零退出记录 `WARNING`、超时记录 `ERROR`，日志写入项目根目录 `log.txt`

### Task 2: SandboxExecutor
- 创建 `executors/sandbox.py`: `SandboxExecutor` 继承 `BaseExecutor`
  - `_build_docker_cmd()`: 构建 `docker run --rm -i` 命令，支持挂载 `-v` 和工作目录 `-w`
  - `execute()`: 异步执行 Docker 命令，支持超时控制
  - `execute_batch()`: 并发执行多条 Docker 命令
  - 日志记录与 LocalExecutor 一致

### Task 3: main.py 沙箱支持
- 修改 `main.py`:
  - 新增 `validate_sandbox_command(command)`: 沙箱模式独立安全校验（SANDBOX_SECURITY_MODE / SANDBOX_COMMAND_BLACKLIST / SANDBOX_COMMAND_WHITELIST）
  - 新增 `execute_sandbox()`: FastMCP tool，支持 Docker 沙箱执行，参数 image/mount/cwd 可覆盖
  - 导入 `SandboxExecutor`，实例化 `sandbox = SandboxExecutor()`

## 2026-07-30 - Task 4-6: 沙箱测试 + README + 验收

### Task 4: 测试
- 创建 `tests/test_sandbox_executor.py`: 5 个测试覆盖 `_build_docker_cmd`（基本命令、自定义镜像、挂载、工作目录、组合）
- 创建 `tests/test_sandbox_security.py`: 4 个测试覆盖 `validate_sandbox_command`（完全模式放行、黑名单拦截、白名单过滤、黑名单优先）

### Task 5: README.md
- 编写 `README.md`: 自用项目风格，MIT 协议，含功能列表、安装、配置表、使用示例、测试命令、日志说明

### Task 6: 验收
- 全量测试: ✅ 38/38 passed
- MCP 工具列表: ✅ `['execute_local', 'execute_sandbox']`

### 修复记录
- **monkeypatch 穿透（沙箱）**: `validate_sandbox_command` 中 `SANDBOX_SECURITY_MODE` 等从 `from config import` 改为 `config.SANDBOX_SECURITY_MODE`，使测试 monkeypatch 能动态生效
- **fastmcp 3.x API 差异**: `mcp._tool_manager._tools` 不存在，改用 `await mcp.list_tools()`（async）获取工具列表

## 2026-08-03 - 沙箱修复 + AGENTS.md 更新

### 修复: SandboxExecutor `_build_docker_cmd` 命令引号缺失
- `" ".join(parts)` 拼接后 `sh -c` 后的命令无引号，Docker 容器内 `sh -c` 只取第一个词作为命令，其余词变成 `sh` 的位置参数
- 现象：`echo hello from sandbox` 的 stdout 为空，exit_code 仍为 0
- 修复：`escaped = command.replace('"', '\\"')` + `f'"{escaped}"'` 手动双引号包裹
- 不可用 `shlex.quote()`：输出单引号，Windows cmd.exe 不认，导致容器内 "Unterminated quoted string" 错误

### AGENTS.md 更新
- 环境：命令执行改为走 `cmd-exec-mcp` 的 `execute_local` / `execute_sandbox`，不再手动跑
- 规则：去掉 `;` 前缀和 `cmd /c` 约束，改为 MCP 执行
- 坑点：新增 Docker sh -c 命令引号