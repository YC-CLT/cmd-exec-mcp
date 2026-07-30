# 安全模式: "restricted" | "full"
SECURITY_MODE = "restricted"

# 白名单/黑名单（仅在 restricted 模式下生效）
COMMAND_WHITELIST = ["ls", "dir", "git", "python", "echo", "cat", "type", "pwd", "cd"]
COMMAND_BLACKLIST = ["rm", "del", "shutdown", "reboot", "format", "dd"]

# 默认超时（秒），-1 表示无超时限制，调用方可覆盖
DEFAULT_TIMEOUT = -1

# 工作目录: None 表示项目根目录，受限模式下强制忽略调用方传入的 cwd
DEFAULT_CWD = None

# 强制指定的 Shell 类型: None 表示自动检测，"powershell" | "bash" | "cmd" 等
FORCE_SHELL = None

# 单例锁文件，防止多实例启动
SINGLETON_LOCK_FILE = "cmd-exec-mcp.lock"

# 返回字段配置，true 表示包含该字段
RESULT_FIELDS = {
    "stdout": True,
    "stderr": True,
    "exit_code": True,
    "duration": True,
    "is_timeout": True,
    "command_echo": True,
}