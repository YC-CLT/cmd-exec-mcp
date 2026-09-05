import os

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
DEFAULT_TIMEOUT = 30

# 强制指定的 Shell 类型: None 表示自动检测（Win→cmd, Linux→bash），"pwsh" | "bash" | "cmd" 等
FORCE_SHELL = None

# WSL 配置（shell="wsl" 时生效）
WSL_DISTRO = "kali-linux"
WSL_USER = "kali"

# 返回字段配置，true 表示包含该字段
RESULT_FIELDS = {
    "stdout": True,
    "stderr": True,
    "exit_code": True,
    "duration": True,
    "is_timeout": True,
    "command_echo": True,
    "output_file": True,
}

# 日志
LOG_FILE = "log.txt"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 输出截断（output_file 参数时，stdout 返回前 N 字符，完整内容落盘）
OUTPUT_TRUNCATE_LENGTH = 8000

# 沙箱后端: "docker" | "opensandbox"
SANDBOX_BACKEND = "opensandbox"

# 安全配置（仅纯Docker生效）
SANDBOX_SECURITY_MODE = "full"  # 默认完全模式，容器内随便跑
SANDBOX_COMMAND_LIST_MODE = "blacklist"
SANDBOX_COMMAND_WHITELIST = []
SANDBOX_COMMAND_BLACKLIST = ["docker", "mount", "fdisk"]

# 默认镜像（仅纯Docker生效）
SANDBOX_DEFAULT_IMAGE = "opensandbox/code-interpreter:v1.1.0"

# 挂载目录: None 表示不挂载，调用方可传入 "host_path:container_path"（仅纯Docker生效）
SANDBOX_DEFAULT_MOUNT = None

# 纯Docke沙箱启动命令前缀：换源 + python alias（bash -lc 执行前拼接）（仅纯Docker生效）
SANDBOX_DOCKER_PREFIX = (
    "export PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/; "
    "export NPM_CONFIG_REGISTRY=https://registry.npmmirror.com; "
    "export GOPROXY=https://goproxy.cn,direct; "
    "ln -sf $HOME/.local/bin/python3.14 $HOME/.local/bin/python 2>/dev/null; "
    "ln -sf /opt/python/versions/cpython-3.14-linux-x86_64-gnu/bin/pip3.14 $HOME/.local/bin/pip 2>/dev/null; "
)

# OpenSandbox 后端配置
SANDBOX_OPEN_TEMPLATE = "ctf-sandbox"
SANDBOX_OPEN_SERVER_HOST = "localhost"
SANDBOX_OPEN_SERVER_PORT = 8080
SANDBOX_OPEN_API_KEY = "cmd-exec-mcp-dev"  # 生产环境必填，本地开发也建议占个位

# OpenSandbox server 配置文件路径，默认项目根目录，不存在则回退 ~/.sandbox.toml
SANDBOX_CONFIG_PATH = os.path.join(os.path.dirname(__file__), ".sandbox.toml")

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

# OpenSandbox Server 懒加载 + 空闲超时
SANDBOX_OPEN_SERVER_STARTUP_TIMEOUT = 15   # 启动后等待就绪的最长秒数
SANDBOX_OPEN_SERVER_IDLE_TIMEOUT = 600     # 无请求空闲多久后自动关闭秒数，-1 永不关闭

# OpenSandbox 命令前缀（备用，正常情况下 entrypoint 已设置 PATH）
SANDBOX_OPEN_PREFIX = ""

# SSH 远程执行配置
SSH_DEFAULT_TARGET = "admin@192.168.2.1:22"    # 默认 SSH 目标，格式: [user@]host[:port]
SSH_DEFAULT_USER = "admin"      # 默认 SSH 用户名
SSH_DEFAULT_PORT = 22          # 默认 SSH 端口
SSH_DEFAULT_KEY = None       # 默认 SSH 密钥路径或密码字符串
SSH_DEFAULT_NO_KNOWN_HOSTS = False  # 默认是否跳过 known_hosts 校验
SSH_PERSISTENT = True          # 长连接复用
SSH_CONNECTION_TIMEOUT = 10    # SSH 连接超时秒数

# Session Detach 配置
SESSION_DEFAULT_ALIVE_TIMEOUT = 300
SESSION_MAX_OUTPUT_LINES = 10000
SESSION_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10MB