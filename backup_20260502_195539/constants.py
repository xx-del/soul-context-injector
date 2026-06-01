"""
Soul Context Injector - 常量定义

所有常量集中管理，支持从 config.yaml 读取配置
"""

import logging
import yaml
from pathlib import Path

# ============ 读取配置 ============
def load_plugin_config():
    """从 config.yaml 读取插件配置"""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            plugin_config = config.get('plugins', {}).get('soul-context-injector', {})
            return plugin_config
    except Exception as e:
        logging.getLogger("soul-context-injector").warning(f"读取配置失败: {e}，使用默认值")
        return {}

_plugin_config = load_plugin_config()

# ============ 配置常量（从 config.yaml 读取） ============
OLLAMA_URL = _plugin_config.get('ollama_url', "http://localhost:11434/api/generate")
DEFAULT_MODEL = _plugin_config.get('ollama_model', "qwen2.5:7b")
TIMEOUT_MS = _plugin_config.get('timeout_ms', 15000)
MAX_RETRIES = 3

# ============ 路径常量 ============
PLUGIN_DIR = Path(__file__).parent
RULES_DIR = PLUGIN_DIR / "rules"
RULES_INDEX_PATH = RULES_DIR / "index.json"
VIOLATIONS_LOG = Path.home() / ".hermes" / "logs" / "soul-violations.log"
EXECUTION_AUTH_FILE = Path.home() / ".hermes" / ".soul_execution_auth"

# ============ 日志 ============
logger = logging.getLogger("soul-context-injector")


# ============ 拦截常量 ============

# 破坏性命令 - 永久禁止（系统级破坏，无法恢复）
# 注意：实际检测逻辑已迁移到 interceptor.py 的 is_dangerous_command() 函数
# 此处保留常量定义用于文档说明和未来扩展
DANGEROUS_PATTERNS = [
    # 检测逻辑已由 interceptor.py 中的正则表达式实现
    # 包括：远程代码执行攻击、磁盘破坏、系统文件破坏、根目录破坏等
]

# 增删改命令 - 需要执行认证
WRITE_PATTERNS = [
    # 文件操作
    "rm ", "rm -", "mv ", "cp ", "mkdir ", "touch ", "rmdir ",
    "ln ", "truncate", "unlink", "tee ",
    
    # 打包解压
    "tar ", "unzip ", "gzip ", "gunzip ", "zip ",
    "xz ", "bzip2 ", "7z ",
    
    # 下载写入
    "curl -o", "curl -O", "wget -o", "wget -O",
    "scp ", "rsync ",
    
    # Git 操作
    "git push", "git commit", "git add",
    "git rm", "git mv", "git reset",
    
    # 包管理
    "pip install", "pip uninstall",
    "npm install", "npm uninstall", "npm update",
    "yarn add", "yarn remove",
    "apt install", "apt remove", "apt purge",
    "dnf install", "dnf remove",
    "yum install", "yum remove",
    "pacman -S", "pacman -R",
    "brew install", "brew uninstall",
    
    # 系统服务
    "systemctl start", "systemctl stop", "systemctl restart",
    "systemctl enable", "systemctl disable",
    "service start", "service stop", "service restart",
    "docker run", "docker rm", "docker stop", "docker rmi",
    "docker-compose up", "docker-compose down",
    
    # 权限修改
    "chmod ", "chown ",
    
    # 配置修改
    "crontab", "sysctl -w",
]

# 增删改工具 - 需要执行认证
WRITE_TOOLS = {"write_file", "patch"}

# 规划性文件（L3 阶段允许写入，不触发认证）
PLANNING_FILES = [
    'execution_plan.md',
    'task_plan.md',
    'findings.md',
    'progress.md',
    '*方案*.md',
    '*规划*.md',
    '*计划*.md'
]

# 技能绑定映射
SKILL_BINDINGS = {
    "L2": ["deep-thinking"],
    "L3": ["deep-thinking", "openclaw-behavior-plan"],
    "L4": ["planning-with-files", "agent-pool"],
}

# 技能白名单 - 白名单内技能执行的所有操作跳过认证
SKILL_WHITELIST = _plugin_config.get(
    'skill_whitelist',
    ["workflow-manager", "agent-pool", "planning-with-files"]
)

# 确认词 - 用户确认执行方案
# 注意："执行"已恢复，通过analyzer.py的上下文判断区分语义（确认方案 vs 执行新任务）
CONFIRM_KEYWORDS = ["是", "同意", "确认", "确认执行", "执行", "开始吧", "好的", "可以", "没问题", "approve", "confirm", "yes", "ok"]
