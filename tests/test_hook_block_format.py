"""Hook 返回值格式测试。

验证 pre_tool_call_hook 返回 {"action": "block", "message": ...}
格式，使 Hermes 框架能正确识别 BLOCK 指令。

v5.14.0: L2/L3 仅在 OUTPUT_TOOLS 时返回 block。
"""
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestHookBlockFormat:
    """验证 pre_tool_call_hook 的返回值格式。"""

    def test_l2_missing_skill_returns_block_on_send_message(self, soul_init):
        """L2 任务缺少 deep-thinking 时，send_message 应返回 action=block。"""
        from soul_context_injector.enforcer import create_tracker

        session_id = "test_format_l2_block"
        create_tracker(session_id, "L2")

        result = soul_init.pre_tool_call_hook(
            tool_name="send_message",
            args={"message": "test"},
            task_id="test_task",
            session_id=session_id,
        )

        assert result is not None, "send_message 应返回非 None 结果（BLOCK）"
        assert result.get("action") == "block", (
            f"返回值应包含 action=block，实际: {result}"
        )
        assert "message" in result, "返回值应包含 message 字段"
        assert "deep-thinking" in result["message"], (
            f"message 应提及 deep-thinking，实际: {result['message']}"
        )

    def test_l2_info_tool_not_blocked(self, soul_init):
        """L2 任务缺少 deep-thinking 时，read_file 不应被 BLOCK（范围缩窄）。"""
        from soul_context_injector.enforcer import create_tracker

        session_id = "test_format_l2_no_block_info"
        create_tracker(session_id, "L2")

        result = soul_init.pre_tool_call_hook(
            tool_name="read_file",
            args={"path": "/etc/hostname"},
            task_id="test_task",
            session_id=session_id,
        )

        # 信息获取工具应放行
        if result is not None:
            assert result.get("action") != "block", (
                f"read_file 不应被 BLOCK，实际: {result}"
            )

    def test_l3_missing_skill_returns_block_on_send_message(self, soul_init):
        """L3 任务缺少 openclaw-behavior-plan 时，send_message 应返回 action=block。"""
        from soul_context_injector.enforcer import create_tracker, track_skill_call

        session_id = "test_format_l3_block"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        result = soul_init.pre_tool_call_hook(
            tool_name="send_message",
            args={"message": "test"},
            task_id="test_task",
            session_id=session_id,
        )

        assert result is not None, "send_message 应返回非 None 结果（BLOCK）"
        assert result.get("action") == "block", (
            f"返回值应包含 action=block，实际: {result}"
        )

    def test_l3_info_tool_not_blocked(self, soul_init):
        """L3 任务缺少 openclaw-behavior-plan 时，terminal 不应被 BLOCK（范围缩窄）。"""
        from soul_context_injector.enforcer import create_tracker, track_skill_call

        session_id = "test_format_l3_no_block_info"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        result = soul_init.pre_tool_call_hook(
            tool_name="terminal",
            args={"command": "ls"},
            task_id="test_task",
            session_id=session_id,
        )

        # 信息获取工具应放行
        if result is not None:
            assert result.get("action") != "block", (
                f"terminal 不应被 BLOCK，实际: {result}"
            )

    def test_l4_missing_skill_returns_no_block(self, soul_init):
        """L4 任务缺少技能时，中间工具不应被 BLOCK（只在 OUTPUT_TOOLS 时检查）。"""
        from soul_context_injector.enforcer import create_tracker

        session_id = "test_format_l4_no_block"
        create_tracker(session_id, "L4")

        result = soul_init.pre_tool_call_hook(
            tool_name="read_file",
            args={"path": "/etc/hostname"},
            task_id="test_task",
            session_id=session_id,
        )

        # L4 中间工具应放行（result 可能是 None 或非 block）
        if result is not None:
            assert result.get("action") != "block", (
                f"L4 中间工具不应被 BLOCK，实际: {result}"
            )

    def test_l2_with_skill_returns_no_block(self, soul_init):
        """L2 任务已调用 deep-thinking 时，不应被 BLOCK。"""
        from soul_context_injector.enforcer import create_tracker, track_skill_call

        session_id = "test_format_l2_no_block"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        result = soul_init.pre_tool_call_hook(
            tool_name="send_message",
            args={"message": "test"},
            task_id="test_task",
            session_id=session_id,
        )

        if result is not None:
            assert result.get("action") != "block", (
                f"已调用 deep-thinking 不应被 BLOCK，实际: {result}"
            )

    def test_no_error_key_in_return(self, soul_init):
        """返回值中不应包含 error 键（框架不识别）。"""
        from soul_context_injector.enforcer import create_tracker

        session_id = "test_format_no_error_key"
        create_tracker(session_id, "L2")

        result = soul_init.pre_tool_call_hook(
            tool_name="send_message",
            args={"message": "test"},
            task_id="test_task",
            session_id=session_id,
        )

        if result is not None:
            assert "error" not in result, (
                f"返回值不应包含 error 键（框架不识别），实际: {result}"
            )
