# CHANGELOG

## 2026-08-04 — OpenSandbox 集成

### 新增：OpenSandbox 沙箱后端
- `config.py` 追加 `SANDBOX_BACKEND`（`docker`/`opensandbox`）及 OpenSandbox 配置常量（`SANDBOX_OPEN_TEMPLATE`、`SANDBOX_OPEN_SERVER_HOST`、`SANDBOX_OPEN_SERVER_PORT`、`SANDBOX_OPEN_API_KEY`）
- `executors/opensandbox.py`：`OpenSandboxExecutor`，封装 opensandbox SDK（`Sandbox.create()` → `commands.run()` → `destroy()`）
- `main.py`：`start_opensandbox_server()` 自动启动子进程，`atexit` 自动关闭；`execute_sandbox` 根据 `SANDBOX_BACKEND` 路由到 Docker 或 OpenSandbox executor
- `pyproject.toml`：追加 `opensandbox>=0.1.0` 依赖

### 精简：execute_sandbox 工具签名
- 移除 `image`/`mount`/`cwd` 参数，统一从 config 常量读取
- 工具签名变为 5 参数：`(command, timeout, env, parallel, fields)`

### 优化：OpenSandbox Server 懒启动
- `main.py`：`start_opensandbox_server()` 从 MCP 启动时调用改为首次 `execute_sandbox` 时按需启动，`_opensandbox_server_started` 防重复

### 测试
- `tests/test_opensandbox_executor.py`：4 个 Mock SDK 测试
- `tests/test_security.py`：2 个 `SandboxBackendRouting` 异步测试
- 全量 43/43 passed

### 修复记录
- **sys.modules mock 模块缓存**：已导入的模块不重载，需用 `monkeypatch.setattr(executor_module, "SDKClass", mock_cls)` 直接打补丁
- **backend routing 测试**：mock `main.sandbox.execute` 比 mock `validate_sandbox_command` 更准确

## 2026-08-03 — 黑白名单模式 + Shell 可选 + 修复

### 新增
- `execute_local` 新增 `shell` 参数（`"pwsh"`/`"cmd"`/`"bash"`），Windows 默认 `cmd`（~0.15s），需要 `&&` 时传 `shell="pwsh"`
- `COMMAND_LIST_MODE` / `SANDBOX_COMMAND_LIST_MODE`：`"whitelist"` 仅白名单可执行，`"blacklist"` 仅黑名单拦截（默认）

### 修复
- `wrap_command()` 从 no-op 改为真正包装 Shell 前缀
- Windows 管道句柄继承：`asyncio.create_subprocess_shell` → `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`
- `SandboxExecutor._build_docker_cmd`：`sh -c` 后的命令必须双引号包裹，`shlex.quote()` 不兼容 Windows
- `COMMAND_LIST_MODE` 引入后测试同步更新

### 优化
- MCP 工具 docstring 改为紧凑摘要 + 参数速查 + 示例
- `mcp_tools_summary.csv` 扩展参数说明

## 2026-07-30 — 沙箱模式 + 日志

### 新增
- `executors/sandbox.py`：`SandboxExecutor`，Docker 沙箱执行（`docker run --rm -i`）
- `config.py`：沙箱安全配置（`SANDBOX_SECURITY_MODE`、`SANDBOX_COMMAND_WHITELIST/BLACKLIST`、`SANDBOX_DEFAULT_IMAGE`、`SANDBOX_DEFAULT_MOUNT`）+ 日志配置
- `executors/local.py`：logging 日志写入项目根目录 `log.txt`
- `main.py`：`validate_sandbox_command()` + `execute_sandbox()` MCP 工具
- `tests/test_sandbox_executor.py`（5 测试）、`tests/test_sandbox_security.py`（4 测试）
- `README.md`：MIT 协议，自用项目

### 修复
- **monkeypatch 穿透（沙箱）**：`from config import` → `import config` + `config.X`
- **fastmcp 3.x API**：`mcp._tool_manager._tools` 不存在，改用 `await mcp.list_tools()`

## 2026-07-30 — 项目基础设施

### 新增
- `config.py`：`SECURITY_MODE`、`COMMAND_WHITELIST/BLACKLIST`、`DEFAULT_TIMEOUT`、`FORCE_SHELL`、`RESULT_FIELDS`
- `models.py`：`ExecResult` dataclass，`to_dict()` 字段过滤
- `executors/base.py`：`BaseExecutor` 抽象基类
- `executors/local.py`：`LocalExecutor`，`asyncio.create_subprocess_shell` 异步执行
- `main.py`：`execute_local` MCP 工具，安全校验、Shell 检测、单例进程检测
- 测试：`test_config.py`（8）、`test_models.py`（5）、`test_executor.py`（5）、`test_security.py`（11）

### 修复
- **monkeypatch 穿透**：`from config import X` → `import config` + `config.X`
- **Windows 单引号**：测试命令统一用双引号
- **单例机制**：从锁文件 → 进程检测（`_count_instances()`），无锁文件残留