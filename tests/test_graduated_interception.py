"""分级拦截策略测试"""
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


class TestGraduatedInterception:
    """首次警告，二次 BLOCK。"""

    def test_first_violation_warns_not_blocks(self, temp_tracking_dir):
        """第1次违规：警告但放行。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("grad1", "L2")
        blocked, msg = should_block_tool_call("grad1", "terminal", "L2")
        assert blocked is False, "第1次违规应放行"

    def test_second_violation_blocks(self, temp_tracking_dir):
        """第2次违规：BLOCK。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("grad2", "L2")
        # 第1次
        should_block_tool_call("grad2", "terminal", "L2")
        # 第2次
        blocked, msg = should_block_tool_call("grad2", "terminal", "L2")
        assert blocked is True, "第2次违规应BLOCK"
        assert "deep-thinking" in msg

    def test_skill_view_call_resets_violation_count(self, temp_tracking_dir):
        """调用必需技能后重置违规计数。"""
        from enforcer import create_tracker, should_block_tool_call, track_skill_call
        create_tracker("grad3", "L2")
        should_block_tool_call("grad3", "terminal", "L2")  # 第1次
        track_skill_call("grad3", "deep-thinking")  # 调用技能
        blocked, _ = should_block_tool_call("grad3", "terminal", "L2")  # 重置后第1次
        assert blocked is False, "调用技能后应重置计数"

    def test_violation_count_only_resets_on_missing_skill(self, temp_tracking_dir):
        """只在调用缺失的必需技能时重置 violation_count。"""
        from enforcer import create_tracker, should_block_tool_call, track_skill_call

        session_id = "grad4"
        create_tracker(session_id, "L3")
        # L3 需要 deep-thinking + openclaw-behavior-plan
        # 两个都没调用

        # 第1次违规
        should_block_tool_call(session_id, "terminal", "L3")
        # 调用 deep-thinking（已在累积中，不是缺失的）
        track_skill_call(session_id, "deep-thinking")
        # violation_count 应不被重置（deep-thinking 不是缺失技能）
        # 第2次违规应 BLOCK
        blocked, msg = should_block_tool_call(session_id, "terminal", "L3")
        assert blocked is True, "调用非缺失技能不应重置 violation_count"
