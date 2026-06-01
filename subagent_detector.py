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
    
    区分规则：
    - CLI会话延续：source=cli且parent存在 → 不是子agent，需要注入L等级
    - 真子agent：source=feishu等且parent存在 → 是子agent，跳过注入
    - 主agent：parent不存在 → 不是子agent
    
    Args:
        session_id: 当前会话 ID
        
    Returns:
        True: 是子 agent（跳过注入）
        False: 不是子 agent（需要注入）
    """
    if not session_id or not _STATE_DB_PATH.exists():
        return False
    
    conn = None
    try:
        # 使用 WAL 模式避免锁竞争
        conn = sqlite3.connect(str(_STATE_DB_PATH), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # 查询 parent_session_id 和 source
        cursor.execute(
            """SELECT s.parent_session_id, s.source, p.source as parent_source
               FROM sessions s
               LEFT JOIN sessions p ON s.parent_session_id = p.id
               WHERE s.id = ?""",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if not row or not row[0]:
            # 无parent_session_id → 主agent
            return False
        
        parent_session_id = row[0]
        source = row[1]
        
        # CLI会话延续：source=cli → 不是子agent，需要注入L等级
        if source == 'cli':
            logger.info(f"[SOUL] CLI会话延续: session={session_id}, parent={parent_session_id}")
            return False
        
        # 其他platform：真子agent，跳过注入
        logger.info(f"[SOUL] 检测到子 agent: session={session_id}, parent={parent_session_id}")
        return True
        
    except sqlite3.Error as e:
        logger.warning(f"[SOUL] 检测子 agent 数据库错误: {e}")
        # 数据库错误时，返回False（需要注入），避免跳过所有会话
        return False
    except Exception as e:
        logger.warning(f"[SOUL] 检测子 agent 失败: {e}")
        return False
    finally:
        if conn:
            conn.close()
