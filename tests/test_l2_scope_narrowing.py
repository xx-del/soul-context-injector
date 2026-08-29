"""L2/L3 执行范围缩窄测试。

验证：L2/L3 任务只在 OUTPUT_TOOLS（send_message, text_to_speech）时拦截，
不拦截信息获取工具（read_file, search_files, terminal, execute_code 等）。

TDD: 这些测试在范围缩窄实现之前会 FAIL。
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


# ============ 信息获取工具（应放行） ============
INFO_TOOLS = ["read_file", "search_files", "terminal", "execute_code", "web_search"]


class TestL2ScopeNarrowing:
    """L2 任务：信息获取工具应放行，仅 OUTPUT_TOOLS 拦截。"""

    @pytest.mark.parametrize("tool_name", INFO_TOOLS)
    def test_l2_info_tool_passes_without_skill(self, temp_tracking_dir, tool_name):
        """L2 任务未调用 deep-thinking 时，信息获取工具应放行。"""
        from enforcer import create_tracker, check_required_skills

        session_id = f"test_l2_scope_{tool_name}"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(
            session_id, tool_name=tool_name, task_level="L2"
        )
        assert result is True, (
            f"L2 范围缩窄后 {tool_name} 应放行，实际: result={result}, error={error}"
        )

    def test_l2_send_message_still_blocks_without_skill(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_output_blocks"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(
            session_id, tool_name="send_message", task_level="L2"
        )
        assert result is False, "L2 未调用技能时 send_message 应被 BLOCK"

    def test_l2_text_to_speech_still_blocks_without_skill(self, temp_tracking_dir):
        """L2 任务未调用 deep-thinking 时，text_to_speech 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l2_tts_blocks"
        create_tracker(session_id, "L2")

        result, error = check_required_skills(
            session_id, tool_name="text_to_speech", task_level="L2"
        )
        assert result is False, "L2 未调用技能时 text_to_speech 应被 BLOCK"

    def test_l2_output_tool_allows_after_skill_called(self, temp_tracking_dir):
        """L2 任务已调用 deep-thinking 后，send_message 应放行。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l2_output_after_skill"
        create_tracker(session_id, "L2")
        track_skill_call(session_id, "deep-thinking")

        result, error = check_required_skills(
            session_id, tool_name="send_message", task_level="L2"
        )
        assert result is True, "L2 已调用技能后 send_message 应放行"


class TestL3ScopeNarrowing:
    """L3 任务：信息获取工具应放行，仅 OUTPUT_TOOLS 拦截。"""

    @pytest.mark.parametrize("tool_name", INFO_TOOLS)
    def test_l3_info_tool_passes_without_skill(self, temp_tracking_dir, tool_name):
        """L3 任务未调用 required_skills 时，信息获取工具应放行。"""
        from enforcer import create_tracker, check_required_skills

        session_id = f"test_l3_scope_{tool_name}"
        create_tracker(session_id, "L3")

        result, error = check_required_skills(
            session_id, tool_name=tool_name, task_level="L3"
        )
        assert result is True, (
            f"L3 范围缩窄后 {tool_name} 应放行，实际: result={result}, error={error}"
        )

    def test_l3_send_message_still_blocks_without_skill(self, temp_tracking_dir):
        """L3 任务未调用 required_skills 时，send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l3_output_blocks"
        create_tracker(session_id, "L3")

        result, error = check_required_skills(
            session_id, tool_name="send_message", task_level="L3"
        )
        assert result is False, "L3 未调用技能时 send_message 应被 BLOCK"

    def test_l3_partial_skill_info_tool_passes(self, temp_tracking_dir):
        """L3 任务只调用了 deep-thinking（缺 openclaw-behavior-plan），
        信息获取工具仍应放行。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l3_partial_info"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        result, error = check_required_skills(
            session_id, tool_name="terminal", task_level="L3"
        )
        assert result is True, (
            f"L3 部分技能调用后 terminal 应放行，实际: result={result}, error={error}"
        )

    def test_l3_partial_skill_output_blocks(self, temp_tracking_dir):
        """L3 任务只调用了 deep-thinking（缺 openclaw-behavior-plan），
        send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, track_skill_call, check_required_skills

        session_id = "test_l3_partial_output"
        create_tracker(session_id, "L3")
        track_skill_call(session_id, "deep-thinking")

        result, error = check_required_skills(
            session_id, tool_name="send_message", task_level="L3"
        )
        assert result is False, "L3 部分技能调用后 send_message 应被 BLOCK"


class TestL4Unchanged:
    """L4 任务：保持原有宽松行为不变。"""

    def test_l4_info_tool_still_passes(self, temp_tracking_dir):
        """L4 任务信息获取工具仍应放行（宽松模式）。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l4_info_still_passes"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(
            session_id, tool_name="read_file", task_level="L4"
        )
        assert result is True, "L4 info tool 应放行"

    def test_l4_output_tool_still_blocks(self, temp_tracking_dir):
        """L4 任务 send_message 仍应被 BLOCK。"""
        from enforcer import create_tracker, check_required_skills

        session_id = "test_l4_output_still_blocks"
        create_tracker(session_id, "L4")

        result, error = check_required_skills(
            session_id, tool_name="send_message", task_level="L4"
        )
        assert result is False, "L4 send_message 应被 BLOCK"


class TestHookIntegration:
    """测试 pre_tool_call_hook 层面的范围缩窄。"""

    def test_l2_hook_passes_read_file(self, temp_tracking_dir):
        """L2 任务 pre_tool_call_hook 对 read_file 应放行（不拦截）。"""
        from enforcer import create_tracker

        session_id = "test_hook_l2_read_file"
        create_tracker(session_id, "L2")

        # 模拟 hook 的逻辑：只有 OUTPUT_TOOLS 才调用 check_required_skills
        from constants import OUTPUT_TOOLS
        from enforcer import check_required_skills

        tool_name = "read_file"
        # 范围缩窄后：非 OUTPUT_TOOLS 不调用 check_required_skills
        should_check = tool_name in OUTPUT_TOOLS
        assert not should_check, (
            f"范围缩窄后 read_file 不应在 OUTPUT_TOOLS 中"
        )

    def test_l2_hook_checks_send_message(self, temp_tracking_dir):
        """L2 任务 pre_tool_call_hook 对 send_message 应检查。"""
        from constants import OUTPUT_TOOLS

        tool_name = "send_message"
        should_check = tool_name in OUTPUT_TOOLS
        assert should_check, "send_message 应在 OUTPUT_TOOLS 中"
