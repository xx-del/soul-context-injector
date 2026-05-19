"""
Soul Context Injector - 子 Agent 检测模块

通过 session_id 查询数据库判断是否为子 agent（存在 parent_session_id）
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("soul-context-injector")

# SessionDB 数据库路径（正确路径是 state.db）
_STATE_DB_PATH = Path.home() / ".hermes" / "state.db"


def is_subagent(session_id: str) -> bool:
    """
    检测当前 session 是否为子 agent
    
    通过查询 sessions 表的 parent_session_id 字段判断：
    - parent_session_id 非空 → 子 agent
    - parent_session_id 为空 → 主 agent
    
    Args:
        session_id: 当前会话 ID
        
    Returns:
        True: 是子 agent
        False: 是主 agent
    """
    if not session_id or not _STATE_DB_PATH.exists():
        return False
    
    conn = None
    try:
        # 使用 WAL 模式避免锁竞争
        conn = sqlite3.connect(str(_STATE_DB_PATH), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT parent_session_id FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if row and row[0]:
            logger.info(f"[SOUL] 检测到子 agent: session={session_id}, parent={row[0]}")
            return True
        
        return False
        
    except sqlite3.Error as e:
        logger.warning(f"[SOUL] 检测子 agent 数据库错误: {e}")
        # 数据库错误时，假设是子 agent（安全降级）
        # 因为子 agent 不应该被拦截
        return True
    except Exception as e:
        logger.warning(f"[SOUL] 检测子 agent 失败: {e}")
        # 其他错误也安全降级
        return True
    finally:
        if conn:
            conn.close()


def get_parent_session_id(session_id: str) -> Optional[str]:
    """
    获取父 session ID
    
    Args:
        session_id: 当前会话 ID
        
    Returns:
        父 session ID，如果不存在则返回 None
    """
    if not session_id or not _STATE_DB_PATH.exists():
        return None
    
    conn = None
    try:
        # 使用 WAL 模式避免锁竞争
        conn = sqlite3.connect(str(_STATE_DB_PATH), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT parent_session_id FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        return row[0] if row else None
        
    except sqlite3.Error as e:
        logger.warning(f"[SOUL] 获取父 session 数据库错误: {e}")
        return None
    except Exception as e:
        logger.warning(f"[SOUL] 获取父 session 失败: {e}")
        return None
    finally:
        if conn:
            conn.close()
