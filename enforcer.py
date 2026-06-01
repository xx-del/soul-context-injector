"""
强制执行器 - 技能调用追踪 + 输出拦截

功能：
1. 追踪技能调用（skill_view）
2. 输出前检查（send_message）
3. 违规拦截
"""

import json
import datetime
import re
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 支持相对导入和绝对导入
try:
    from .constants import (
        logger, SKILL_BINDINGS,
        EXECUTION_TYPES, REQUIRED_SKILLS_L4, MAX_ESCAPE_ATTEMPTS,
        EXECUTION_TIMEOUT_SECONDS, TRACKER_TTL_SECONDS,
        TERMINAL_DETECTION_PATTERNS, SENSITIVE_PATTERNS, PHASE_INFO_MAX_LENGTH,
    )
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("soul-enforcer")
    # 降级时使用本地定义
    SKILL_BINDINGS = {
        "W": ["workflow-manager"],
        "L2": ["deep-thinking"],
        "L3": ["deep-thinking", "openclaw-behavior-plan"],
        "L4": ["planning-with-files", "agent-pool"],
    }
    # L4 常量降级定义
    EXECUTION_TYPES = {
        "DELEGATE_TASK": "delegate_task",
        "AGENT_POOL_CLIENT": "agent_pool_client",
        "ORCHESTRATOR": "orchestrator",
        "TERMINAL_EXECUTION": "terminal_execution",
        "PYTHON_API": "python_api",
    }
    REQUIRED_SKILLS_L4 = ["planning-with-files", "agent-pool"]
    MAX_ESCAPE_ATTEMPTS = 7  # Increased from 3 to prevent quick bypass
    EXECUTION_TIMEOUT_SECONDS = 600
    TRACKER_TTL_SECONDS = 86400
    TERMINAL_DETECTION_PATTERNS = []
    SENSITIVE_PATTERNS = []
    PHASE_INFO_MAX_LENGTH = 200

# 追踪文件目录
TRACKING_DIR = Path.home() / ".hermes" / "skill-tracking"


def create_tracker(session_id: str, task_level: str) -> Path:
    """创建技能追踪文件"""
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    
    required_skills = SKILL_BINDINGS.get(task_level, [])
    
    tracker_data = {
        "session_id": session_id,
        "task_level": task_level,
        "created_at": datetime.datetime.now().isoformat(),
        "called_skills": [],  # 已调用的技能列表
        "required_skills": required_skills,  # 必须调用的技能
    }
    
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    tracker_file.write_text(json.dumps(tracker_data, ensure_ascii=False, indent=2))
    logger.info(f"[SOUL-ENFORCER] 创建技能追踪: session={session_id}, level={task_level}, required={required_skills}")
    
    return tracker_file


def get_tracker(session_id: str) -> Optional[Dict[str, Any]]:
    """获取技能追踪数据"""
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return None
    
    try:
        return json.loads(tracker_file.read_text())
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 读取追踪文件失败: {e}")
        return None


def _write_tracker_file(session_id: str, tracker: dict) -> bool:
    """直接写入追踪器文件（内部函数）"""
    try:
        tracker_file = TRACKING_DIR / f"{session_id}.json"
        tracker_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tracker_file, 'w', encoding='utf-8') as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)
        logger.debug(f"[SOUL-ENFORCER] 追踪器文件写入成功: {tracker_file}")
        return True
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 追踪器文件写入失败: {e}")
        return False


def _update_tracker_data(session_id: str, updates: dict) -> bool:
    """更新追踪器数据（内部函数）"""
    tracker = get_tracker(session_id)
    if not tracker:
        logger.warning(f"[SOUL-ENFORCER] 追踪器不存在，无法更新: {session_id}")
        return False
    
    tracker.update(updates)
    
    try:
        from . import persistence
        if hasattr(persistence, 'set_tracker') and callable(persistence.set_tracker):
            persistence.set_tracker(session_id, tracker)
            logger.debug("[SOUL-ENFORCER] 使用 persistence.set_tracker 持久化")
        elif hasattr(persistence, 'save_tracker') and callable(persistence.save_tracker):
            persistence.save_tracker(session_id, tracker)
            logger.debug("[SOUL-ENFORCER] 使用 persistence.save_tracker 持久化")
        else:
            logger.warning("[SOUL-ENFORCER] persistence 模块无可用函数，回退到文件写入")
            _write_tracker_file(session_id, tracker)
    except ImportError as e:
        logger.debug(f"[SOUL-ENFORCER] persistence 模块不存在: {e}")
        _write_tracker_file(session_id, tracker)
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 持久化失败，回退到文件写入: {e}")
        try:
            _write_tracker_file(session_id, tracker)
        except Exception as e2:
            logger.error(f"[SOUL-ENFORCER] 文件写入也失败: {e2}")
            return False
    
    return True


def track_execution(session_id: str, execution_type: str, tool_name: str = None) -> bool:
    """追踪实际执行（多路径支持）"""
    tracker = get_tracker(session_id)
    if not tracker:
        logger.warning(f"[SOUL-ENFORCER] 追踪器不存在: {session_id}")
        return False
    
    if "executed_by" not in tracker:
        tracker["executed_by"] = []
    
    if execution_type not in tracker["executed_by"]:
        tracker["executed_by"].append(execution_type)
        _update_tracker_data(session_id, {"executed_by": tracker["executed_by"]})
        logger.info(f"[SOUL-ENFORCER] 执行追踪: session={session_id}, type={execution_type}, tool={tool_name}")
    
    return True


