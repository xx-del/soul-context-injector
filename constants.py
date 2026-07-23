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
# EXECUTION_AUTH_FILE 已废弃 - session 追踪机制不可靠（v5.9.0 移除）

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

# 输出类工具 - 需要技能调用检查
OUTPUT_TOOLS = {
    "send_message",      # Telegram/Discord/Slack 消息
    "text_to_speech",    # 语音输出
    "execute_code",      # Python 代码执行（可能输出结果）
    "terminal",          # 终端命令（可能输出结果）
}

# 技能绑定映射
SKILL_BINDINGS = {
    "W": ["workflow-manager"],  # 工作流任务 - 硬编码绑定
    "L2": ["deep-thinking"],
    "L3": ["deep-thinking", "openclaw-behavior-plan"],
    "L4": ["planning-with-files", "agent-pool"],
}

# 技能白名单 - 白名单内技能执行的所有操作跳过认证
# 支持三种模式:
#   "all"     → 所有已安装技能（默认）
#   false     → 关闭白名单
#   [列表]    → 只指定这些技能
SKILL_WHITELIST_RAW = _plugin_config.get(
    'skill_whitelist',
    'all'
)

# 解析白名单模式
SKILL_WHITELIST_MODE = None  # 'all', 'list', 'disabled'
SKILL_WHITELIST = []         # list 模式下的具体技能列表

if isinstance(SKILL_WHITELIST_RAW, str) and SKILL_WHITELIST_RAW.lower() == 'all':
    SKILL_WHITELIST_MODE = 'all'
elif SKILL_WHITELIST_RAW is False or SKILL_WHITELIST_RAW == 'disabled':
    SKILL_WHITELIST_MODE = 'disabled'
elif isinstance(SKILL_WHITELIST_RAW, list):
    SKILL_WHITELIST_MODE = 'list'
    SKILL_WHITELIST = SKILL_WHITELIST_RAW
else:
    # 回退默认
    SKILL_WHITELIST_MODE = 'all'

# 确认词 - 用户确认执行方案
# 注意："执行"已恢复，通过analyzer.py的上下文判断区分语义（确认方案 vs 执行新任务）
CONFIRM_KEYWORDS = [
    "是", "同意", "确认", "执行", "好的", "可以", "没问题",
    "开始吧", "执行吧", "确认执行", "同意执行",
    "ok", "OK", "yes", "Yes", "approve", "confirm",
    "好", "嗯", "需要"
]

# ============================================================================
# L4 强制执行常量（v3.0 - 2026-05-14）
# ============================================================================

# 执行方式类型
EXECUTION_TYPES = {
    "DELEGATE_TASK": "delegate_task",
    "AGENT_POOL_CLIENT": "agent_pool_client",
    "ORCHESTRATOR": "orchestrator",
    "TERMINAL_EXECUTION": "terminal_execution",
    "PYTHON_API": "python_api",
}

# L4 任务必须技能
REQUIRED_SKILLS_L4 = [
    "planning-with-files",
    "agent-pool",
]

# 最大拦截次数（逃生舱阈值）
MAX_ESCAPE_ATTEMPTS = 7  # Increased from 3 to prevent quick bypass

# 执行超时（秒）
EXECUTION_TIMEOUT_SECONDS = 600  # 10 分钟

# 追踪文件 TTL（秒）
TRACKER_TTL_SECONDS = 86400  # 24 小时

# 终端检测正则
TERMINAL_DETECTION_PATTERNS = [
    r'agent_pool_client\.execute\(',
    r'Orchestrator\([^)]*\)\.batch_execute',
    r'python\s+-c\s+.*agent_pool',
    r'python\s+.*agent_pool_client\.py',
]

# 敏感信息检测正则（phase_info 清理）
SENSITIVE_PATTERNS = [
    r'password["\']?\s*[:=]\s*["\']?[^\s"\']+',
    r'token["\']?\s*[:=]\s*["\']?[^\s"\']+',
    r'secret["\']?\s*[:=]\s*["\']?[^\s"\']+',
    r'api_key["\']?\s*[:=]\s*["\']?[^\s"\']+',
]

# phase_info 最大长度
PHASE_INFO_MAX_LENGTH = 200
