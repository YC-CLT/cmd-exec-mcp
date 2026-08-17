# AGENTS.md

## 环境

- Python 3.11，uv 管理依赖
- config.py 集中配置所有常量，pyproject.toml 管理依赖
- **命令**：用 `cmd-exec-mcp`

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
| `executors/session.py` | SessionManager + ProcessSession 会话管理 |
| `models.py` | ExecResult 数据模型 |
| `tests/` | 测试目录 |

## 关键常量

| 常量 | 位置 | 说明 |
|------|------|------|
| `SECURITY_MODE` | config.py | 安全模式 restricted/full |
| `COMMAND_WHITELIST` / `BLACKLIST` | config.py | 本地/远程命令黑白名单 |
| `SANDBOX_BACKEND` | config.py | 沙箱后端 docker/opensandbox |
| `SANDBOX_SECURITY_MODE` | config.py | 沙箱安全模式（仅 Docker 后端） |
| `SANDBOX_COMMAND_WHITELIST` / `BLACKLIST` | config.py | 沙箱命令黑白名单 |
| `SANDBOX_DEFAULT_IMAGE` | config.py | Docker 沙箱默认镜像 |
| `SANDBOX_OPEN_*` | config.py | OpenSandbox 连接配置组 |
| `DEFAULT_TIMEOUT` | config.py | 默认超时 30s，-1 无限 |
| `FORCE_SHELL` | config.py | 强制指定 Shell pwsh/cmd/bash/wsl |
| `SSH_CONFIG_MODE` | config.py | SSH 配置 standard/custom |
| `SSH_PERSISTENT` | config.py | SSH 长连接复用 |
| `WSL_DISTRO` / `WSL_USER` | config.py | WSL 发行版/用户名 |
| `OUTPUT_TRUNCATE_LENGTH` | config.py | output_file 截断长度 |
| `SESSION_DEFAULT_ALIVE_TIMEOUT` | config.py | session 默认 alive 超时 |
| `SESSION_MAX_OUTPUT_LINES` | config.py | session 输出最大行数 |
| `SESSION_MAX_OUTPUT_BYTES` | config.py | session 输出最大字节 |

## 规则

- **monkeypatch 必须用 `import config` + `config.X`**：`from config import X` 创建本地副本，monkeypatch 无法穿透；executor 同理 patch `executors.模块名.X`
- **executor 签名变更需全链同步**：方法签名变，main.py 工具、测试、同接口其他 executor 都改
- **config 重命名全量 grep**：常量改名/移除后搜索所有引用
- **跨 Task 依赖等待**：并行派发时先检查上游产物是否存在

## 查文献指南

| 资源 | 路径 |
|------|------|
| 项目设计文档 | `docs/superpowers/specs/` |
| 项目实现计划 | `docs/superpowers/plans/` |
| OpenSandbox 文档 | `docs/opensandbox/`（api/configuration/pysdk/server/调查报告） |
| OpenSandbox 官方 | `open-sandbox.ai/sdks/code-interpreter/python` |

## 工具/MCP

- **wet-mcp**：`search`/`extract`/`media`/`help`/`config`，`extract` 参数名是 `urls`（数组），详见 `mcp_tools_summary.csv`
- **cmd-exec-mcp Skill**：`skills/cmd-exec-mcp/SKILL.md`，Agent 调用指南（工具选择、参数速查、常见错误）

## 工作流

0. 读AGENTS.md
1. 构想：调用 brainstorming → 产出 `docs/superpowers/specs/<date>-design.md`
2. 计划：调用 writing-plans → 产出 `docs/superpowers/plans/<date>-plan.md`
3. 发派：调用 dispatching-parallel-agents 产出给n号机（目前只有1，2号机）的提示词 `docs/superpowers/subprompts/<date>-plan-subprompt-n.md` ，用于手动发派（当前环境是win且不支持子代理，无法自动 dispatch），创建`docs/superpowers/subprompts/<date>-plan-process.md` 用于记录进度，防止冲突
4. 实施：调用 executing-plans
   - 先隔离，使用git创建新的dev分支（1号机）或者进入已有分支（2号机）  
   - 遇到 bug 自动触发 systematic-debugging（先找根因再修）
   - 写代码自动触发 test-driven-development（先写测试再实现）
5. 验证：调用 verification-before-completion → 跑验证命令确认完成
6. 记录：调用 writing-agents → 写CHANGELOG.md + 经验教训到AGENTS.md
7. 提交：调用 finishing-a-development-branch → 分组提交

## 经验/坑点

