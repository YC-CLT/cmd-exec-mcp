# CHANGELOG

## 2026-08-29 — SSH Remote 增强 + 统一 Session 工具

### Round 4: 加密密钥 agent 回退

- **Windows SSH agent 支持** (`executors/remote.py`)：模块加载时自动设 `SSH_AUTH_SOCK=\\.\pipe\openssh-ssh-agent`
- **加密密钥检测**：新增 `_is_encrypted_key()` 检测 `ENCRYPTED` 标记，加密密钥不传 `client_keys`，回退到 agent 认证
- **`SSH_DEFAULT_KEY`** 恢复为 `"~/.ssh/id_rsa"`（加密密钥也能用 agent 了）

### Round 3: 文档精简 + 默认密钥

- **SSH 默认密钥** (`config.py`)：`SSH_DEFAULT_KEY` 从 `None` 改为 `"~/.ssh/id_rsa"`，`_connect()` 中 `os.path.expanduser()` 跨平台展开
- **工具 docstring 精简** (`main.py`)：`execute_local`/`execute_sandbox`/`execute_sandbox_file`/`execute_remote`/`execute_remote_file`/`execute_session` 的 docstring 砍掉冗长参数列表，只保留示例
- **SKILL.md 重写** (`skills/cmd-exec-mcp/SKILL.md`)：精简 Overview/When to Use，新增执行前自检清单，合并参数表，减少重复示例

### Bugfix
- **`execute_batch` 补 `cwd` 参数**：`remote.py` 签名补 `cwd=None`，`main.py` 并行分支补 `cwd=cwd`
- **`execute_session` `is_running` 硬编码**：opensandbox 的 `list`/`status` 改为 `s.get("last_result") is None`

### Round 2: Key Auth + OpenSandbox 原生文件 API

- **SSH 密钥认证** (`executors/remote.py`)：`_connect()` 新增 `key`/`no_known_hosts` 参数；新增 `_is_key_path()` 自动区分密钥路径和密码
- **OpenSandbox 原生文件传输** (`executors/opensandbox.py`)：新增 `upload_file()`/`download_file()`，使用 execd HTTP API 直接上传/下载
- **`execute_remote` 工具**：新增 `key`、`no_known_hosts` 参数
- **`execute_remote_file` 工具**：新增 `key`、`no_known_hosts` 参数
- **`execute_sandbox_file` 工具**：改用 opensandbox executor 原生 API 上传/下载，弃用 sdk `files.read_file`/`write_file`
- **测试**：新增 `TestKeyAuth`（6 tests）、`test_session_tool.py`（12 tests）；更新 `test_opensandbox_file.py` mock 适配

### Round 1: 核心重构

- **SSH 配置重构** (`config.py`)：移除 `SSH_CONFIG_MODE`/`SSH_HOST_NAME`，新增 `SSH_DEFAULT_TARGET`/`SSH_DEFAULT_USER`/`SSH_DEFAULT_PORT`/`SSH_DEFAULT_KEY`/`SSH_DEFAULT_NO_KNOWN_HOSTS`
- **SSH 连接池** (`executors/remote.py`)：`_conns` 改为 `dict[str, SSHClientConnection]` 按 target 缓存；新增 `_parse_target()` 静态方法解析目标字符串；新增 `upload_file()`/`download_file()` SFTP 文件传输
- **Session 管理增强** (`executors/session.py`)：`SessionManager` 新增 `status()` 和 `list_all()` 方法
- **`execute_remote` 工具**：新增 `target`、`cwd` 参数，移除 `session_id`/`action`
- **`execute_remote_file` 工具** (新增)：SSH 远程文件上传/下载（SFTP）
- **`execute_session` 工具** (新增)：统一 Session 管理（list/read/send/kill/status），跨本地/远程/OpenSandbox
- **`execute_local` / `execute_sandbox`**：移除 `session_id`/`action` 参数，session 操作统一走 `execute_session`
- **`execute_sandbox_file`**：缩减为 `upload`/`download` 两种 action，移除 `read`/`write`/`list`/`delete`/`exists`/`content`
- **清理**：`mcp_tools_summary.csv` 更新 6 个工具描述
- **工具 docstring 简化**：MCP 已从签名拿到参数名/类型，docstring 只保留非显而易见的参数和 1-2 个示例

### 测试

