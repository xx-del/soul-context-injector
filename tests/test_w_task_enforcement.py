"""W 任务应创建 tracker 并触发强制执行。"""
import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestWTaskEnforcement:
    """W 任务 tracker 创建 + should_enforce"""

    def test_pre_llm_call_w_task_creates_tracker(self, soul_init):
        """W 任务应创建 task_level=W 的 tracker"""
        session_id = "test_w_tracker"
        # 清理可能残留的追踪文件
        import os
        from pathlib import Path as P
        tf = P.home() / ".hermes" / "skill-tracking" / f"{session_id}.json"
        if tf.exists():
            tf.unlink()

        soul_init.analyze_task.return_value = {
            "success": True, "task_level": "W",
            "workflow_name": "资产收集流程",
            "write_operation": False, "code_guidance": False,
            "agent_pool": False, "skill_usage": True,
            "self_improving": False,
        }

        result = soul_init.pre_llm_call_hook(
            session_id=session_id,
            user_message="执行 资产收集流程 工作流",
            conversation_history=[],
            is_first_turn=False,
            model="deepseek-v4-flash",
            platform="custom",
        )
        assert result is not None, "W 任务应注入上下文"

        from enforcer import get_tracker
        tracker = get_tracker(session_id)
        assert tracker is not None, "W 任务应创建 tracker"
        assert tracker["task_level"] == "W", f"预期W，实际 {tracker.get('task_level')}"

    def test_w_tracker_enables_enforcement(self, soul_init):
        """W tracker 存在时 should_enforce 应为 True"""
        session_id = "test_w_enforce"
        from enforcer import create_tracker, get_tracker, should_enforce
        create_tracker(session_id, "W")
        try:
            assert should_enforce(session_id) is True, "W 任务应触发强制"
        finally:
            import os
            from pathlib import Path as P
            tf = P.home() / ".hermes" / "skill-tracking" / f"{session_id}.json"
            if tf.exists():
                tf.unlink()

    def test_w_required_skill_is_workflow_manager(self):
        """W 任务 required_skills 应为 workflow-manager"""
        from constants import SKILL_BINDINGS
        assert SKILL_BINDINGS.get("W") == ["workflow-manager"]
