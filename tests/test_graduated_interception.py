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
    """首次警告，二次仍警告，三次 BLOCK（GRADUATED_BLOCK_THRESHOLD=3）。"""

    def test_first_violation_warns_not_blocks(self, temp_tracking_dir):
        """第1次违规：警告但放行。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("grad1", "L2")
        blocked, msg = should_block_tool_call("grad1", "write_file", "L2")
        assert blocked is False, "第1次违规应放行"

    def test_second_violation_warns_not_blocks(self, temp_tracking_dir):
        """第2次违规：仍警告（阈值=3，需3次才BLOCK）。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("grad2", "L2")
        # 第1次
        should_block_tool_call("grad2", "write_file", "L2")
        # 第2次
        blocked, msg = should_block_tool_call("grad2", "write_file", "L2")
        assert blocked is False, "第2次违规应仍警告（阈值=3）"

    def test_third_violation_blocks(self, temp_tracking_dir):
        """第3次违规：BLOCK（GRADUATED_BLOCK_THRESHOLD=3）。"""
        from enforcer import create_tracker, should_block_tool_call
        create_tracker("grad2b", "L2")
        # 第1次
        should_block_tool_call("grad2b", "write_file", "L2")
        # 第2次
        should_block_tool_call("grad2b", "write_file", "L2")
        # 第3次
        blocked, msg = should_block_tool_call("grad2b", "write_file", "L2")
        assert blocked is True, "第3次违规应BLOCK"
        assert "deep-thinking" in msg

    def test_skill_view_call_resets_violation_count(self, temp_tracking_dir):
        """调用必需技能后重置违规计数。"""
        from enforcer import create_tracker, should_block_tool_call, track_skill_call
        create_tracker("grad3", "L2")
        should_block_tool_call("grad3", "write_file", "L2")  # 第1次
        track_skill_call("grad3", "deep-thinking")  # 调用技能
        blocked, _ = should_block_tool_call("grad3", "write_file", "L2")  # 重置后第1次
        assert blocked is False, "调用技能后应重置计数"

    def test_violation_count_only_resets_on_missing_skill(self, temp_tracking_dir):
        """只在调用缺失的必需技能时重置 violation_count。"""
        from enforcer import create_tracker, should_block_tool_call, track_skill_call
        from enforcer import _write_tracker_file, GRADUATED_BLOCK_THRESHOLD

        # === 场景1：调用缺失技能 → violation_count 应重置 ===
        session_id = "grad4"
        create_tracker(session_id, "L3")
        # L3 需要 deep-thinking + openclaw-behavior-plan
        should_block_tool_call(session_id, "write_file", "L3")  # violation_count=1
        track_skill_call(session_id, "deep-thinking")  # 缺失的 → 重置为 0
        blocked, _ = should_block_tool_call(session_id, "write_file", "L3")
        assert blocked is False, "调用缺失技能应重置 violation_count（第2次=警告，不BLOCK）"

        # === 场景2：调用非缺失技能 → violation_count 不应重置 ===
        # 重置 tracker 状态：清空 called_skills，保留 required_skills
        from enforcer import get_tracker
        tracker = get_tracker(session_id)
        tracker["current"]["called_skills"] = ["deep-thinking"]  # 只有 deep-thinking
        tracker["violation_count"] = 0
        _write_tracker_file(session_id, tracker)
        # 此时 required=['deep-thinking','openclaw-behavior-plan'], called=['deep-thinking']
        # openclaw-behavior-plan 仍缺失

        # 累积 violation_count 到 GRADUATED_BLOCK_THRESHOLD 次，非缺失技能不应重置
        for i in range(GRADUATED_BLOCK_THRESHOLD):
            should_block_tool_call(session_id, "write_file", "L3")  # violation_count 递增
            track_skill_call(session_id, "deep-thinking")  # 非缺失，is_new=False，不重置
        blocked, _ = should_block_tool_call(session_id, "write_file", "L3")
        assert blocked is True, "调用非缺失技能不应重置 violation_count"
