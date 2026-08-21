"""L2/L3 逃生舱机制测试。"""
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


class TestEscape舱L2:
    """L2/L3 逃生舱机制。"""

    def test_l2_escape舱_after_max_attempts(self, temp_tracking_dir):
        """L2 任务达到 MAX_ESCAPE_ATTEMPTS 后应自动放行。"""
        from enforcer import (
            create_tracker, check_required_skills,
            MAX_ESCAPE_ATTEMPTS,
        )

        session_id = "test_escape_l2"
        create_tracker(session_id, "L2")

        with patch('enforcer.check_execution_timeout', return_value=False):
            for i in range(MAX_ESCAPE_ATTEMPTS):
                result, error = check_required_skills(
                    session_id, tool_name="read_file", task_level="L2"
                )
                assert result is False, f"第 {i+1} 次应 BLOCK"

            result, error = check_required_skills(
                session_id, tool_name="read_file", task_level="L2"
            )
            assert result is True, f"达到 {MAX_ESCAPE_ATTEMPTS} 次后应放行，实际: {result}"

    def test_l2_timeout_does_not_override_escape舱(self, temp_tracking_dir):
        """超时检查不应在 escape_attempts 检查之前触发。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_timeout_not_override"
        create_tracker(session_id, "L2")

        with patch('enforcer.check_execution_timeout', return_value=True):
            result, error = check_required_skills(
                session_id, tool_name="read_file", task_level="L2"
            )
            assert result is False, (
                f"超时不应覆盖未达阈值的 escape_attempts，实际: {result}"
            )

    def test_l3_escape舱_after_max_attempts(self, temp_tracking_dir):
        """L3 任务达到 MAX_ESCAPE_ATTEMPTS 后应自动放行。"""
        from enforcer import (
            create_tracker, track_skill_call, check_required_skills,
            MAX_ESCAPE_ATTEMPTS,
        )

        session_id = "test_escape_l3"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        with patch('enforcer.check_execution_timeout', return_value=False):
            for i in range(MAX_ESCAPE_ATTEMPTS):
                result, error = check_required_skills(
                    session_id, tool_name="terminal", task_level="L3"
                )
                assert result is False, f"第 {i+1} 次应 BLOCK"

            result, error = check_required_skills(
                session_id, tool_name="terminal", task_level="L3"
            )
            assert result is True, f"达到 {MAX_ESCAPE_ATTEMPTS} 次后应放行"
