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
import fcntl
import contextlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 支持相对导入和绝对导入
try:
    from .constants import (
        logger, SKILL_BINDINGS,
        EXECUTION_TYPES, REQUIRED_SKILLS_L4, MAX_ESCAPE_ATTEMPTS,
        EXECUTION_TIMEOUT_SECONDS, TRACKER_TTL_SECONDS,
        TERMINAL_DETECTION_PATTERNS, SENSITIVE_PATTERNS, PHASE_INFO_MAX_LENGTH,
        OUTPUT_TOOLS, INFO_TOOLS, HERMES_HOME, GRADUATED_WARN_THRESHOLD, GRADUATED_BLOCK_THRESHOLD,
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
        "L4": ["planning-with-files"],
    }
    # L4 常量降级定义
    EXECUTION_TYPES = {
        "DELEGATE_TASK": "delegate_task",
        "AGENT_POOL_CLIENT": "agent_pool_client",
        "ORCHESTRATOR": "orchestrator",
        "TERMINAL_EXECUTION": "terminal_execution",
        "PYTHON_API": "python_api",
    }
    REQUIRED_SKILLS_L4 = ["planning-with-files"]
    MAX_ESCAPE_ATTEMPTS = 5  # 给 AI 更多纠正机会
    EXECUTION_TIMEOUT_SECONDS = 300  # 空闲阈值：距最近一次必需技能调用超过此值视为空闲超时（与 constants.py 保持同步）
    TRACKER_TTL_SECONDS = 86400
    TERMINAL_DETECTION_PATTERNS = []
    SENSITIVE_PATTERNS = []
    PHASE_INFO_MAX_LENGTH = 200
    OUTPUT_TOOLS = {"send_message", "text_to_speech"}
    INFO_TOOLS = {"terminal", "read_file", "search_files", "delegate_task", "web_search", "memory", "clarify"}
    HERMES_HOME = Path('/home/kali/.hermes')
    GRADUATED_WARN_THRESHOLD = 1  # 首次警告
    GRADUATED_BLOCK_THRESHOLD = 3  # 给 AI 更多纠正机会

# 追踪文件目录
TRACKING_DIR = HERMES_HOME / "skill-tracking"


@contextlib.contextmanager
def file_lock(file_path: Path, mode: str = "r"):
    """文件锁上下文管理器"""
    with open(file_path, mode) as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁


def _check_completion(tracker: Dict) -> bool:
    """检查任务是否完成（内部函数）

    Args:
        tracker: 追踪器数据

    Returns:
        True 如果所有必需技能已调用
    """
    required = tracker.get("current", {}).get("required_skills", [])
    called = tracker.get("current", {}).get("called_skills", [])
    return all(s in called for s in required)


def check_round_completion(session_id: str, task_level: str) -> Tuple[bool, List[str]]:
    """检查本轮是否已完成必要的技能调用"""
    tracker = get_tracker(session_id)
    if not tracker:
        return False, SKILL_BINDINGS.get(task_level, [])
    current = tracker.get("current", {})
    called_skills = current.get("called_skills", [])
    required_skills = current.get("required_skills", [])
    missing = [s for s in required_skills if s not in called_skills]
    return len(missing) == 0, missing


