# 安全模式: "restricted" | "full"
SECURITY_MODE = "restricted"

# 列表模式: "whitelist" | "blacklist"
#   whitelist: 仅白名单命令可执行（黑名单仍然拦截）
#   blacklist: 仅黑名单命令被拦截，其余放行
COMMAND_LIST_MODE = "blacklist"

# 白名单/黑名单（仅在 restricted 模式下生效）
COMMAND_WHITELIST = ["ls", "dir", "git", "python", "echo", "cat", "type", "pwd", "cd"]
COMMAND_BLACKLIST = ["rm", "del", "shutdown", "reboot", "format", "dd"]

# 默认超时（秒），-1 表示无超时限制，调用方可覆盖
DEFAULT_TIMEOUT = -1

# 工作目录: None 表示项目根目录，受限模式下强制忽略调用方传入的 cwd
DEFAULT_CWD = None

# 强制指定的 Shell 类型: None 表示自动检测（Win→cmd, Linux→bash），"pwsh" | "bash" | "cmd" 等
FORCE_SHELL = None

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
SANDBOX_COMMAND_LIST_MODE = "blacklist"
SANDBOX_COMMAND_WHITELIST = []
SANDBOX_COMMAND_BLACKLIST = ["docker", "mount", "fdisk"]

# Docker 镜像，默认 ubuntu，调用方可覆盖
SANDBOX_DEFAULT_IMAGE = "opensandbox/code-interpreter:v1.1.0"

# 挂载目录: None 表示不挂载，调用方可传入 "host_path:container_path"
SANDBOX_DEFAULT_MOUNT = None

# Docker 沙箱命令前缀：换源 + python alias（bash -lc 执行前拼接）
SANDBOX_DOCKER_PREFIX = (
    "export PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/; "
    "export NPM_CONFIG_REGISTRY=https://registry.npmmirror.com; "
    "export GOPROXY=https://goproxy.cn,direct; "
    "ln -sf $HOME/.local/bin/python3.14 $HOME/.local/bin/python 2>/dev/null; "
    "ln -sf /opt/python/versions/cpython-3.14-linux-x86_64-gnu/bin/pip3.14 $HOME/.local/bin/pip 2>/dev/null; "
)

# 沙箱后端: "docker" | "opensandbox"
SANDBOX_BACKEND = "opensandbox"

# OpenSandbox 后端配置
SANDBOX_OPEN_TEMPLATE = "opensandbox/code-interpreter:v1.1.0"
SANDBOX_OPEN_SERVER_HOST = "localhost"
SANDBOX_OPEN_SERVER_PORT = 8080
SANDBOX_OPEN_API_KEY = "cmd-exec-mcp-dev"  # 生产环境必填，本地开发可留空

# SSH 远程执行配置
SSH_CONFIG_MODE = "standard"  # "standard" | "custom"
SSH_HOST_NAME = "rpig"        # standard 模式下指定 Host 别名
SSH_PERSISTENT = True        # 长连接复用
SSH_CONNECTION_TIMEOUT = 10   # SSH 连接超时秒数

# 日志
LOG_FILE = "log.txt"
LOG_LEVEL = "INFO"

# OpenSandbox 入口脚本（code-interpreter.sh 负责初始化 PATH 和运行时环境）
SANDBOX_OPEN_ENTRYPOINT = ["/opt/code-interpreter/code-interpreter.sh"]

# OpenSandbox 运行时版本（传给 code-interpreter.sh 的环境变量）
SANDBOX_OPEN_RUNTIME_ENV = {
    "PYTHON_VERSION": "3.11",
    "JAVA_VERSION": "17",
    "NODE_VERSION": "20",
    "GO_VERSION": "1.24",
    # 国内镜像加速
    "PIP_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/",
    "NPM_CONFIG_REGISTRY": "https://registry.npmmirror.com",
    "GOPROXY": "https://goproxy.cn,direct",
}

# OpenSandbox 命令前缀（备用，正常情况下 entrypoint 已设置 PATH）
SANDBOX_OPEN_PREFIX = ""

# 日志
LOG_FILE = "log.txt"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"