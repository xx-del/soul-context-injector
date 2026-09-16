"""工具拦截范围缩窄测试 — 信息获取工具放行"""
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


class TestToolScopeNarrowing:
    """信息获取工具完全放行，仅输出工具被 BLOCK。"""

    def test_terminal_always_passes(self, temp_tracking_dir):
        """terminal 永远放行（即使缺少技能）。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("scope1", "L2")
        # 不调用 deep-thinking，直接用 terminal
        blocked, _ = should_block_tool_call("scope1", "terminal", "L2")
        assert blocked is False, "terminal 应永远放行"

    def test_read_file_always_passes(self, temp_tracking_dir):
        """read_file 永远放行。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("scope2", "L2")
        blocked, _ = should_block_tool_call("scope2", "read_file", "L2")
        assert blocked is False, "read_file 应永远放行"

    def test_search_files_always_passes(self, temp_tracking_dir):
        """search_files 永远放行。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("scope3", "L2")
        blocked, _ = should_block_tool_call("scope3", "search_files", "L2")
        assert blocked is False, "search_files 应永远放行"

    def test_delegate_task_always_passes(self, temp_tracking_dir):
        """delegate_task 永远放行。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("scope4", "L2")
        blocked, _ = should_block_tool_call("scope4", "delegate_task", "L2")
        assert blocked is False, "delegate_task 应永远放行"

    def test_send_message_blocked_when_skills_missing(self, temp_tracking_dir):
        """send_message 在缺少技能时被 BLOCK（输出工具不豁免）。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("scope5", "L2")
        # send_message 是 OUTPUT_TOOL，缺少 deep-thinking 时直接 BLOCK
        blocked, msg = should_block_tool_call("scope5", "send_message", "L2")
        assert blocked is True, "send_message 缺少技能时应 BLOCK"
        assert msg is not None, "BLOCK 时应返回错误信息"

    def test_info_tools_not_counted_as_violations(self, temp_tracking_dir):
        """信息获取工具调用不计入 violation_count（不影响后续拦截）。"""
        from enforcer import create_tracker, should_block_tool_call, get_tracker
        create_tracker("scope6", "L2")
        # 多次调用信息获取工具
        for _ in range(5):
            should_block_tool_call("scope6", "terminal", "L2")
        # violation_count 不应增加
        tracker = get_tracker("scope6")
        assert tracker.get("violation_count", 0) == 0, \
            "信息获取工具调用不应增加 violation_count"
