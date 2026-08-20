"""SOUL-ENFORCER 优化验证测试。v5.12.0"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

PLUGIN_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PLUGIN_DIR))


class TestTimeoutConstants:
    """验证超时参数已按计划降低。"""

    def test_max_escape_attempts_is_3(self):
        """MAX_ESCAPE_ATTEMPTS 应从 7 降为 3。"""
        from soul_context_injector.constants import MAX_ESCAPE_ATTEMPTS
        assert MAX_ESCAPE_ATTEMPTS == 3, (
            f"MAX_ESCAPE_ATTEMPTS 应为 3，实际为 {MAX_ESCAPE_ATTEMPTS}"
        )

    def test_execution_timeout_is_120(self):
        """EXECUTION_TIMEOUT_SECONDS 应从 600 降为 120。"""
        from soul_context_injector.constants import EXECUTION_TIMEOUT_SECONDS
        assert EXECUTION_TIMEOUT_SECONDS == 120, (
            f"EXECUTION_TIMEOUT_SECONDS 应为 120，实际为 {EXECUTION_TIMEOUT_SECONDS}"
        )


class TestOutputToolsNarrowed:
    """验证 OUTPUT_TOOLS 已收窄。"""

    def test_output_tools_excludes_terminal(self):
        """OUTPUT_TOOLS 不应包含 terminal。"""
        from soul_context_injector.constants import OUTPUT_TOOLS
        assert "terminal" not in OUTPUT_TOOLS, (
            "terminal 不应出现在 OUTPUT_TOOLS 中"
        )

    def test_output_tools_excludes_execute_code(self):
        """OUTPUT_TOOLS 不应包含 execute_code。"""
        from soul_context_injector.constants import OUTPUT_TOOLS
        assert "execute_code" not in OUTPUT_TOOLS, (
            "execute_code 不应出现在 OUTPUT_TOOLS 中"
        )

    def test_output_tools_still_has_send_message(self):
        """OUTPUT_TOOLS 仍应包含 send_message。"""
        from soul_context_injector.constants import OUTPUT_TOOLS
        assert "send_message" in OUTPUT_TOOLS

    def test_output_tools_still_has_text_to_speech(self):
        """OUTPUT_TOOLS 仍应包含 text_to_speech。"""
        from soul_context_injector.constants import OUTPUT_TOOLS
        assert "text_to_speech" in OUTPUT_TOOLS


class TestEnforcementDowngrade:
    """验证非输出工具的拦截降级为警告。"""

    def test_check_required_skills_returns_false_for_missing(self, soul_init):
        """L4 tracker 缺少必需技能时 check_required_skills 应返回 False。"""
        from soul_context_injector.enforcer import create_tracker, check_required_skills
        from pathlib import Path

        session_id = "test_downgrade_check"
        tracker_file = Path.home() / ".hermes" / "skill-tracking" / f"{session_id}.json"
        if tracker_file.exists():
            tracker_file.unlink()

        # 创建 L4 tracker（缺少必需技能）
        create_tracker(session_id, "L4")

        # check_required_skills 应返回 False（技能缺失）
        result, error = check_required_skills(session_id)
        assert result is False, f"L4 缺少技能应返回 False，实际: result={result}"
        assert error is not None

        # 清理
        if tracker_file.exists():
            tracker_file.unlink()
