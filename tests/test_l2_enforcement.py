"""L2/L3 技能强制分级测试。

验证：L2/L3 任务未调用 required_skills 时，非输出工具（read_file 等）
也应被 BLOCK，而不只是警告。L4 保持现有宽松行为。
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
    """使用临时目录存储追踪文件，测试后自动清理。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch('enforcer.TRACKING_DIR', Path(tmpdir)):
            yield Path(tmpdir)


class TestL2Enforcement:
    """L2 任务：未调用 deep-thinking 时所有工具调用应被 BLOCK。"""

    def test_l2_missing_skill_blocks_read_file(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，read_file 应返回 (False, error)。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_blocks_read_file"
        create_tracker(session_id, "L2")

        # 未调用 deep-thinking，尝试 read_file
        result, error = check_required_skills(session_id, tool_name="read_file", task_level="L2")

        assert result is False, f"L2 缺少 deep-thinking 时 read_file 应被 BLOCK，实际: {result}"
        assert error is not None
        assert "deep-thinking" in error

    def test_l2_missing_skill_blocks_search_files(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，search_files 应返回 (False, error)。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_blocks_search_files"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(session_id, tool_name="search_files", task_level="L2")

        assert result is False, f"L2 缺少 deep-thinking 时 search_files 应被 BLOCK，实际: {result}"
        assert error is not None

    def test_l2_missing_skill_blocks_terminal(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，terminal 应返回 (False, error)。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_blocks_terminal"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(session_id, tool_name="terminal", task_level="L2")

        assert result is False, f"L2 缺少 deep-thinking 时 terminal 应被 BLOCK，实际: {result}"

    def test_l2_with_skill_allows_read_file(self, temp_tracking_dir):
        """L2 任务已调用 deep-thinking 时，read_file 应放行。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l2_allows_read_file"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        result, error = check_required_skills(session_id, tool_name="read_file", task_level="L2")

        assert result is True, f"L2 已调用 deep-thinking 时 read_file 应放行，实际: {result}"

    def test_l2_send_message_blocks_until_skill_called(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，send_message 也应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_blocks_send_message"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(session_id, tool_name="send_message", task_level="L2")

        assert result is False, f"L2 缺少 deep-thinking 时 send_message 应被 BLOCK"


class TestL3Enforcement:
    """L3 任务：未调用 required_skills 时所有工具调用应被 BLOCK。"""

    def test_l3_missing_skill_blocks_read_file(self, temp_tracking_dir):
        """L3 任务未调用 deep-thinking 时，read_file 应返回 (False, error)。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l3_blocks_read_file"
        create_tracker(session_id, "L3")

        result, error = check_required_skills(session_id, tool_name="read_file", task_level="L3")

        assert result is False, f"L3 缺少 deep-thinking 时 read_file 应被 BLOCK，实际: {result}"
        assert "deep-thinking" in error

    def test_l3_partial_skill_blocks_terminal(self, temp_tracking_dir):
        """L3 任务只调用了 deep-thinking（缺 openclaw-behavior-plan），terminal 应被 BLOCK。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l3_partial_blocks"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        result, error = check_required_skills(session_id, tool_name="terminal", task_level="L3")

        assert result is False, f"L3 缺少 openclaw-behavior-plan 时 terminal 应被 BLOCK"
        assert "openclaw-behavior-plan" in error

    def test_l3_all_skills_allows_read_file(self, temp_tracking_dir):
        """L3 任务已调用所有 required_skills 时，read_file 应放行。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l3_allows"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")
        track_skill_call(session_id, "openclaw-behavior-plan")

        result, error = check_required_skills(session_id, tool_name="read_file", task_level="L3")

        assert result is True, f"L3 已调用所有技能时 read_file 应放行"


class TestL4EnforcementUnchanged:
    """L4 任务：保持现有宽松行为——中间工具可自由调用。"""

    def test_l4_missing_skill_allows_read_file(self, temp_tracking_dir):
        """L4 任务未调用 planning-with-files 时，read_file 仍应放行（只警告）。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l4_allows_read_file"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(session_id, tool_name="read_file", task_level="L4")

        assert result is True, f"L4 缺少技能时 read_file 应放行（宽松模式），实际: {result}"

    def test_l4_missing_skill_blocks_send_message(self, temp_tracking_dir):
        """L4 任务未调用 planning-with-files 时，send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l4_blocks_send_message"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(session_id, tool_name="send_message", task_level="L4")

        assert result is False, f"L4 缺少技能时 send_message 应被 BLOCK"


class TestNoTaskLevelBackwardCompat:
    """向后兼容：不传 task_level 时保持旧行为。"""

    def test_no_task_level_allows_read_file(self, temp_tracking_dir):
        """不传 task_level 时，非输出工具应放行（兼容旧行为）。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_no_level_compat"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(session_id, tool_name="read_file")

        assert result is True, f"不传 task_level 时 read_file 应放行"

    def test_no_task_level_blocks_send_message(self, temp_tracking_dir):
        """不传 task_level 时，send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_no_level_blocks_send"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(session_id, tool_name="send_message")

        assert result is False, f"不传 task_level 时 send_message 应被 BLOCK"