- 全量回归：**131 passed, 8 skipped**

## 2026-08-22 — OpenSandbox Session 与文件 API 完善

### 新增

- **`OpenSandboxExecutor.create_session` 重写**：从本地 `subprocess.Popen` 改为 OpenSandbox SDK 原生 `sandbox.commands.create_session()` API，返回 `(Sandbox, str)` 元组
- **`OpenSandboxExecutor.run_in_session`**：新增方法，通过 `sandbox.commands.run_in_session()` 在已有 session 中执行命令，返回 `ExecResult`
- **`OpenSandboxExecutor.delete_session`**：新增方法，通过 `sandbox.commands.delete_session()` + `sandbox.destroy()` 清理沙箱
- **`_opensandbox_sessions` 自管字典**：`main.py` 新增 `_opensandbox_sessions` 字典 + `asyncio.Lock`，OpenSandbox 不走 `SessionManager`
- **`_opensandbox_session_create` / `_dispatch` / `_cleanup`**：自管 session 生命周期（create/send/read/kill），返回格式与 `SessionManager` 一致
- **`_watchdog_loop` / `_reset_watchdog`**：per-session watchdog，可重置超时，超时自动清理
- **`_cleanup_all_opensandbox_sessions` + atexit**：进程退出时自动清理所有 OpenSandbox session
- **`execute_sandbox` 分流**：`session_id` 和 `detach` 分支按 `SANDBOX_BACKEND` 分流到 opensandbox 自管或 SessionManager
- **`execute_sandbox_file` MCP 工具**：新增 5 种文件操作
  - `read`：读取沙箱内文件
  - `write`：写入沙箱内文件
  - `list`：列出目录内容
  - `delete`：删除文件
  - `exists`：检查文件是否存在
  - 支持 `session_id` 复用已有 sandbox，无则创建临时 sandbox

### 测试

- 新增 30 个测试（5 + 14 + 11），覆盖 executor 新方法、session 管理、文件操作
- 全量回归：100 passed, 8 skipped（Linux 专属跳过）

## 2026-08-21 — Linux 子进程树完整清理

### 修复

- **`_kill_process_tree` Linux 空实现**：Linux 分支新增 `os.killpg(os.getpgid(pid), signal.SIGKILL)` 杀整个进程组，`ProcessLookupError`/`OSError` 静默忽略
- **所有 `Popen` 加 `start_new_session=True`**：`local.py`/`sandbox.py`/`opensandbox.py` 的 `_run_with_timeout` 和 `create_session` 中 `Popen` 均加 `start_new_session=True`，建立独立进程组
- **`session.py` `_cleanup` 改用 `_kill_process_tree`**：新增模块级 `_kill_process_tree(pid)` 替代 `proc.terminate()`，`poll()` 返回 None 时兜底 `exit_code = -1`
- **`remote.py` 超时杀远程进程树**：`TimeoutError` 后通过 SSH 发 `kill -- -$(ps -o pgid= -p $$)` 杀远程进程组

## 2026-08-16 — Skill 配套文档

### 新增

- **`skills/cmd-exec-mcp/SKILL.md`**：Agent 使用指南，含工具选择决策图、参数速查、常见错误表、理性化反驳

## 2026-08-16 — OpenSandbox Server 懒加载 + 空闲超时

### 修复

- **`start_opensandbox_server()` 无就绪等待**：新增 `_wait_for_server_ready()` 轮询 `/health` 端点，15 秒超时可配 `SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT`
- **Server 崩溃不自愈**：新增 `_ensure_opensandbox_server()` 自动检测 `poll()` 并重启，替代旧的手动 flag 模式
- **无空闲超时**：新增 `_idle_watchdog_loop()` 后台任务，默认 600 秒无请求自动关闭 server，`SANDBOX_OPEN_SERVER_IDLE_TIMEOUT=-1` 永不关闭

## 2026-08-16 — Tool Description 精简 + Flaky 修复

### 修复

- **`test_watchdog_reset_on_read` flaky**：`_read_loop` 修复后 `FakeProcess` 立即 EOF 导致 `exit_code` 被设置，`is_running` 恒为 `False`。修复：`FakeProcess` 加 `never_eof` 模式，watchdog 测试用 `never_eof=True` 保持进程存活。

### 改进

