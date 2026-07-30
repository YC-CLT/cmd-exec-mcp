# AGENTS.md

## 环境

- uv环境，py3.11
- 所有命令前加 `;`，不用 `cmd /c`

## 关键文件

## 规则

- **禁止使用 RunCommand**：命令行工具故障，AI 无法看到返回。所有命令以代码块形式输出，让用户手动复制执行
- 命令行只能执行，看不到返回，需验证时通知用户手动输入
- 文本替换用 pwsh 正则：`(Get-Content file) -replace 'a','b' | Set-Content file`
- WebFetch 只能搜索不能提取正文，提取网页用 `wet-mcp extract`
- MCP 输出过长时：`; Copy-Item` 到根目录再 `\\n`→`\n` 还原换行

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
- **uv pip install 环境差异**：实际安装的 fastmcp 版本为 3.4.5（非 plan 中写的 0.1.0），pytest 版本为 9.1.1（非 8.0.0），plan 中的版本约束 `>=` 是正确的，实际安装以最新兼容版本为准
- **monkeypatch 与模块级 import**：`from config import SECURITY_MODE` 会在函数模块创建值的本地副本，`monkeypatch.setattr(config, "SECURITY_MODE", ...)` 无法穿透。必须用 `import config` + `config.SECURITY_MODE` 让函数在运行时动态读取模块属性
- **Windows shell 单引号陷阱**：`asyncio.create_subprocess_shell` 在 Windows 默认走 cmd.exe，单引号 `'...'` 被当作字面字符而非字符串定界符。跨平台测试命令一律用双引号 `"..."` 包裹 Python -c 参数
- **Python 3.13 asyncio proactor warning**：`PytestUnraisableExceptionWarning: ProactorBasePipeTransport.__del__` 是 Python 3.13 Windows 的已知 asyncio bug，不影响测试结果，可安全忽略