# CHANGELOG

## 2026-08-05 — 非交互执行文档 + 配置同步

### 文档

- README 新增「非交互执行」小节（中英文）：说明 `stdin=DEVNULL` 行为，列出 `apt -y`、`sudo -n` 等常用非交互 flag
- 工具参数表 shell 选项补 `"wsl"`（5 处），配置表补 `WSL_DISTRO`、`WSL_USER`
- AGENTS.md：`DEFAULT_TIMEOUT` 描述修正，新增外部依赖同步坑点

## 2026-08-05 — 双语 README + LICENSE + 文档同步

### 文档

- README 新增完整英文版，顶部 `[English](#english) | [中文](#chinese)` 语言切换
- 新增 MIT `LICENSE` 文件
- `pyproject.toml`：补充 `license = "MIT"`、`asyncssh>=2.0.0`、`python-dotenv>=1.0.0` 依赖声明
- README 配置表同步 config.py：修正 4 个默认值不一致，补充 6 个遗漏配置项（`SANDBOX_COMMAND_WHITELIST`、`SANDBOX_DEFAULT_MOUNT`、`SANDBOX_DOCKER_PREFIX`、`OUTPUT_TRUNCATE_LENGTH`、`RESULT_FIELDS`、`LOG_LEVEL`）
- 工具参数表 `timeout` 默认值 `-1` → `30`（对齐 `DEFAULT_TIMEOUT`）
- 精简冗余测试命令 `uv pip install -e ".[dev]"`（`uv sync` 已覆盖）

## 2026-08-05 — WSL shell + pwsh 优化 + output_file 落盘

### 新增：shell="wsl" 选项

- `wrap_command` 添加 `wsl` 分支：`wsl -d <distro> -u <user> --shell-type standard -- bash -c`
- `config.py`：`WSL_DISTRO="kali-linux"`, `WSL_USER="kali"` 可配置
- 单命令 0.25s，4 并发 0.19~0.29s

### 新增：output_file 长输出落盘

- `_handle_output_file` helper：stdout 超过 `OUTPUT_TRUNCATE_LENGTH(2000)` 截断预览，完整内容落盘
- 三个工具统一加 `output_file` 参数，AI 传绝对路径精确控制
- 文件名 basename 消毒防路径穿越

### 优化：pwsh 启动提速

- `-NoProfile`（跳过 profile 加载，2.1s→0.5s）
- `-NonInteractive`（关闭交互提示）
- `$PSStyle.OutputRendering = 'PlainText'`（去 ANSI 转义码）
- `[console]::OutputEncoding = UTF8Encoding`（UTF-8 输出）

### 测试

- 55/55 passed

## 2026-08-05 — cwd 必填 + 安全统一 + describe 精简

### 变更：cwd 必填 + 移除 DEFAULT_CWD

- `execute_local` 的 `cwd` 参数改为必填（无默认值），调用方必须显式传入工作目录
- 移除 `config.DEFAULT_CWD` 和 `resolve_cwd()` 函数
- restricted/full 模式只控黑白名单，不再控 cwd

### 安全统一：execute_remote 复用本地安全校验

- `execute_remote` 调用 `validate_command()`，复用 `SECURITY_MODE` + `COMMAND_LIST_MODE` 黑白名单
- 移除独立的 `REMOTE_SECURITY_MODE`，远程和本地共享同一套安全策略

### 优化：MCP 工具 describe 精简

- `execute_sandbox` / `execute_remote` 描述复用 `execute_local` 的通用参数说明
- 各自只标注差异：安全模式、后端选择、SSH 配置方式

### 测试

- 全量 54/54 passed（移除 DEFAULT_CWD 测试）

## 2026-08-05 — execute_remote SSH 远程执行

### 新增

- `executors/remote.py`：`RemoteExecutor` 继承 `BaseExecutor`
  - `_connect()`：`standard` 模式用 `asyncssh.connect(host=SSH_HOST_NAME, config=[~/.ssh/config])`，`custom` 模式读 `.env`
  - `_get_connection()`：`SSH_PERSISTENT` 长连接复用
  - `execute()`：asyncssh 异步执行，超时捕获 `asyncio.TimeoutError`
  - `execute_batch()`：`asyncio.gather` 并发（复用同一 TCP 连接，每个命令独立 SSH channel）
