"""L4 拦截作用域测试（v5.14.0 范围缩窄）。

验证 L4 任务在 planning-with-files/agent-pool 调用前：
- 输出工具（send_message）拦截
- 信息获取工具（terminal/read_file/write_file/delegate_task）放行
调用后全部放行；escape_attempts 达到阈值自动放行。
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


class TestL4ToolScoping:
    """L4 任务：信息获取工具放行，仅输出工具拦截（v5.14.0 范围缩窄）。"""

    def test_l4_allows_terminal_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t1", "L4")
        blocked, _ = should_block_tool_call("l4t1", "terminal", "L4")
        assert blocked is False

    def test_l4_allows_read_file_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t2", "L4")
        blocked, _ = should_block_tool_call("l4t2", "read_file", "L4")
        assert blocked is False

    def test_l4_allows_write_file_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t3", "L4")
        blocked, _ = should_block_tool_call("l4t3", "write_file", "L4")
        assert blocked is False

    def test_l4_allows_delegate_task_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t4", "L4")
        blocked, _ = should_block_tool_call("l4t4", "delegate_task", "L4")
        assert blocked is False

    def test_l4_blocks_send_message_before_skill(self, temp_tracking_dir):
        """L4 未调用技能时，输出工具 send_message 仍被拦截。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t4b", "L4")
        blocked, msg = should_block_tool_call("l4t4b", "send_message", "L4")
        assert blocked is True
        assert "planning-with-files" in msg

    def test_l4_allows_whitelisted_tools(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t5", "L4")
        for tool in ["skill_view", "memory_search", "session_search", "todo", "skill_manage", "skills_list"]:
            blocked, _ = should_block_tool_call("l4t5", tool, "L4")
            assert blocked is False, f"{tool} should be whitelisted"

    def test_l4_allows_after_planning_with_files_only(self, temp_tracking_dir):
        """L4 调用 planning-with-files 后即放行（agent-pool 不再是必需技能）。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4t6", "L4")
        track_skill_call("l4t6", "planning-with-files")
        blocked, _ = should_block_tool_call("l4t6", "send_message", "L4")
        assert blocked is False

    def test_l4_allows_all_tools_after_planning_with_files(self, temp_tracking_dir):
        """L4 调用 planning-with-files 后，所有工具放行。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4t7", "L4")
        track_skill_call("l4t7", "planning-with-files")
        for tool in ["terminal", "read_file", "delegate_task", "send_message"]:
            blocked, _ = should_block_tool_call("l4t7", tool, "L4")
            assert blocked is False

    def test_l4_allows_deep_thinking_called_before_planning(self, temp_tracking_dir):
        """L4 先调用 deep-thinking 不干扰最终完成判定。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex1", "L4")
        track_skill_call("l4flex1", "deep-thinking")
        blocked, _ = should_block_tool_call("l4flex1", "send_message", "L4")
        assert blocked is True
        track_skill_call("l4flex1", "planning-with-files")
        blocked, _ = should_block_tool_call("l4flex1", "terminal", "L4")
        assert blocked is False

    def test_l4_allows_openclaw_behavior_plan_called_before_planning(self, temp_tracking_dir):
        """L4 先调用 openclaw-behavior-plan 不干扰最终完成判定。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex2", "L4")
        track_skill_call("l4flex2", "openclaw-behavior-plan")
        blocked, _ = should_block_tool_call("l4flex2", "send_message", "L4")
        assert blocked is True
        track_skill_call("l4flex2", "planning-with-files")
        blocked, _ = should_block_tool_call("l4flex2", "terminal", "L4")
        assert blocked is False

    def test_l4_full_skill_chain(self, temp_tracking_dir):
        """L4 完整技能链：deep-thinking -> openclaw-behavior-plan -> planning-with-files -> 放行。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex3", "L4")
        skills = ["deep-thinking", "openclaw-behavior-plan", "planning-with-files"]
        for i, skill in enumerate(skills):
            if i < len(skills) - 1:
                blocked, _ = should_block_tool_call("l4flex3", "send_message", "L4")
                assert blocked is True, f"Should be blocked before calling {skill}"
            track_skill_call("l4flex3", skill)
        blocked, _ = should_block_tool_call("l4flex3", "send_message", "L4")
        assert blocked is False

    def test_l4_only_requires_planning_with_files(self, temp_tracking_dir):
        """L4 只需 planning-with-files 即可通过技能检查。"""
        from enforcer import create_tracker, track_skill_call, check_round_completion
        create_tracker("l4only", "L4")
        is_complete, missing = check_round_completion("l4only", "L4")
        assert not is_complete
        assert missing == ["planning-with-files"]
        track_skill_call("l4only", "planning-with-files")
        is_complete, missing = check_round_completion("l4only", "L4")
        assert is_complete
        assert missing == []

    def test_l4_agent_pool_not_required(self, temp_tracking_dir):
        """L4 不调用 agent-pool 仍可通过技能检查。"""
        from enforcer import create_tracker, track_skill_call, check_round_completion
        create_tracker("l4nopool", "L4")
        track_skill_call("l4nopool", "planning-with-files")
        is_complete, missing = check_round_completion("l4nopool", "L4")
        assert is_complete
        assert "agent-pool" not in missing


class TestL4EscapeHatch:
    """L4 逃生舱：输出工具连续拦截达到阈值后自动放行。"""

    def test_escape_releases_after_max_attempts(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4esc1", "L4")
        for i in range(3):
            blocked, _ = should_block_tool_call("l4esc1", "send_message", "L4")
            assert blocked is True, f"Attempt {i+1} should be blocked"
        blocked, _ = should_block_tool_call("l4esc1", "send_message", "L4")
        assert blocked is False

    def test_escape_resets_on_level_transition(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4esc2", "L4")
        for _ in range(2):
            should_block_tool_call("l4esc2", "send_message", "L4")
        create_tracker("l4esc2", "L3", force_reset=True)
        create_tracker("l4esc2", "L4", force_reset=True)
        for i in range(3):
            blocked, _ = should_block_tool_call("l4esc2", "send_message", "L4")
            assert blocked is True, f"After reset, attempt {i+1} should be blocked"


class TestL2L3Regression:
    """回归测试：L2/L3 输出工具仍拦截（信息工具放行由 test_block_scope 覆盖）。"""

    def test_l2_output_still_blocks(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("reg1", "L2")
        blocked, _ = should_block_tool_call("reg1", "send_message", "L2")
        assert blocked is True

    def test_l3_output_still_blocks(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("reg2", "L3")
        blocked, _ = should_block_tool_call("reg2", "send_message", "L3")
        assert blocked is True

    def test_l2_allows_after_deep_thinking(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("reg3", "L2")
        track_skill_call("reg3", "deep-thinking")
        blocked, _ = should_block_tool_call("reg3", "send_message", "L2")
        assert blocked is False

    def test_l3_allows_after_both_skills(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("reg4", "L3")
        track_skill_call("reg4", "deep-thinking")
        track_skill_call("reg4", "openclaw-behavior-plan")
        blocked, _ = should_block_tool_call("reg4", "send_message", "L3")
        assert blocked is False