def has_executed(session_id: str) -> bool:
    """检查是否已实际执行"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False
    executed_by = tracker.get("executed_by", [])
    return len(executed_by) > 0


def check_execution_timeout(session_id: str) -> bool:
    """检查执行是否超时"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False
    
    created_at_str = tracker.get("created_at")
    if not created_at_str:
        return False
    
    try:
        created_at = datetime.datetime.fromisoformat(created_at_str)
        elapsed = (datetime.datetime.now() - created_at).total_seconds()
        if elapsed > EXECUTION_TIMEOUT_SECONDS:
            logger.warning(f"[SOUL-ENFORCER] 执行超时，自动放行: session={session_id}, elapsed={elapsed:.1f}s")
            return True
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 时间解析失败: {e}")
        return False
    
    return False


def cleanup_expired_trackers():
    """清理过期追踪文件"""
    if not TRACKING_DIR.exists():
        return
    
    now = time.time()
    cleaned = 0
    
    for tracker_file in TRACKING_DIR.glob("*.json"):
        try:
            with open(tracker_file, encoding='utf-8') as f:
                tracker = json.load(f)
            created_at_str = tracker.get("created_at")
            if created_at_str:
                created_at = datetime.datetime.fromisoformat(created_at_str).timestamp()
                if now - created_at > TRACKER_TTL_SECONDS:
                    os.remove(tracker_file)
                    cleaned += 1
                    logger.info(f"[SOUL-ENFORCER] 清理过期追踪: {tracker_file.name}")
        except Exception as e:
            logger.error(f"[SOUL-ENFORCER] 清理失败: {tracker_file.name}, {e}")
    
    if cleaned > 0:
        logger.info(f"[SOUL-ENFORCER] 清理完成: {cleaned} 个追踪文件")


def update_tracker(session_id: str, data: Dict[str, Any]) -> bool:
    """更新技能追踪数据"""
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return False
    
    try:
        tracker_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 更新追踪文件失败: {e}")
        return False


def track_skill_call(session_id: str, skill_name: str) -> bool:
    """追踪技能调用"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False
    
    if skill_name not in tracker["called_skills"]:
        tracker["called_skills"].append(skill_name)
        update_tracker(session_id, tracker)
        logger.info(f"[SOUL-ENFORCER] 技能调用追踪: session={session_id}, skill={skill_name}")
    
    return True


def has_called_skill(session_id: str, skill_name: str) -> bool:
    """检查是否调用了指定技能"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False
    
    return skill_name in tracker["called_skills"]


def check_required_skills(session_id: str) -> Tuple[bool, Optional[str]]:
    """检查是否调用了所有必须技能 + 实际执行
    
    ⚠️ 逃生舱机制：每次拦截自动递增 escape_attempts
    达到 MAX_ESCAPE_ATTEMPTS 后自动放行
    
    Args:
        session_id: 会话ID
    
    Returns:
        (True, None): 检查通过，允许输出
        (False, error): 检查失败，返回错误信息
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return True, None
    
    required = tracker.get("required_skills", [])
    called = tracker.get("called_skills", [])
    executed_by = tracker.get("executed_by", [])
    task_level = tracker.get("task_level")
    
    # 超时检查
    if check_execution_timeout(session_id):
        return True, None
    
    # 检查技能调用
    missing_skills = [s for s in required if s not in called]
    
    # L4 任务检查实际执行
    missing_execution = False
    if task_level == "L4" and not executed_by:
        missing_execution = True
    
    if missing_skills or missing_execution:
        # 【v3.0 修复】自动递增 escape_attempts
        escape_attempts = tracker.get("escape_attempts", 0) + 1
        
        # 持久化
        _update_tracker_data(session_id, {"escape_attempts": escape_attempts})
        
        # 达到阈值自动放行
        if escape_attempts >= MAX_ESCAPE_ATTEMPTS:
            logger.warning(f"[SOUL-ENFORCER] 达到最大拦截次数，自动放行: session={session_id}, attempts={escape_attempts}")
            return True, None
        
        # 构造错误信息
        error_parts = []
        
        if missing_skills:
            error_parts.append(f"未调用必须技能: {', '.join(missing_skills)}")
        
        if missing_execution:
            error_parts.append("未执行实际任务（需调用 delegate_task 或 agent_pool_client）")
        
        error_text = "\n".join(error_parts)
        
        return False, f"""【规则违反】

{error_text}

当前任务等级: {task_level}
已调用技能: {', '.join(called) if called else '无'}
执行方式: {', '.join(executed_by) if executed_by else '无'}

---

【正确流程】

1. skill_view("planning-with-files")
2. skill_view("agent-pool")
3. delegate_task() 或 agent_pool_client.execute()
4. 输出结果

---

【回退选项】

如果 agent-pool 不可用：

**选项 A: 回退到 L3（生成方案）**
1. skill_view("deep-thinking")
2. skill_view("openclaw-behavior-plan")
3. 生成 execution_plan.md

**选项 B: 回退到 L2（仅分析）**
1. skill_view("deep-thinking")
2. 输出分析结论

---

【自动放行机制】

拦截次数: {escape_attempts}/{MAX_ESCAPE_ATTEMPTS}
达到 {MAX_ESCAPE_ATTEMPTS} 次后将自动放行（触发回退）

---

⚠️ 此拦截由 soul-context-injector 强制执行机制触发
"""
    
    return True, None


def should_enforce(session_id: str) -> bool:
    """判断是否需要强制执行
    
    L2/L3/L4/W 任务需要强制执行
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return False
    
    task_level = tracker.get("task_level")
    return task_level in ["L2", "L3", "L4", "W"]
