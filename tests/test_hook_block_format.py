"""Hook 返回值格式测试（v5.14.0 范围缩窄版）。

范围缩窄语义：L2/L3/L4 未调用必须技能时，仅输出工具
（send_message/text_to_speech）被 BLOCK；信息获取工具
（read_file/terminal 等）放行。
"""
import sys
from pathlib import Path
PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))

class TestHookBlockFormat:
    def test_l2_missing_skill_returns_block_on_send_message(self, soul_init):
        from soul_context_injector.enforcer import create_tracker
        create_tracker("fmt_l2", "L2")
        result = soul_init.pre_tool_call_hook(tool_name="send_message", args={"message": "test"}, task_id="t", session_id="fmt_l2")
        assert result is not None
        assert result.get("action") == "block"
        assert "deep-thinking" in result.get("message", "")

    def test_l2_info_tool_passes(self, soul_init):
        """L2 未调用 deep-thinking 时，信息获取工具（read_file）放行（v5.14.0 范围缩窄）。"""
        from soul_context_injector.enforcer import create_tracker
        create_tracker("fmt_l2info", "L2")
        result = soul_init.pre_tool_call_hook(tool_name="read_file", args={"path": "/etc/hostname"}, task_id="t", session_id="fmt_l2info")
        assert result is None

    def test_l3_missing_skill_returns_block_on_send_message(self, soul_init):
        from soul_context_injector.enforcer import create_tracker, track_skill_call
        create_tracker("fmt_l3", "L3")
        track_skill_call("fmt_l3", "deep-thinking")
        result = soul_init.pre_tool_call_hook(tool_name="send_message", args={"message": "test"}, task_id="t", session_id="fmt_l3")
        assert result is not None
        assert result.get("action") == "block"

    def test_l3_info_tool_passes(self, soul_init):
        """L3 未调用全部技能时，信息获取工具（terminal）放行（v5.14.0 范围缩窄）。"""
        from soul_context_injector.enforcer import create_tracker, track_skill_call
        create_tracker("fmt_l3info", "L3")
        track_skill_call("fmt_l3info", "deep-thinking")
        result = soul_init.pre_tool_call_hook(tool_name="terminal", args={"command": "ls"}, task_id="t", session_id="fmt_l3info")
        assert result is None

    def test_l4_send_message_returns_block(self, soul_init):
        """L4 未调用技能时，输出工具 send_message 被拦截（v5.14.0 范围缩窄）。"""
        from soul_context_injector.enforcer import create_tracker
        create_tracker("fmt_l4", "L4")
        result = soul_init.pre_tool_call_hook(tool_name="send_message", args={"message": "test"}, task_id="t", session_id="fmt_l4")
        assert result is not None
        assert result.get("action") == "block"

    def test_l2_with_skill_returns_no_block(self, soul_init):
        from soul_context_injector.enforcer import create_tracker, track_skill_call
        create_tracker("fmt_l2ok", "L2")
        track_skill_call("fmt_l2ok", "deep-thinking")
        result = soul_init.pre_tool_call_hook(tool_name="send_message", args={"message": "test"}, task_id="t", session_id="fmt_l2ok")
        if result is not None:
            assert result.get("action") != "block"

    def test_no_error_key_in_return(self, soul_init):
        from soul_context_injector.enforcer import create_tracker
        create_tracker("fmt_noerr", "L2")
        result = soul_init.pre_tool_call_hook(tool_name="send_message", args={"message": "test"}, task_id="t", session_id="fmt_noerr")
        if result is not None:
            assert "error" not in result