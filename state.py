"""
Soul Context Injector - 会话状态管理

v5.2 简化版：仅保留必要的状态管理
"""

import threading
from pathlib import Path
from typing import Optional, Dict, Any

from .constants import logger, SKILL_WHITELIST

# 技能目录
SKILLS_DIR = Path.home() / ".hermes" / "skills"


def _skill_exists(skill_name: str) -> bool:
    """检查技能是否已安装（支持分类目录和扁平目录）

    分类目录结构: ~/.hermes/skills/<category>/<skill_name>/SKILL.md
    扁平目录结构: ~/.hermes/skills/<skill_name>/SKILL.md
    """
    # 直接路径: ~/.hermes/skills/<skill_name>/SKILL.md
    direct = SKILLS_DIR / skill_name / "SKILL.md"
    if direct.exists():
        return True

    # 分类路径: ~/.hermes/skills/<category>/<skill_name>/SKILL.md
    try:
        for category_dir in SKILLS_DIR.iterdir():
            if category_dir.is_dir():
                nested = category_dir / skill_name / "SKILL.md"
                if nested.exists():
                    return True
    except PermissionError:
        pass

    return False


# ============ 会话状态 ============
_session_state: Dict[str, Any] = {
    "active_skill": None,       # 当前执行的技能名称
}

_state_lock = threading.Lock()  # 状态访问锁


# ============ 状态管理函数 ============

def get_active_skill() -> Optional[str]:
    """获取当前执行的技能名称"""
    with _state_lock:
        return _session_state.get("active_skill")


def set_active_skill(skill_name: str):
    """设置当前执行的技能
    
    Args:
        skill_name: 技能名称，None 表示清除当前技能
    """
    with _state_lock:
        if skill_name:
            _session_state["active_skill"] = skill_name
            logger.info(f"[SOUL] 技能激活: {skill_name}")
        else:
            _session_state["active_skill"] = None
            logger.debug("[SOUL] 技能已清除")


def is_skill_in_whitelist(skill_name: str) -> bool:
    """检查技能是否在白名单中（支持三种模式）

    all:      所有已安装技能都在白名单中
    list:     只在指定的技能列表中
    disabled: 白名单关闭，所有技能都需要认证
    """
    if not skill_name:
        return False

    # 从 constants 重新导入（避免循环导入问题）
    from .constants import SKILL_WHITELIST_MODE, SKILL_WHITELIST

    if SKILL_WHITELIST_MODE == 'all':
        return _skill_exists(skill_name)

    elif SKILL_WHITELIST_MODE == 'list':
        return skill_name in SKILL_WHITELIST

    elif SKILL_WHITELIST_MODE == 'disabled':
        return False

    return False


# ============ 注入等级追踪 ============
_injected_levels: Dict[str, str] = {}  # session_id → task_level


def get_last_injected_level(session_id: str) -> Optional[str]:
    """获取某 session 最近一次注入的任务等级"""
    return _injected_levels.get(session_id)


def set_last_injected_level(session_id: str, level: str) -> None:
    """记录某 session 注入的任务等级"""
    if level:
        _injected_levels[session_id] = level
