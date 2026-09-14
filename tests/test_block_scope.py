"""should_block_tool_call 范围缩窄测试（真实 hook 路径）。

v5.14.0 声明"仅在 OUTPUT_TOOLS 时拦截，不拦截信息获取工具"，
但该语义只实现于未被调用的 check_required_skills（死代码）；
pre_tool_call_hook 实际调用的 should_block_tool_call 仍对
所有非白名单工具一刀切 BLOCK → 批量 read_file+search_files
双拦截（2026-09-14 09:47 违规日志实锤）。
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def temp_tracking_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            yield Path(tmpdir)


INFO_TOOLS = [
    "read_file", "search_files", "terminal", "execute_code",
    "web_search", "web_extract", "write_file", "delegate_task",
]


class TestL2ShouldBlockScope:
    @pytest.mark.parametrize("tool", INFO_TOOLS)
    def test_l2_info_tools_pass_without_skill(self, temp_tracking_dir, tool):
        """L2 未调用 deep-thinking：信息获取工具应放行（不再 BLOCK）。"""
        from enforcer import create_tracker, should_block_tool_call

        sid = "block_scope_l2_" + tool
        create_tracker(sid, "L2")

        should_block, msg = should_block_tool_call(sid, tool, "L2")
        assert should_block is False, tool + " 应放行，实际拦截: " + str(msg)

    def test_l2_send_message_blocks_without_skill(self, temp_tracking_dir):
        """L2 未调用 deep-thinking：send_message 仍应 BLOCK。"""
        from enforcer import create_tracker, should_block_tool_call

        sid = "block_scope_l2_output"
        create_tracker(sid, "L2")

        should_block, msg = should_block_tool_call(sid, "send_message", "L2")
        assert should_block is True, "send_message 应被拦截"
        assert "deep-thinking" in msg

    def test_l2_skill_view_always_passes(self, temp_tracking_dir):
        """白名单工具（skill_view）始终放行。"""
        from enforcer import create_tracker, should_block_tool_call

        sid = "block_scope_l2_skillview"
        create_tracker(sid, "L2")
        should_block, _ = should_block_tool_call(sid, "skill_view", "L2")
        assert should_block is False


class TestL3ShouldBlockScope:
    def test_l3_read_file_passes_partial_skill(self, temp_tracking_dir):
        """L3 只调用 deep-thinking（缺 openclaw-behavior-plan）：read_file 放行。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call

        sid = "block_scope_l3_partial"
        create_tracker(sid, "L3")
        track_skill_call(sid, "deep-thinking")

        should_block, msg = should_block_tool_call(sid, "read_file", "L3")
        assert should_block is False, "read_file 应放行: " + str(msg)

    def test_l3_send_message_blocks_partial_skill(self, temp_tracking_dir):
        """L3 只调用 deep-thinking：send_message 仍应 BLOCK。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call

        sid = "block_scope_l3_output"
        create_tracker(sid, "L3")
        track_skill_call(sid, "deep-thinking")

        should_block, msg = should_block_tool_call(sid, "send_message", "L3")
        assert should_block is True