def should_block_tool_call(session_id: str, tool_name: str, task_level: str) -> tuple:
    """检查是否应该拦截工具调用

    逃生舱机制：连续拦截达到 MAX_ESCAPE_ATTEMPTS 后自动放行，
    防止 AI 无法执行任何操作导致死锁。

    v5.14.0 范围缩窄：仅 OUTPUT_TOOLS（send_message/text_to_speech）
    强制拦截；信息获取工具（read_file/search_files/terminal 等）
    放行，避免批量消息中多个工具同时被 BLOCK。
    """
    try:
        from .constants import TOOL_WHITELIST, MAX_ESCAPE_ATTEMPTS, OUTPUT_TOOLS
    except ImportError:
        from constants import TOOL_WHITELIST, MAX_ESCAPE_ATTEMPTS, OUTPUT_TOOLS

    if tool_name in TOOL_WHITELIST:
        return False, None

    is_complete, missing_skills = check_round_completion(session_id, task_level)

    if not is_complete and missing_skills:
        # 信息获取工具：只记录不拦截
        if tool_name and tool_name in INFO_TOOLS:
            logger.info(
                f"[SOUL-ENFORCER] 信息获取工具放行: session={session_id}, "
                f"tool={tool_name}, missing={missing_skills}"
            )
            return False, None

        # 分级拦截：非输出工具首次警告，二次 BLOCK
        if tool_name and tool_name not in OUTPUT_TOOLS:
            tracker = get_tracker(session_id)
            if tracker:
                violation_count = tracker.get("violation_count", 0) + 1
                _update_tracker_data(session_id, {"violation_count": violation_count})

                if violation_count >= GRADUATED_BLOCK_THRESHOLD:
                    # 第2次：BLOCK
                    error_msg = (
                        "【强制执行约束】你必须先调用skill_view加载必须技能: "
                        + ", ".join(missing_skills)
                        + "。禁止调用其他工具！"
                    )
                    return True, error_msg
                else:
                    # 第1次：警告放行
                    logger.warning(
                        "[SOUL-ENFORCER] 首次违规警告: "
                        "session=" + session_id + ", tool=" + tool_name
                    )
                    return False, None

        # 逃生舱：递增 escape_attempts，达到阈值自动放行
        tracker = get_tracker(session_id)
        if tracker:
            escape_attempts = tracker.get("escape_attempts", 0) + 1
            _update_tracker_data(session_id, {"escape_attempts": escape_attempts})
            if escape_attempts > MAX_ESCAPE_ATTEMPTS:
                logger.warning(
                    "[SOUL] 逃生舱触发，自动放行: attempts=%d" % escape_attempts
                )
                return False, None

        error_msg = "【强制执行约束】你必须先调用skill_view加载必须技能: " + ", ".join(missing_skills) + "。禁止调用其他工具！"
        return True, error_msg

    return False, None


def migrate_tracker(old_tracker: Dict) -> Dict:
    """迁移旧格式追踪器到新格式

    Args:
        old_tracker: 旧格式追踪器数据

    Returns:
        新格式追踪器数据
    """
    now = datetime.datetime.now().isoformat()
    return {
        "session_id": old_tracker.get("session_id"),
        "task_level": old_tracker.get("task_level"),
        "created_at": old_tracker.get("created_at", now),
        "updated_at": old_tracker.get("updated_at", now),
        "current": {
            "required_skills": old_tracker.get("required_skills", []),
            "called_skills": old_tracker.get("called_skills", []),
            "round_skills": [],
        },
        "history": [],
        "metadata": {
            "total_calls": len(old_tracker.get("called_skills", [])),
            "level_transitions": 0,
            "last_skill_at": None
        }
    }


