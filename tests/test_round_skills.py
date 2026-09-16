"""轮次级技能追踪测试"""
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


class TestRoundSkills:
    """round_skills 每轮清空，called_skills 跨轮累积。"""

    def test_round_skills_cleared_on_new_request(self, temp_tracking_dir):
        """新请求时 round_skills 清空，called_skills 保留。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        session_id = "round1"
        create_tracker(session_id, "L2", force_reset=True)
        track_skill_call(session_id, "deep-thinking")

        # 新请求
        create_tracker(session_id, "L2", force_reset=True)
        tracker = get_tracker(session_id)
        round_skills = tracker["current"].get("round_skills", [])
        called_skills = tracker["current"]["called_skills"]

        assert "deep-thinking" not in round_skills, "round_skills 应被清空"
        assert "deep-thinking" in called_skills, "called_skills 应保留"

    def test_l2_requires_deep_thinking_each_round(self, temp_tracking_dir):
        """L2 每轮必须调用 deep-thinking。"""
        from enforcer import create_tracker, track_skill_call, check_round_completion

        session_id = "round2"
        # 模拟上一轮调用了 deep-thinking（累积到 called_skills）
        create_tracker(session_id, "L2", force_reset=True)
        track_skill_call(session_id, "deep-thinking")

        # 新一轮：round_skills 被清空，但 called_skills 保留
        create_tracker(session_id, "L2", force_reset=True)

        # check_round_completion 检查 called_skills（累积）→ 应该通过
        is_complete, missing = check_round_completion(session_id, "L2")
        assert is_complete, "累积模式下 check_round_completion 应通过"

        # 但 round_skills 为空（本轮未调用）→ L2 轮次级强制应拦截
        from enforcer import get_tracker
        tracker = get_tracker(session_id)
        round_skills = tracker["current"].get("round_skills", [])
        assert "deep-thinking" not in round_skills, "round_skills 应为空（本轮未调用）"

    def test_same_level_new_request_clears_round_skills(self, temp_tracking_dir):
        """同等级新请求时 round_skills 清空，called_skills 保留。"""
        from enforcer import create_tracker, track_skill_call, get_tracker

        session_id = "round3"
        # 第1轮：调用 deep-thinking
        create_tracker(session_id, "L2", force_reset=True)
        track_skill_call(session_id, "deep-thinking")

        # 第2轮：同等级，force_reset=False
        create_tracker(session_id, "L2", force_reset=False)
        tracker = get_tracker(session_id)
        round_skills = tracker["current"].get("round_skills", [])
        called_skills = tracker["current"]["called_skills"]

        assert "deep-thinking" not in round_skills, "round_skills 应被清空"
        assert "deep-thinking" in called_skills, "called_skills 应保留"