- **WebFetch 无法使用**：用 `wet-mcp extract`
- **Temp 目录不可读，MCP 输出无结构化**：Read 工具无法访问 `D:\Temp`，长输出需 Copy-Item 到项目根目录后用正则替换 `\\n` 为 `\n`
- **uv sync 会清 dev 依赖**：`uv sync` 只同步 `[project.dependencies]`，依赖变更后使用 `uv pip install -e ".[dev]"` 保留 dev 依赖
- **Windows shell 单引号陷阱**：cmd.exe 不认单引号，跨平台测试命令一律用双引号
- **subprocess 三大坑**：① `env=` 替换整个环境，先 `os.environ.copy()` 再 `.update()`；② `shell=True` + `cmd /c` 双层引号转义断裂；③ `timeout=` 只杀父进程，用 `Popen` + `taskkill /F /T /PID`
- **Windows 管道句柄继承**：`asyncio.create_subprocess_shell` 管道可被孙子进程继承，改用 `loop.run_in_executor` + `subprocess.run(stdin=DEVNULL, capture_output=True)`
- **OpenSandbox entrypoint 陷阱**：默认 entrypoint 不执行 `code-interpreter.sh`，Python 等运行时不在 PATH。必须显式传 `entrypoint=["/opt/code-interpreter/code-interpreter.sh"]` + env 版本变量
- **OpenSandbox env 注入优于命令前缀**：镜像源等环境变量通过 `Sandbox.create(env=...)` 注入，比 Docker 后端 `--entrypoint` 方案更干净
- **OpenSandbox 超时**：`Sandbox.create()` 的 timeout 接受 `timedelta` 或 `None`，`-1` 需转为 `None`
- **sys.modules mock 对已导入模块无效**：用 `monkeypatch.setattr(executor_module, "ClassName", mock_cls)` 直接打补丁
- **fastmcp 3.x API 内部属性不可用**：`mcp._tool_manager._tools` 不存在，用 `await mcp.list_tools()`
- **plan 中的 API 可能不存在**：plan 引用的 API 在实际库中可能不同名，实现时以实际库文档为准
- **asyncssh.connect 原生支持 ssh_config**：`asyncssh.connect(host=alias, config=[~/.ssh/config])` 直接读取 Host 别名
- **RemoteExecutor 长连接模式**：`SSH_PERSISTENT=True` 时检查 `is_closed()` 决定复用/重连，非持久模式 `finally` 中 close
- **wsl.exe 管道 UTF-16LE 乱码**：`wsl` 直接管道输出是 UTF-16LE，用 `--shell-type standard` 替代 `-lc`（login shell）可解决，且速度更快
- **pwsh 冷启动 ~2s 是因为 profile**：`-NoProfile` 跳过模块加载（posh-git/oh-my-posh 等），降到 0.5s；`-NonInteractive` 关闭交互提示；`$PSStyle.OutputRendering = 'PlainText'` 去 ANSI
- **WSL 用 `--shell-type standard` 不用 `-lc`**：`-lc`（login shell）触发 profile 加载，慢且编码乱；`--shell-type standard` + `-c` 干净快速
- **output_file 路径由 AI 控制**：传绝对路径如 `D:/project/out.txt`，不依赖 MCP 进程的 cwd；文件名 basename 消毒防路径穿越
- **env 穿透审计四件套**：① `os.environ.copy()` 后 `pop("VIRTUAL_ENV")` 防 venv 泄漏；② PATH 中 strip `sys.prefix` 防 `uv run` 解析到错误 python；③ `env` 参数必须传到子进程；④ Docker/SSH 隔离执行器不继承父进程环境
- **Session `_read_loop` 顺序读 stdout/stderr 会提前退出**：逐个 `readline` 时 stderr 返回空串被误判为 EOF，应用 `asyncio.create_task` 并行读或 `select` 多路复用
- **`_cleanup` 终止进程后必须设 `exit_code`**：watchdog 超时调用 `_cleanup` 后 `exit_code` 仍为 None 导致 `is_running` 仍为 True，`terminate()` 后应 `poll()` 或设 `-1`
- **Mock `poll()` 需优先检查 `returncode`**：`FakeProcess.poll()` 应先检查 `returncode` 再查内部状态，否则 `terminate()` 后仍返回旧值
- **`_build_docker_cmd(image)` 是必传位置参数**：不能误传 `env` 代替，签名是 `(command, image, mount, cwd)`
- **FastMCP 必填参数拦截在函数体之前**：`session_id` 短路逻辑无法救 `command`/`cwd` 等必填参数缺失。方案：Schema 层给默认值（`str = ""`），运行时在短路之后做校验（`if not cwd: raise`），保留设计意图。
- **`_write_loop` 写入 pipe 前必须编码**：`proc.stdin.write()` 需要 `bytes`，字符串直接写入报 `TypeError`。用 `data.encode() if isinstance(data, str) else data` 统一处理。
- **Windows pipe 关闭与进程退出有时间差**：`shell=True` 下 `readline()` 返回 EOF 时进程可能尚未"死透"，`poll()` 返回 `None`。修复：`poll()` 返回 `None` 时 `sleep(0.1)` 后重试。
- **并发 I/O 代码必须加诊断日志**：`_read_loop` 无日志时无法判断是管道阻塞、线程池异常还是 gather 未完成。日志应覆盖：启动、每个 task 的 EOF/异常、gather 结果、exit_code。