def create_tracker(session_id: str, task_level: str, force_reset: bool = False) -> Path:
    """创建或更新追踪器（增量模式）

    - 首次创建：初始化新追踪器
    - 等级相同：无操作
    - 等级转换：保存历史，更新当前任务

    Args:
        session_id: 会话 ID
        task_level: 任务等级（L0-L4, W, S）

    Returns:
        追踪文件路径
    """
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)

    required_skills = SKILL_BINDINGS.get(task_level, [])
    tracker_file = TRACKING_DIR / f"{session_id}.json"

    # 尝试读取旧追踪器
    old_tracker = None
    if tracker_file.exists():
        try:
            with file_lock(tracker_file, "r") as f:
                old_tracker = json.load(f)
        except Exception as e:
            logger.warning(f"[SOUL-ENFORCER] 读取旧追踪器失败: {e}")

    now = datetime.datetime.now().isoformat()

    # 首次创建
    if not old_tracker:
        tracker_data = {
            "session_id": session_id,
            "task_level": task_level,
            "created_at": now,
            "updated_at": now,
            "current": {
                "required_skills": required_skills,
                "called_skills": [],
                "round_skills": [],  # 本轮调用（每轮清空）
            },
            "history": [],
            "metadata": {
                "total_calls": 0,
                "level_transitions": 0,
                "last_skill_at": None
            }
        }
        logger.info(f"[SOUL-ENFORCER] 创建追踪器: session={session_id}, level={task_level}")

    # 增量更新
    else:
        old_level = old_tracker.get("task_level")

        # 等级相同
        if old_level == task_level:
            if force_reset:
                # 新请求：同等级轮次重置。上一轮未完成（缺技能）时保留
                # 已调用技能，避免每轮重复强制调用 deep-thinking；
                # 上一轮已完成才清空（真正的"新任务"语义）。
                old_complete = _check_completion(old_tracker)
                prev_called = old_tracker.get("current", {}).get("called_skills", [])
                tracker_data = {
                    "session_id": session_id,
                    "task_level": task_level,
                    "created_at": old_tracker.get("created_at"),
                    "updated_at": now,
                    "current": {
                        "required_skills": required_skills,
                        "called_skills": list(prev_called),  # 累积模式：只增不减
                        "round_skills": [],  # 每轮清空
                    },
                    "history": old_tracker.get("history", []),
                    "escape_attempts": 0,
                    "metadata": {
                        "total_calls": old_tracker.get("metadata", {}).get("total_calls", 0),
                        "level_transitions": old_tracker.get("metadata", {}).get("level_transitions", 0),
                        "last_skill_at": None
                    }
                }
                logger.info("[SOUL-ENFORCER] 新请求重置追踪器: " + session_id
                            + " (completed=" + str(old_complete)
                            + ", retained=" + str(len(tracker_data["current"]["called_skills"])) + ")")
                # 写入并返回
                with file_lock(tracker_file, "w") as f:
                    json.dump(tracker_data, f, ensure_ascii=False, indent=2)
                return tracker_file
            else:
                # 同等级新请求：清空 round_skills（每轮重新强制），保留 called_skills（累积）
                prev_called = old_tracker.get("current", {}).get("called_skills", [])
                tracker_data = {
                    "session_id": session_id,
                    "task_level": task_level,
                    "created_at": old_tracker.get("created_at"),
                    "updated_at": now,
                    "current": {
                        "required_skills": required_skills,
                        "called_skills": list(prev_called),
                        "round_skills": [],  # 清空 round_skills
                    },
                    "history": old_tracker.get("history", []),
                    "escape_attempts": 0,
                    "metadata": old_tracker.get("metadata", {}),
                }
                logger.info(f"[SOUL-ENFORCER] 同等级新请求清空 round_skills: {session_id}")
                with file_lock(tracker_file, "w") as f:
                    json.dump(tracker_data, f, ensure_ascii=False, indent=2)
                return tracker_file

        # 等级转换
        history_entry = {
            "level": old_level,
            "from": old_tracker.get("created_at"),
            "to": now,
            "required": old_tracker.get("current", {}).get("required_skills", []),
            "called": old_tracker.get("current", {}).get("called_skills", []),
            "completed": _check_completion(old_tracker)
        }

        # 限制历史长度
        history = old_tracker.get("history", [])
        history.append(history_entry)
        if len(history) > 10:
            history = history[-10:]

        prev_called = old_tracker.get("current", {}).get("called_skills", [])
        tracker_data = {
            "session_id": session_id,
            "task_level": task_level,
            "created_at": old_tracker.get("created_at"),  # 保留创建时间
            "updated_at": now,
            "current": {
                "required_skills": required_skills,
                "called_skills": list(prev_called),  # 累积模式：保留已调用技能
                "round_skills": [],  # 等级转换时清空 round_skills
            },
            "history": history,
            "metadata": {
                "total_calls": old_tracker.get("metadata", {}).get("total_calls", 0),
                "level_transitions": old_tracker.get("metadata", {}).get("level_transitions", 0) + 1,
                "last_skill_at": old_tracker.get("metadata", {}).get("last_skill_at")
            }
        }
        logger.info(f"[SOUL-ENFORCER] 等级转换: {session_id}, {old_level} → {task_level}")

    # 写入文件（带锁）
    with file_lock(tracker_file, "w") as f:
        json.dump(tracker_data, f, ensure_ascii=False, indent=2)

    return tracker_file


