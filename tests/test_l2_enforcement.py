"""L2/L3 技能强制分级测试（v5.14.0 范围缩窄版）。"""
import sys, tempfile
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

class TestL2Enforcement:
    def test_l2_info_tool_passes_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t1", "L2")
        result, _ = check_required_skills("t1", tool_name="read_file", task_level="L2")
        assert result is True
    def test_l2_info_tool_passes_search_files(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t2", "L2")
        result, _ = check_required_skills("t2", tool_name="search_files", task_level="L2")
        assert result is True
    def test_l2_info_tool_passes_terminal(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t3", "L2")
        result, _ = check_required_skills("t3", tool_name="terminal", task_level="L2")
        assert result is True
    def test_l2_with_skill_allows_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, check_required_skills
        create_tracker("t4", "L2")
        track_skill_call("t4", "deep-thinking")
        result, _ = check_required_skills("t4", tool_name="read_file", task_level="L2")
        assert result is True
    def test_l2_send_message_blocks_until_skill_called(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t5", "L2")
        result, _ = check_required_skills("t5", tool_name="send_message", task_level="L2")
        assert result is False

class TestL3Enforcement:
    def test_l3_info_tool_passes_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t6", "L3")
        result, _ = check_required_skills("t6", tool_name="read_file", task_level="L3")
        assert result is True
    def test_l3_partial_skill_passes_terminal(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, check_required_skills
        create_tracker("t7", "L3")
        track_skill_call("t7", "deep-thinking")
        result, _ = check_required_skills("t7", tool_name="terminal", task_level="L3")
        assert result is True
    def test_l3_all_skills_allows_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, check_required_skills
        create_tracker("t8", "L3")
        track_skill_call("t8", "deep-thinking")
        track_skill_call("t8", "openclaw-behavior-plan")
        result, _ = check_required_skills("t8", tool_name="read_file", task_level="L3")
        assert result is True
    def test_l3_send_message_blocks_without_skill(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t9", "L3")
        result, _ = check_required_skills("t9", tool_name="send_message", task_level="L3")
        assert result is False
    def test_l3_partial_skill_blocks_send_message(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, check_required_skills
        create_tracker("t10", "L3")
        track_skill_call("t10", "deep-thinking")
        result, error = check_required_skills("t10", tool_name="send_message", task_level="L3")
        assert result is False
        assert error is not None and "openclaw-behavior-plan" in error

class TestL4EnforcementUnchanged:
    def test_l4_missing_skill_allows_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t11", "L4")
        result, _ = check_required_skills("t11", tool_name="read_file", task_level="L4")
        assert result is True
    def test_l4_missing_skill_blocks_send_message(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t12", "L4")
        result, _ = check_required_skills("t12", tool_name="send_message", task_level="L4")
        assert result is False

class TestNoTaskLevelBackwardCompat:
    def test_no_task_level_allows_read_file(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t13", "L4")
        result, _ = check_required_skills("t13", tool_name="read_file")
        assert result is True
    def test_no_task_level_blocks_send_message(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("t14", "L4")
        result, _ = check_required_skills("t14", tool_name="send_message")
        assert result is False