- **Tool 描述精简**：`execute_sandbox`/`execute_remote` 用"同上 execute_local"复用参数说明，示例改为真实场景（git status、npm install、docker ps、systemctl status 等），去掉无意义的 echo/whoami。

## 2026-08-15 — Session Detach Bug 修复

### 修复

- **Schema 校验缺陷**：`execute_local`/`execute_sandbox`/`execute_remote` 的 `command` 参数改为可选（`str = ""`），`execute_local` 的 `cwd` 改为可选（`str = ""`），使 `session_id` + `action="read"/"kill"` 无需传假参数即可通过 FastMCP 校验。`cwd` 在运行时强制校验（非 session 路径 `if not cwd` raise），保留设计意图。
- **_read_loop 顺序读取 bug**：`session.py` 的 `_read_loop` 从顺序读 stdout/stderr 改为 `asyncio.create_task` 并发读，解决 stderr EOF 导致整循环 break 丢失 stdout 后续行 + exit_code 永不设置的问题。
- **send 写入编码 bug**：`_write_loop` 中字符串数据直接写入 `proc.stdin` 报 `TypeError: a bytes-like object is required, not 'str'`，修复为 `encoded = data.encode() if isinstance(data, str) else data`。
- **exit_code 时序 bug**：Windows `shell=True` 下 pipe 关闭与进程退出之间存在时间差，`poll()` 在纳秒级窗口内返回 `None` 但进程已退出。修复：`poll()` 返回 `None` 时 `sleep(0.1)` 后重试一次。
- **_read_loop 诊断日志**：新增 `_read_loop` 全链路日志（启动/task 创建/stdout EOF/stderr EOF/gather 完成/exit_code），便于排查 pipe 阻塞与退出时序问题。

## 2026-08-15 — Session Detach 实现

### 新增

- `config.py`：`SESSION_DEFAULT_ALIVE_TIMEOUT`(300)、`SESSION_MAX_OUTPUT_LINES`(10000)、`SESSION_MAX_OUTPUT_BYTES`(10MB) 三个配置常量
- `executors/session.py`：`SessionManager` + `ProcessSession` 核心组件，支持 create/read/send/kill 操作，watchdog 超时自动清理，atexit 兜底
- `executors/base.py`：`create_session` 抽象方法，所有 executor 实现
- `executors/local.py`：`create_session` 本地后台进程启动（env 穿透审计）
- `executors/sandbox.py`：`create_session` Docker 沙箱后台进程启动
- `executors/remote.py`：`create_session` SSH 远程后台进程启动（asyncssh `create_process`）
- `executors/opensandbox.py`：`create_session` OpenSandbox 后台进程启动
- `main.py`：`execute_local`/`execute_sandbox`/`execute_remote` 三个工具新增 `detach`/`session_id`/`action`/`alive_timeout` 参数，支持 session 路由

### 测试

- `tests/test_session_manager.py`：10 个用例（create/read/send/kill/notfound/watchdog/reset/cleanup）
- `tests/test_session_local.py`：2 个用例（create_session 返回 proc、忽略 alive_timeout）
- `tests/test_session_sandbox.py`：1 个用例（create_session 返回 proc）
- `tests/test_session_remote.py`：1 个用例（mock create_session 返回 proc）

## 2026-08-12 — 环境变量泄漏修复 + 沙箱/远程 env 穿透

### 修复

- `executors/local.py`：`os.environ.copy()` 后 `pop("VIRTUAL_ENV")` + 从 PATH 中 strip venv 的 Scripts 目录，防止 MCP 进程的 venv 泄漏到子进程（`uv run` 解析到错误 python）
- `executors/sandbox.py`：`env` 参数被静默忽略的 bug，`_run_with_timeout` 新增 `env` 参数 + `VIRTUAL_ENV` 清理
- `executors/remote.py`：`conn.run()` 未传 `env` 参数，导致用户自定义环境变量被静默忽略
- `tests/test_remote_executor.py`：mock `run()` 签名适配 `env` 参数

### 文档

- README：OpenSandbox 前置条件步骤精简，包管理器统一 `uv pip install`
- `docs/opensandbox/opensandbox调查报告.md`：新增 Code Interpreter 镜像章节，删除对 executor 无用的源码架构/Execd API 章节
- `docs/opensandbox/.sandbox.toml`：Windows 本地开发配置模板

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