- `main.py`：注册 `execute_remote` MCP 工具，5 参数签名 `(command, timeout, env, parallel, fields)`
- `config.py`：新增 `SSH_HOST_NAME`（standard 模式指定 Host 别名）

### 测试

- `tests/test_remote_executor.py`：9 个 Mock asyncssh 测试
- `tests/test_config.py`：追加 3 个 SSH 配置断言
- 全量 55/55 passed

### 实测验证

- 目标 rpig（树莓派 aarch64 Debian）：`whoami` / `uname -a` / `python3 -V` / `docker ps` 全部通过
- 并发 batch：4 命令 0.45s，复用同一 TCP 连接

### 修复记录

- **asyncssh.read_config 不存在**：asyncssh 2.24.0 无此 API，改用 `asyncssh.connect(host=SSH_HOST_NAME, config=[~/.ssh/config])` 原生支持
- **remote.py 模块级 import 副本**：`from config import SSH_CONFIG_MODE` 在 remote.py 创建本地值，monkeypatch `config.SSH_CONFIG_MODE` 不穿透。需 patch `executors.remote.SSH_CONFIG_MODE` 直接模块属性

## 2026-08-05 — OpenSandbox 环境修复 + 换源

### 修复：OpenSandbox Python 不可用

- **根因**：`Sandbox.create()` 默认 `entrypoint=["tail", "-f", "/dev/null"]`，跳过了 `code-interpreter.sh` 环境初始化脚本，导致 Python 不在 PATH
- **修复**：设置 `entrypoint=["/opt/code-interpreter/code-interpreter.sh"]`，传入 `PYTHON_VERSION`/`JAVA_VERSION`/`NODE_VERSION`/`GO_VERSION` 环境变量
- 来源：官方文档 `https://open-sandbox.ai/sdks/code-interpreter/python`

### 新增：OpenSandbox 国内镜像加速

- `SANDBOX_OPEN_RUNTIME_ENV` 追加 `PIP_INDEX_URL`（阿里云）、`NPM_CONFIG_REGISTRY`（npmmirror）、`GOPROXY`（goproxy.cn）
- 通过 `Sandbox.create(env=...)` 注入容器，比 Docker 后端的命令前缀更干净

### 验证

- MCP 实测：`python -V` / `node -v` / `go version` 全部通过
- `pip install requests --break-system-packages` 成功（PEP 668 uv 管理环境）
- 全量 43/43 passed

## 2026-08-04 — MCP 功能测试 + 解析/超时修复

### 修复：wrap_command cmd 双层包装

- `wrap_command` 对 cmd 模式做了 `cmd /c "..."` 包装，但 `subprocess.run(shell=True)` 已走 cmd.exe
- 导致 `python -c "exit(1)"` 被双层转义变成语法错误，exit_code 误报 0
- 修复：cmd 模式下直接返回原始命令，不再包装

### 修复：env 参数全覆盖

- `LocalExecutor` 把 `env` 直接传给 `subprocess.run(env=env)`，替换整个环境导致 PATH 丢失
- 修复：先 `os.environ.copy()` 再 `merged_env.update(env)`

### 修复：Sandbox 管道句柄继承

- `SandboxExecutor` 使用 `asyncio.create_subprocess_shell`，Docker 容器继承管道句柄导致 `communicate()` 卡死
- 修复：对齐 `LocalExecutor`，改用 `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`

### 修复：超时进程树 kill

- `subprocess.run(timeout=N)` 在 Windows 上只杀 cmd.exe，子进程（ping.exe）残留
- 修复：`Popen` + `communicate(timeout=...)`，超时时 `taskkill /F /T /PID` 杀进程树
- 效果：`ping -n 10` timeout=2s，耗时从 9.2s → 2.2s

### 测试

- 全量 43/43 passed
- MCP 验证：`execute_local` 基本命令/并行/env/fields 过滤/超时 均通过
- MCP 验证：`execute_sandbox` Docker 沙箱 `whoami && uname -a` 通过

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

## 2026-08-05 — SSH 远程执行前置配置

### 新增

- `config.py` 追加 `SSH_CONFIG_MODE`、`SSH_PERSISTENT`、`SSH_CONNECTION_TIMEOUT`
- `.env.example`（SSH_HOST/SSH_PORT/SSH_USER/SSH_KEY_PATH/SSH_PASSWORD/SSH_KNOWN_HOSTS）
- `pyproject.toml` 追加 `asyncssh>=2.14.0`、`python-dotenv>=1.0.0`

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