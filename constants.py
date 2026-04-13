"""
Soul Context Injector - 常量定义

所有常量集中管理，避免循环导入
"""

import logging
from pathlib import Path

# ============ 配置常量 ============
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"
TIMEOUT_MS = 15000
MAX_RETRIES = 3

# ============ 路径常量 ============
PLUGIN_DIR = Path(__file__).parent
RULES_DIR = PLUGIN_DIR / "rules"
RULES_INDEX_PATH = RULES_DIR / "index.json"
VIOLATIONS_LOG = Path.home() / ".hermes" / "logs" / "soul-violations.log"
EXECUTION_AUTH_FILE = Path.home() / ".hermes" / ".soul_execution_auth"

# ============ 工作流路径 ============
WORKFLOWS_DIR = Path.home() / ".hermes" / "workflows"
WORKFLOWS_INDEX = WORKFLOWS_DIR / "_index.yaml"
WORKFLOW_MANAGER_SKILL = Path.home() / ".hermes" / "skills" / "openclaw-imports" / "workflow-manager" / "SKILL.md"

# ============ 日志 ============
logger = logging.getLogger("soul-context-injector")


# ============ 拦截常量 ============

# 破坏性命令 - 永久禁止（系统级破坏，无法恢复）
DANGEROUS_PATTERNS = [
    # 磁盘破坏
    "dd if=", "dd of=",
    "mkfs", "format",
    "> /dev/sd", "> /dev/hd", "> /dev/nvme",
    
    # 系统破坏
    "> /etc/passwd", "> /etc/shadow", "> /etc/fstab",
    "> /boot/",
    
    # Fork 炸弹
    ":(){:|:&};:", ":(){ :", "fork bomb",
    
    # 防火墙破坏
    "iptables -f", "iptables -x",
    "ufw disable",
    
    # 远程执行（未审查代码）- 更严格的检测
    "| bash", "|  bash", "|sh", "| sh", "|sudo",
    "|/bin/bash", "|/bin/sh",
    
    # 根目录破坏（新增）
    "rm -rf /", "rm -rf /*", "rm -fr /",
    "chmod 777 /", "chmod 777 /*", "chmod -r 777 /",
    "chown -r", "chown --recursive",
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

# 技能白名单 - 白名单内技能执行的所有操作跳过认证
SKILL_WHITELIST = [
    "workflow-manager",
    "agent-pool",
    "planning-with-files",
]

# 确认词 - 用户确认执行方案
CONFIRM_KEYWORDS = ["同意", "确认", "执行", "开始吧", "好的", "可以", "没问题", "approve", "confirm", "yes", "ok", "execute"]
