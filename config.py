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

# 沙箱模式安全配置（独立于本地模式）
SANDBOX_SECURITY_MODE = "full"  # 默认完全模式，容器内随便跑
SANDBOX_COMMAND_WHITELIST = []
SANDBOX_COMMAND_BLACKLIST = ["docker", "mount", "fdisk"]

# Docker 镜像，默认 ubuntu，调用方可覆盖
SANDBOX_DEFAULT_IMAGE = "ubuntu"

# 挂载目录: None 表示不挂载，调用方可传入 "host_path:container_path"
SANDBOX_DEFAULT_MOUNT = None

# 日志
LOG_FILE = "log.txt"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"