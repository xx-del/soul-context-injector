"""L4 全工具拦截测试（v5.15.0）。

验证 L4 任务在 planning-with-files 调用前拦截所有非白名单工具，
调用后放行；escape_attempts 达到阈值自动放行。
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


class TestL4FullToolBlocking:
    """L4 任务应拦截所有非白名单工具（与 L2/L3 同等行为）。"""

    def test_l4_blocks_terminal_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t1", "L4")
        blocked, _ = should_block_tool_call("l4t1", "terminal", "L4")
        assert blocked is True

    def test_l4_blocks_read_file_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t2", "L4")
        blocked, _ = should_block_tool_call("l4t2", "read_file", "L4")
        assert blocked is True

    def test_l4_blocks_write_file_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t3", "L4")
        blocked, _ = should_block_tool_call("l4t3", "write_file", "L4")
        assert blocked is True

    def test_l4_blocks_delegate_task_before_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t4", "L4")
        blocked, _ = should_block_tool_call("l4t4", "delegate_task", "L4")
        assert blocked is True

    def test_l4_allows_whitelisted_tools(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4t5", "L4")
        for tool in ["skill_view", "memory_search", "session_search", "todo", "skill_manage", "skills_list"]:
            blocked, _ = should_block_tool_call("l4t5", tool, "L4")
            assert blocked is False, f"{tool} should be whitelisted"

    def test_l4_still_blocks_after_only_planning_with_files(self, temp_tracking_dir):
        """L4 仅调用 planning-with-files 时仍拦截（需两个技能都调用）。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4t6", "L4")
        track_skill_call("l4t6", "planning-with-files")
        blocked, _ = should_block_tool_call("l4t6", "terminal", "L4")
        assert blocked is True

    def test_l4_allows_all_tools_after_both_skills(self, temp_tracking_dir):
        """L4 调用 planning-with-files + agent-pool 后，所有工具放行。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4t7", "L4")
        track_skill_call("l4t7", "planning-with-files")
        track_skill_call("l4t7", "agent-pool")
        for tool in ["terminal", "read_file", "delegate_task"]:
            blocked, _ = should_block_tool_call("l4t7", tool, "L4")
            assert blocked is False

    def test_l4_allows_deep_thinking_called_before_planning(self, temp_tracking_dir):
        """L4 先调用 deep-thinking 不干扰最终完成判定。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex1", "L4")
        track_skill_call("l4flex1", "deep-thinking")
        blocked, _ = should_block_tool_call("l4flex1", "terminal", "L4")
        assert blocked is True
        track_skill_call("l4flex1", "planning-with-files")
        track_skill_call("l4flex1", "agent-pool")
        blocked, _ = should_block_tool_call("l4flex1", "terminal", "L4")
        assert blocked is False

    def test_l4_allows_openclaw_behavior_plan_called_before_planning(self, temp_tracking_dir):
        """L4 先调用 openclaw-behavior-plan 不干扰最终完成判定。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex2", "L4")
        track_skill_call("l4flex2", "openclaw-behavior-plan")
        blocked, _ = should_block_tool_call("l4flex2", "terminal", "L4")
        assert blocked is True
        track_skill_call("l4flex2", "planning-with-files")
        track_skill_call("l4flex2", "agent-pool")
        blocked, _ = should_block_tool_call("l4flex2", "terminal", "L4")
        assert blocked is False

    def test_l4_full_skill_chain(self, temp_tracking_dir):
        """L4 完整技能链：deep-thinking -> openclaw-behavior-plan -> planning-with-files -> agent-pool -> 放行。"""
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("l4flex3", "L4")
        skills = ["deep-thinking", "openclaw-behavior-plan", "planning-with-files", "agent-pool"]
        for i, skill in enumerate(skills):
            if i < len(skills) - 1:
                blocked, _ = should_block_tool_call("l4flex3", "terminal", "L4")
                assert blocked is True, f"Should be blocked before calling {skill}"
            track_skill_call("l4flex3", skill)
        blocked, _ = should_block_tool_call("l4flex3", "terminal", "L4")
        assert blocked is False


class TestL4EscapeHatch:
    """L4 逃生舱：连续拦截达到阈值后自动放行。"""

    def test_escape_releases_after_max_attempts(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4esc1", "L4")
        for i in range(3):
            blocked, _ = should_block_tool_call("l4esc1", "terminal", "L4")
            assert blocked is True, f"Attempt {i+1} should be blocked"
        blocked, _ = should_block_tool_call("l4esc1", "terminal", "L4")
        assert blocked is False

    def test_escape_resets_on_level_transition(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("l4esc2", "L4")
        for _ in range(2):
            should_block_tool_call("l4esc2", "terminal", "L4")
        create_tracker("l4esc2", "L3", force_reset=True)
        create_tracker("l4esc2", "L4", force_reset=True)
        for i in range(3):
            blocked, _ = should_block_tool_call("l4esc2", "terminal", "L4")
            assert blocked is True, f"After reset, attempt {i+1} should be blocked"


class TestL2L3Regression:
    """回归测试：L2/L3 行为不变。"""

    def test_l2_still_blocks_all_tools(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("reg1", "L2")
        blocked, _ = should_block_tool_call("reg1", "terminal", "L2")
        assert blocked is True

    def test_l3_still_blocks_all_tools(self, temp_tracking_dir):
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("reg2", "L3")
        blocked, _ = should_block_tool_call("reg2", "terminal", "L3")
        assert blocked is True

    def test_l2_allows_after_deep_thinking(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("reg3", "L2")
        track_skill_call("reg3", "deep-thinking")
        blocked, _ = should_block_tool_call("reg3", "terminal", "L2")
        assert blocked is False

    def test_l3_allows_after_both_skills(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, should_block_tool_call
        create_tracker("reg4", "L3")
        track_skill_call("reg4", "deep-thinking")
        track_skill_call("reg4", "openclaw-behavior-plan")
        blocked, _ = should_block_tool_call("reg4", "terminal", "L3")
        assert blocked is False
