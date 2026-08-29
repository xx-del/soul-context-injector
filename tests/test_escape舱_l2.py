"""L2/L3 逃生舱机制测试（v5.14.0 范围缩窄版）。"""
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

class TestEscape舱L2:
    def test_l2_escape舱_after_max_attempts_on_output_tool(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills, MAX_ESCAPE_ATTEMPTS
        create_tracker("esc1", "L2")
        for i in range(MAX_ESCAPE_ATTEMPTS):
            result, _ = check_required_skills("esc1", tool_name="send_message", task_level="L2")
            if i < MAX_ESCAPE_ATTEMPTS - 1:
                assert result is False, f"第 {i+1} 次应 BLOCK"
        result, _ = check_required_skills("esc1", tool_name="send_message", task_level="L2")
        assert result is True
    def test_l2_info_tool_passes_immediately(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("esc2", "L2")
        result, _ = check_required_skills("esc2", tool_name="read_file", task_level="L2")
        assert result is True
    def test_l3_escape舱_after_max_attempts_on_output_tool(self, temp_tracking_dir):
        from enforcer import create_tracker, track_skill_call, check_required_skills, MAX_ESCAPE_ATTEMPTS
        create_tracker("esc3", "L3")
        track_skill_call("esc3", "deep-thinking")
        for i in range(MAX_ESCAPE_ATTEMPTS):
            result, _ = check_required_skills("esc3", tool_name="send_message", task_level="L3")
            if i < MAX_ESCAPE_ATTEMPTS - 1:
                assert result is False, f"第 {i+1} 次应 BLOCK"
        result, _ = check_required_skills("esc3", tool_name="send_message", task_level="L3")
        assert result is True
    def test_l3_info_tool_passes_immediately(self, temp_tracking_dir):
        from enforcer import create_tracker, check_required_skills
        create_tracker("esc4", "L3")
        result, _ = check_required_skills("esc4", tool_name="terminal", task_level="L3")
        assert result is True
