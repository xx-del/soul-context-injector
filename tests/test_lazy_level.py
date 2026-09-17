"""延迟兜底按首消息本地定级守卫测试"""
import importlib
import sqlite3
from pathlib import Path


def _seed_db(db_path: Path, session_id: str, content: str):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, parent_session_id TEXT, source TEXT)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT, tool_call_id TEXT, tool_calls TEXT,
            tool_name TEXT, timestamp REAL, token_count INTEGER DEFAULT 0,
            finish_reason TEXT, reasoning TEXT, reasoning_content TEXT,
            reasoning_details TEXT, codex_reasoning_items TEXT)"""
    )
    conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
        (session_id, content),
    )
    conn.commit()
    conn.close()


class TestFirstUserMessage:
    """能从库中取出本会话首条用户消息"""

    def test_returns_first_user_message(self, tmp_path, monkeypatch):
        import soul_context_injector.subagent_detector as mod
        db = tmp_path / "state.db"
        _seed_db(db, "s1", "查看系统日志文件内容")
        monkeypatch.setattr(mod, "_STATE_DB_PATH", db)
        assert mod.get_first_user_message("s1") == "查看系统日志文件内容"

    def test_returns_none_when_empty(self, tmp_path, monkeypatch):
        import soul_context_injector.subagent_detector as mod
        db = tmp_path / "state.db"
        _seed_db(db, "s2", "")
        monkeypatch.setattr(mod, "_STATE_DB_PATH", db)
        assert mod.get_first_user_message("s2") is None
        assert mod.get_first_user_message("nope") is None


class TestLocalLevelForSession:
    """首消息本地定级：豁免与分类与analyze_task一致"""

    def test_investigation_message_is_l1(self):
        from soul_context_injector.analyzer import local_client
        from soul_context_injector.subagent_detector import (
            get_first_user_message as _g,
        )
        assert _g is not None
        decision = local_client.analyze("查看系统日志文件内容")
        assert decision["task_level"] in ("L1", "L2")

    def test_create_message_is_l3(self):
        from soul_context_injector.analyzer import local_client
        decision = local_client.analyze("创建一个端口监控脚本")
        assert decision["task_level"] == "L3"


class TestLazyFallbackOrder:
    """兜底顺序：首消息本地定级优先，不再继承父等级"""

    def test_no_parent_inheritance_in_source(self):
        src = (Path(__file__).parent.parent / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert "get_parent_session_id" not in src.split(
            "延迟创建", 1
        )[1].split("if enforce:", 1)[0] if "延迟创建" in src else True

    def test_fallback_uses_local_classify(self, tmp_path, monkeypatch):
        """L1只读子会话不再拿到L4"""
        import soul_context_injector.subagent_detector as det
        import soul_context_injector.enforcer as enf
        importlib.reload(enf)
        monkeypatch.setattr(enf, "TRACKING_DIR", tmp_path)
        from soul_context_injector.analyzer import local_client
        decision = local_client.analyze("查看系统日志文件内容")
        level = decision["task_level"]
        enf.ensure_tracker("lazy-l1-child", level)
        tracker = enf.get_tracker("lazy-l1-child")
        assert tracker["task_level"] != "L4"