def get_tracker(session_id: str) -> Optional[Dict[str, Any]]:
    """获取技能追踪数据（自动迁移旧格式）

    自动检测并迁移旧格式追踪器到新格式。

    Args:
        session_id: 会话ID

    Returns:
        追踪器数据（新格式），或 None 如果不存在
    """
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return None

    try:
        with file_lock(tracker_file, "r") as f:
            tracker = json.load(f)

        # 检测旧格式（没有 "current" 字段）
        if "current" not in tracker:
            # 迁移到新格式
            tracker = migrate_tracker(tracker)
            # 保存迁移后的数据
            with file_lock(tracker_file, "w") as fw:
                json.dump(tracker, fw, ensure_ascii=False, indent=2)
            logger.info(f"[SOUL-ENFORCER] 迁移旧格式追踪器: {session_id}")

        return tracker
    except json.JSONDecodeError as e:
        logger.error(f"[SOUL-ENFORCER] 追踪文件损坏: {e}")
        # 备份损坏文件
        backup_file = tracker_file.with_suffix(".json.corrupted")
        tracker_file.rename(backup_file)
        logger.warning(f"[SOUL-ENFORCER] 已备份损坏文件: {backup_file}")
        return None
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 读取追踪文件失败: {e}")
        return None


def ensure_tracker(session_id: str, task_level: str = 'L2') -> None:
    tracker = get_tracker(session_id)
    if not tracker:
        create_tracker(session_id, task_level)
        logger.info('[SOUL-ENFORCER] 延迟创建 tracker: session=%s, level=%s', session_id, task_level)


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
    """更新追踪器数据（内部函数）——统一走文件写入。"""
    tracker = get_tracker(session_id)
    if not tracker:
        logger.warning(f"[SOUL-ENFORCER] 追踪器不存在，无法更新: {session_id}")
        return False
    tracker.update(updates)
    try:
        return _write_tracker_file(session_id, tracker)
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 追踪器文件写入失败: {e}")
        return False


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
    
    # 滑动窗口基准：优先 metadata.last_skill_at（最近一次技能调用），回退 created_at
    baseline_str = (tracker.get("metadata", {}) or {}).get("last_skill_at") or tracker.get("created_at")
    if not baseline_str:
        return False

    try:
        baseline = datetime.datetime.fromisoformat(baseline_str)
        idle_seconds = (datetime.datetime.now() - baseline).total_seconds()
        if idle_seconds > EXECUTION_TIMEOUT_SECONDS:
            baseline_src = "last_skill_at" if (tracker.get("metadata", {}) or {}).get("last_skill_at") else "created_at"
            logger.warning(f"[SOUL-ENFORCER] 执行超时(滑动窗口)，自动放行: session={session_id}, idle={idle_seconds:.1f}s, 基准={baseline_src}")
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
    """更新技能追踪数据（带文件锁）

    Args:
        session_id: 会话ID
        data: 追踪器数据

    Returns:
        True 如果更新成功
    """
    tracker_file = TRACKING_DIR / f"{session_id}.json"
    if not tracker_file.exists():
        return False

    try:
        with file_lock(tracker_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"[SOUL-ENFORCER] 更新追踪文件失败: {e}")
        return False


def track_skill_call(session_id: str, skill_name: str) -> bool:
    """追踪技能调用（更新元数据）

    支持新旧格式追踪器，并更新 metadata。

    Args:
        session_id: 会话ID
        skill_name: 技能名称

    Returns:
        True 如果追踪成功
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return False

    # 获取已调用技能列表（兼容新旧格式）
    current = tracker.get("current", {})
    if current:
        # 新格式
        called_skills = current.get("called_skills", [])
        round_skills = current.get("round_skills", [])
    else:
        # 旧格式
        called_skills = tracker.get("called_skills", [])
        round_skills = []

    is_new = skill_name not in called_skills
    if is_new:
        called_skills.append(skill_name)

    # 更新 round_skills（本轮调用记录）
    if skill_name not in round_skills:
        round_skills.append(skill_name)
    if current:
        current["round_skills"] = round_skills

    # 无条件续期滑动窗口基准（重复调用同一技能也要刷新）
    metadata = tracker.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        tracker["metadata"] = metadata
    if is_new:
        metadata["total_calls"] = metadata.get("total_calls", 0) + 1
    metadata["last_skill_at"] = datetime.datetime.now().isoformat()

    # 只在调用前该技能是缺失的时重置 violation_count
    # 防止 AI 通过重复调用已满足技能绕过拦截
    if is_new:
        required_skills = current.get("required_skills", [])
        called_before = [s for s in called_skills if s != skill_name]
        missing_before = [s for s in required_skills if s not in called_before]
        if skill_name in missing_before:
            tracker["violation_count"] = 0

    update_tracker(session_id, tracker)
    logger.info(
        f"[SOUL-ENFORCER] 技能调用追踪: session={session_id}, skill={skill_name}, renewed={not is_new}"
    )

    return True


def has_called_skill(session_id: str, skill_name: str) -> bool:
    """检查是否调用了指定技能（支持新旧格式）

    Args:
        session_id: 会话ID
        skill_name: 技能名称

    Returns:
        True 如果已调用
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return False

    # 兼容新旧格式
    current = tracker.get("current", {})
    if current:
        called_skills = current.get("called_skills", [])
    else:
        called_skills = tracker.get("called_skills", [])

    return skill_name in called_skills


