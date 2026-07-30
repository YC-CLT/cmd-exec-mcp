# CHANGELOG

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