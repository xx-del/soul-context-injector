"""
Soul Context Injector - 会话状态管理

v5.2 简化版：仅保留必要的状态管理
"""

import threading
from typing import Optional, Dict, Any

from .constants import logger, SKILL_WHITELIST


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
    """检查技能是否在白名单中"""
    if not skill_name:
        return False
    return skill_name in SKILL_WHITELIST