def check_required_skills(session_id: str, tool_name: str = None, task_level: str = None) -> Tuple[bool, Optional[str]]:
    """检查是否调用了所有必须技能 + 实际执行

    支持新旧格式追踪器：
    - 新格式: tracker.current.required_skills, tracker.current.called_skills, tracker.history
    - 旧格式: tracker.required_skills, tracker.called_skills

    ⚠️ 逃生舱机制：每次拦截自动递增 escape_attempts
    达到 MAX_ESCAPE_ATTEMPTS 后自动放行

    v5.12.0: 非输出工具降级为警告（不 BLOCK）
    v5.14.0: L2/L3 范围缩窄 — 仅在 OUTPUT_TOOLS 时拦截，不拦截信息获取工具

    Args:
        session_id: 会话ID
        tool_name: 当前调用的工具名（用于判断是否 BLOCK）
        task_level: 当前任务等级（L2/L3 仅 OUTPUT_TOOLS 强制，L4 宽松）

    Returns:
        (True, None): 检查通过，允许输出
        (False, error): 检查失败，返回错误信息
    """
    tracker = get_tracker(session_id)
    if not tracker:
        return True, None

    # 获取当前任务必需技能（兼容新旧格式）
    current = tracker.get("current", {})
    if current:
        # 新格式
        required = current.get("required_skills", [])
        called = set(current.get("called_skills", []))
        # 从历史中合并已调用技能
        for h in tracker.get("history", []):
            called.update(h.get("called", []))
    else:
        # 旧格式
        required = tracker.get("required_skills", [])
        called = set(tracker.get("called_skills", []))

    executed_by = tracker.get("executed_by", [])
    # 优先使用传入的 task_level，否则从 tracker 获取
    if task_level is None:
        task_level = tracker.get("task_level")

    # 检查技能调用
    missing_skills = [s for s in required if s not in called]

    # L4 任务不再强制要求 agent_pool_client 执行（delegate_task 由 Hermes 内置支持）
    missing_execution = False
    
    if missing_skills or missing_execution:
        # 信息获取工具：只记录不拦截
        if tool_name and tool_name in INFO_TOOLS:
            logger.info(
                f"[SOUL-ENFORCER] 信息获取工具放行: tool={tool_name}, "
                f"missing={missing_skills}, session={session_id}"
            )
            return True, None

        # 非输出工具：按 task_level 分级处理
        if tool_name and tool_name not in OUTPUT_TOOLS:
            # L2/L3：信息获取工具放行（范围缩窄：不拦截非输出工具）
            # L4/其他：降级为警告（保持 v5.12.0 行为）
            logger.warning(
                f"[SOUL-ENFORCER] 技能缺失但放行: session={session_id}, "
                f"missing={missing_skills}, tool={tool_name}"
            )
            return True, None

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
            error_parts.append("未执行实际任务（需调用 delegate_task）")
        
        error_text = "\n".join(error_parts)
        
        return False, f"""【规则违反】

{error_text}

当前任务等级: {task_level}
已调用技能: {', '.join(called) if called else '无'}
执行方式: {', '.join(executed_by) if executed_by else '无'}

---

【正确流程】

1. skill_view("planning-with-files")
2. delegate_task()
3. 输出结果

---

【回退选项】

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
    # 超时兜底已移除：check_execution_timeout 由 hook 主流程独立调用
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
